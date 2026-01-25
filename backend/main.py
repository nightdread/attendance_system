from fastapi import FastAPI, HTTPException, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, PlainTextResponse, Response
import json
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
import uvicorn
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from pathlib import Path
# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from config import (
    BOT_USERNAME,
    API_HOST, API_PORT, QR_UPDATE_INTERVAL, SECRET_KEY, SESSION_SECRET_KEY, API_KEY, DB_PATH
)
from database import Database
from auth.jwt_handler import JWTHandler
from utils.logger import (
    log_error, log_request, log_auth_event,
    log_failed_login, log_successful_login, log_role_change,
    log_suspicious_activity, log_rate_limit_exceeded, log_csrf_failure,
    log_unauthorized_access, log_data_export
)
from utils.cache import cache
from utils.validators import (
    validate_username, validate_password, validate_fio, validate_role,
    validate_department, validate_position, sanitize_string
)
from utils.rate_limit import rate_limit
from utils.csrf import set_csrf_token, get_csrf_token, require_csrf_token

app = FastAPI(
    title="Attendance System API",
    description="""
    API для системы учета рабочего времени.
    
    ## Аутентификация
    
    API поддерживает два способа аутентификации:
    1. **API Key** - через заголовок `X-API-Key` (если настроен API_KEY)
    2. **JWT Token** - через сессию или заголовок `Authorization: Bearer <token>`
    
    ## Rate Limiting
    
    Endpoints имеют ограничения по частоте запросов:
    - `/api/active_token`: 10 запросов/минуту
    - `/api/user/*`: 20 запросов/минуту (GET), 10 запросов/минуту (PUT)
    - `/api/analytics/*`: 30 запросов/минуту
    - `/login`: 5 попыток/5 минут
    
    При превышении лимита возвращается HTTP 429.
    
    ## CSRF Protection
    
    Все модифицирующие операции (POST, PUT, DELETE) требуют CSRF токен:
    - Для форм: поле `csrf_token`
    - Для JSON: заголовок `X-CSRF-Token`
    
    ## Версионирование
    
    Текущая версия API: **v1**
    
    ## Ошибки
    
    API возвращает стандартные HTTP коды:
    - `200` - Успех
    - `400` - Неверный запрос (валидация)
    - `401` - Не авторизован
    - `403` - Доступ запрещен (недостаточно прав или CSRF)
    - `404` - Не найдено
    - `429` - Превышен rate limit
    - `500` - Внутренняя ошибка сервера
    - `503` - Сервис недоступен (health check)
    """,
    version="1.0.0",
    contact={
        "name": "Attendance System Support",
    },
    license_info={
        "name": "Proprietary",
    },
    tags_metadata=[
        {
            "name": "authentication",
            "description": "Аутентификация и авторизация",
        },
        {
            "name": "tokens",
            "description": "Управление токенами для отметки посещаемости",
        },
        {
            "name": "users",
            "description": "Управление пользователями (требует admin/manager роль)",
        },
        {
            "name": "analytics",
            "description": "Аналитика и статистика (требует admin/manager/hr роль)",
        },
        {
            "name": "health",
            "description": "Проверка здоровья системы и метрики",
        },
    ]
)

# Add session middleware (use dedicated session secret, defaulting to SECRET_KEY)
# max_age=31536000 = 1 year in seconds for long-lived sessions (terminal)
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET_KEY, max_age=31536000)

# Login rate limiter (Redis + fallback memory)
MAX_LOGIN_ATTEMPTS = 5
LOGIN_WINDOW_SEC = 300  # 5 minutes
LOGIN_BLOCK_SEC = 900   # block 15 minutes
LOGIN_ATTEMPTS = defaultdict(list)


def authorize_request(
    request: Request,
    require_roles: list[str] | None = None,
    allow_terminal_session: bool = False,
):
    """Authorize API requests.

    - If API_KEY is set, require matching X-API-Key header.
    - Else, allow authenticated session (access_token in session or bearer header).
    - Optionally allow terminal session flag (set on public terminal page) for read-only endpoints.
    """
    # API key check (if configured and header provided)
    if API_KEY:
        header_key = request.headers.get("X-API-Key")
        if header_key == API_KEY:
            return {"role": "api"}

    # Allow terminal session flag (for public terminal QR updates) if enabled
    if allow_terminal_session and request.session.get("terminal_allowed"):
        return {"role": "terminal"}

    # Session or bearer token
    token = request.session.get("access_token")
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1]

    if not token:
        client_ip = request.client.host if request.client else "unknown"
        log_unauthorized_access(str(request.url.path), ip_address=client_ip, reason="No token provided")
        raise HTTPException(status_code=401, detail="Unauthorized")

    payload = JWTHandler.verify_token(token)
    if not payload:
        client_ip = request.client.host if request.client else "unknown"
        log_unauthorized_access(str(request.url.path), ip_address=client_ip, reason="Invalid token")
        raise HTTPException(status_code=401, detail="Unauthorized")

    role = payload.get("role", "user")
    username = payload.get("sub")
    if require_roles and role not in require_roles:
        client_ip = request.client.host if request.client else "unknown"
        log_unauthorized_access(str(request.url.path), user=username, ip_address=client_ip, reason=f"Insufficient permissions: role '{role}' not in {require_roles}")
        raise HTTPException(status_code=403, detail="Forbidden")

    return payload

# Mount static files (disabled - no static files needed)
# app.mount("/static", StaticFiles(directory="../static"), name="static")

# Resolve paths that work both locally and inside Docker
BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = BASE_DIR / "templates"

# Templates
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Database instance
db = Database(str(DB_PATH))

# Dependency to get database
def get_db():
    return db

def build_terminal_context(request: Request, db: Database) -> dict:
    """Prepare context for the public terminal page"""
    token_data = db.get_active_token()
    token = token_data['token'] if token_data else db.create_token()
    url = f"https://t.me/{BOT_USERNAME}?start={token}"

    # Проверяем авторизацию для отображения админских ссылок (если пользователь уже логинился)
    user_info = None
    try:
        jwt_token = request.session.get("access_token")
        if jwt_token:
            payload = JWTHandler.verify_token(jwt_token)
            username = payload.get("sub")
            if username:
                user = db.get_web_user_by_username(username)
                if user:
                    user_info = {
                        "username": username,
                        "role": user.get("role", "user"),
                        "is_admin": user.get("role") in ["admin", "manager", "hr"]
                    }
    except Exception:
        # если токен невалиден, просто показываем публичную страницу
        pass

    return {
            "request": request,
            "token": token,
            "url": url,
            "bot_url": url,
            "update_interval": QR_UPDATE_INTERVAL * 1000,
            "user_info": user_info
        }


@app.get(
    "/api/active_token",
    response_model=TokenResponse,
    responses={
        200: {"description": "Success", "model": TokenResponse},
        401: {"description": "Unauthorized - требуется аутентификация", "model": ErrorResponse},
        429: {"description": "Rate limit exceeded - превышен лимит запросов (10/мин)", "model": ErrorResponse}
    },
    tags=["tokens"],
    summary="Получить активный токен для отметки",
    description="""
    Возвращает текущий активный токен для отметки посещаемости через Telegram бота.
    
    **Аутентификация:** Требуется (API key или JWT token)
    
    **Rate Limit:** 10 запросов в минуту
    
    **Пример использования:**
    ```bash
    curl -H "Authorization: Bearer <token>" https://api.example.com/api/active_token
    ```
    """
)
async def get_active_token(request: Request, db: Database = Depends(get_db)):
    """Get active token for attendance"""
    # Rate limiting
    rate_limit(request, max_requests=10, window_seconds=60, key_prefix="api_token")
    # Авторизация: API key или авторизованная сессия
    # Терминал теперь требует авторизацию, поэтому убираем allow_terminal_session
    authorize_request(request, allow_terminal_session=False)

    token_data = db.get_active_token()
    token = token_data['token'] if token_data else db.create_token()
    url = f"https://t.me/{BOT_USERNAME}?start={token}"
    return {"token": token, "url": url, "bot_url": url}

@app.get("/api/token")
async def get_token_for_device(request: Request, db: Database = Depends(get_db)):
    """Get active token for microcontroller/device (simplified endpoint)
    
    This endpoint is designed for microcontrollers (ESP32, Arduino, etc.)
    that need to get the current token and generate QR code locally.
    
    Authentication: Optional API key via X-API-Key header (if API_KEY is configured)
    If no API_KEY is set, this endpoint is publicly accessible (read-only).
    
    Returns:
        {
            "token": "current_token_string",
            "url": "https://t.me/bot_username?start=token",
            "bot_username": "bot_username"
        }
    """
    # Optional API key check (if configured)
    if API_KEY:
        header_key = request.headers.get("X-API-Key")
        if header_key != API_KEY:
            raise HTTPException(status_code=401, detail="Invalid API key")
    
    token_data = db.get_active_token()
    token = token_data['token'] if token_data else db.create_token()
    url = f"https://t.me/{BOT_USERNAME}?start={token}"
    
    # Include token creation timestamp for change detection
    if token_data:
        created_at = token_data.get('created_at', '')
    else:
        # If we just created a token, get it again to include timestamp
        token_data = db.get_active_token()
        created_at = token_data.get('created_at', '') if token_data else ''
    
    return {
        "token": token,
        "url": url,
        "bot_username": BOT_USERNAME,
        "created_at": created_at  # ISO format timestamp for change detection
    }

# Web terminal routes
@app.get("/", response_class=HTMLResponse)
async def home(request: Request, db: Database = Depends(get_db)):
    """Главная: терминал с QR-кодом (требует авторизацию с ролью terminal)"""
    # Проверяем авторизацию
    if not request.session.get("authenticated"):
        return RedirectResponse(url="/login?next=/", status_code=302)
    
    # Проверяем роль - только terminal может видеть QR-код
    user_role = request.session.get("user_role")
    if user_role != "terminal":
        # Если не terminal, редиректим на админку или страницу доступа
        if user_role in ["admin", "manager", "hr"]:
            return RedirectResponse(url="/admin", status_code=302)
        else:
            return RedirectResponse(url="/me", status_code=302)
    
    context = build_terminal_context(request, db)
    return templates.TemplateResponse("terminal.html", context)

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Страница входа с поддержкой редиректа после логина"""
    next_url = request.query_params.get("next", "/terminal")
    # Генерируем CSRF токен для формы логина
    csrf_token = set_csrf_token(request)
    return templates.TemplateResponse("login.html", {
        "request": request,
        "next_url": next_url,
        "csrf_token": csrf_token
    })

@app.post("/login")
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Database = Depends(get_db),
    next_url: str = Form("/terminal"),
    csrf_token: str = Form(None)
):
    # Проверка CSRF токена
    await require_csrf_token(request)
    
    # Валидация входных данных
    username = sanitize_string(username, max_length=50)
    is_valid, error_msg = validate_username(username)
    if not is_valid:
        csrf_token = get_csrf_token(request) or set_csrf_token(request)
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": error_msg, "next_url": next_url, "csrf_token": csrf_token}
        )
    
    is_valid, error_msg = validate_password(password, min_length=6, require_complexity=False)
    if not is_valid:
        csrf_token = get_csrf_token(request) or set_csrf_token(request)
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": error_msg, "next_url": next_url, "csrf_token": csrf_token}
        )
    
    # Rate limit by client IP
    client_ip = request.client.host if request.client else "unknown"
    now = time.time()

    # Redis-based limiter (fallback to memory)
    try:
        if cache.redis_client:
            key_block = f"login:block:{client_ip}"
            key_counter = f"login:count:{client_ip}"

            if cache.redis_client.exists(key_block):
                return templates.TemplateResponse(
                    "login.html",
                    {
                        "request": request,
                        "error": "Слишком много попыток. Попробуйте позже.",
                        "next_url": next_url
                    }
                )

            count = cache.redis_client.incr(key_counter)
            if count == 1:
                cache.redis_client.expire(key_counter, LOGIN_WINDOW_SEC)
            if count > MAX_LOGIN_ATTEMPTS:
                cache.redis_client.set(key_block, 1, ex=LOGIN_BLOCK_SEC)
                log_rate_limit_exceeded("/login", client_ip, attempts=count)
                return templates.TemplateResponse(
                    "login.html",
                    {
                        "request": request,
                        "error": "Слишком много попыток. Попробуйте позже.",
                        "next_url": next_url
                    }
                )
        else:
            # Use get() to avoid KeyError if key doesn't exist
            attempts = LOGIN_ATTEMPTS.get(client_ip, [])
            LOGIN_ATTEMPTS[client_ip] = [t for t in attempts if now - t < LOGIN_WINDOW_SEC]
            if len(LOGIN_ATTEMPTS.get(client_ip, [])) >= MAX_LOGIN_ATTEMPTS:
                log_rate_limit_exceeded("/login", client_ip, attempts=len(LOGIN_ATTEMPTS.get(client_ip, [])))
                return templates.TemplateResponse(
                    "login.html",
                    {
                        "request": request,
                        "error": "Слишком много попыток. Попробуйте позже.",
                        "next_url": next_url
                    }
                )
    except Exception as e:
        # Log rate limiting errors but don't block login
        log_error(e, "Rate limiting")

    # Попытка логина через API
    try:
        user = db.get_web_user_by_username(username)
        if user and JWTHandler.verify_password(password, user["password_hash"]):
            # Сброс счетчика попыток при успехе
            try:
                if cache.redis_client:
                    cache.redis_client.delete(f"login:count:{client_ip}")
                    cache.redis_client.delete(f"login:block:{client_ip}")
                else:
                    LOGIN_ATTEMPTS.pop(client_ip, None)
            except Exception as e:
                log_error(e, "Reset login attempts counter")
            # Генерируем JWT токен
            # Для роли terminal делаем очень долгую сессию (1 год) для работы 24/7
            user_role = user.get("role", "user")
            if user_role == "terminal":
                # Для терминала - сессия на 1 год (525600 минут)
                expires_delta = timedelta(days=365)
            else:
                # Для остальных ролей - стандартное время (30 минут)
                expires_delta = None
            
            access_token = JWTHandler.create_access_token(
                data={"sub": username, "role": user_role},
                expires_delta=expires_delta
            )
            # Сохраняем токен в сессии
            request.session["access_token"] = access_token
            request.session["authenticated"] = True
            request.session["user_role"] = user.get("role", "user")
            # Генерируем новый CSRF токен после успешного логина
            set_csrf_token(request)
            # Логируем успешный вход
            log_successful_login(username, client_ip, role=user_role)

            # Редирект на запрошенную страницу или по умолчанию
            # Админы могут попасть в админку, но по умолчанию все идут на терминал
            redirect_to = next_url if next_url and next_url.startswith("/") else "/terminal"
            return RedirectResponse(url=redirect_to, status_code=302)
        else:
            # Initialize list if key doesn't exist (defaultdict handles this, but being explicit)
            if client_ip not in LOGIN_ATTEMPTS:
                LOGIN_ATTEMPTS[client_ip] = []
            LOGIN_ATTEMPTS[client_ip].append(now)
            # Логируем неудачную попытку входа
            log_failed_login(username, client_ip, reason="Invalid credentials")
            return templates.TemplateResponse(
                "login.html",
                {"request": request, "error": "Invalid credentials", "next_url": next_url}
            )
    except Exception as e:
        log_error(e, "Login")
        # Initialize list if key doesn't exist (defaultdict handles this, but being explicit)
        if client_ip not in LOGIN_ATTEMPTS:
            LOGIN_ATTEMPTS[client_ip] = []
        LOGIN_ATTEMPTS[client_ip].append(now)
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Login failed", "next_url": next_url}
        )

@app.get("/terminal", response_class=HTMLResponse)
async def terminal_page(request: Request, db: Database = Depends(get_db)):
    """Терминал с QR-кодом (требует авторизацию с ролью terminal)"""
    # Проверяем авторизацию
    if not request.session.get("authenticated"):
        return RedirectResponse(url="/login?next=/terminal", status_code=302)
    
    # Проверяем роль - только terminal может видеть QR-код
    user_role = request.session.get("user_role")
    if user_role != "terminal":
        # Если не terminal, редиректим на админку или страницу доступа
        if user_role in ["admin", "manager", "hr"]:
            return RedirectResponse(url="/admin", status_code=302)
        else:
            return RedirectResponse(url="/me", status_code=302)
    
    context = build_terminal_context(request, db)
    return templates.TemplateResponse("terminal.html", context)

@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=302)

# Admin routes for reporting
@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request, db: Database = Depends(get_db)):
    if not request.session.get("authenticated"):
        return RedirectResponse(url="/login", status_code=302)

    user_role = request.session.get("user_role", "user")

    # Get currently present users
    present_users = db.get_currently_present()

    initial_creds = None
    if user_role in ["admin", "manager", "hr"]:
        initial_creds = db.consume_initial_credentials()

    return templates.TemplateResponse(
        "admin.html",
        {
            "request": request,
            "present_users": present_users,
            "initial_creds": initial_creds
        }
    )

@app.get("/admin/user/{user_id}", response_class=HTMLResponse)
async def user_history(request: Request, user_id: int, db: Database = Depends(get_db)):
    if not request.session.get("authenticated"):
        return RedirectResponse(url="/login", status_code=302)

    # Get user info
    user = db.get_person_by_tg_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Get user events
    events = db.get_user_events(user_id, limit=100)

    return templates.TemplateResponse(
        "user_history.html",
        {
            "request": request,
            "user": user,
            "events": events
        }
    )

@app.get("/me", response_class=HTMLResponse)
async def self_dashboard(request: Request, db: Database = Depends(get_db)):
    """Personal dashboard for authenticated users (role user and above)"""
    token = request.session.get("access_token")
    if not token:
        return RedirectResponse(url="/login", status_code=302)

    try:
        payload = JWTHandler.verify_token(token)
        username = payload.get("sub")
        role = payload.get("role", "user")

        # derive tg_user_id from username pattern user<tgid>
        tg_user_id = None
        if username and username.startswith("user"):
            suffix = username[4:]
            if suffix.isdigit():
                tg_user_id = int(suffix)

        if tg_user_id is None:
            return RedirectResponse(url="/login", status_code=302)

        person = db.get_person_by_tg_id(tg_user_id)
        stats = db.get_employee_stats_by_tg(tg_user_id)

        if not person or not stats:
            return templates.TemplateResponse(
                "self_dashboard.html",
                {
                    "request": request,
                    "error": "Профиль не найден. Отсканируйте QR через бота, чтобы зарегистрироваться."
                }
            )

        return templates.TemplateResponse(
            "self_dashboard.html",
            {
                "request": request,
                "person": person,
                "stats": stats,
                "role": role
            }
        )
    except Exception as e:
        log_error(e, "Self dashboard")
        request.session.clear()
        return RedirectResponse(url="/login", status_code=302)

# Analytics and user management pages
@app.get("/analytics", response_class=HTMLResponse)
async def analytics_dashboard(request: Request):
    """Analytics dashboard page"""
    token = request.session.get("access_token")
    if not token:
        return RedirectResponse(url="/login", status_code=302)

    try:
        payload = JWTHandler.verify_token(token)
        user_role = payload.get("role", "user")

        # Проверяем права доступа
        if user_role not in ["admin", "manager", "hr"]:
            return RedirectResponse(url="/terminal", status_code=302)

        # Get analytics data
        analytics_summary = db.get_analytics_summary()
        daily_visits = db.get_daily_visits_chart()
        hourly_distribution = db.get_hourly_distribution()
        top_workers = db.get_top_workers()
        department_stats = db.get_department_stats()

        # Get employee list for selection
        employee_list = db.get_employee_list()

        return templates.TemplateResponse(
            "analytics.html",
            {
                "request": request,
                "analytics_summary": analytics_summary,
                "daily_visits": daily_visits,
                "hourly_distribution": hourly_distribution,
                "top_workers": top_workers,
                "department_stats": department_stats,
                "employee_list": employee_list
            }
        )
    except Exception as e:
        log_error(e, "Analytics page token validation")
        request.session.clear()
        return RedirectResponse(url="/login", status_code=302)

@app.get("/users", response_class=HTMLResponse)
async def user_management(request: Request, db: Database = Depends(get_db)):
    """User management page"""
    token = request.session.get("access_token")
    if not token:
        return RedirectResponse(url="/login", status_code=302)

    # Генерируем CSRF токен для форм на странице
    csrf_token = set_csrf_token(request)

    try:
        payload = JWTHandler.verify_token(token)
        user_role = payload.get("role", "user")

        # Проверяем права доступа (только админ и менеджер)
        if user_role not in ["admin", "manager"]:
            client_ip = request.client.host if request.client else "unknown"
            username = payload.get("sub")
            log_unauthorized_access("/users", user=username, ip_address=client_ip, reason=f"Role '{user_role}' not allowed")
            return RedirectResponse(url="/terminal", status_code=302)

        # Получаем данные для шаблона
        users = db.get_all_web_users()
        roles = db.get_all_roles()

        return templates.TemplateResponse(
            "user_management.html",
            {
                "request": request,
                "users": users,
                "roles": roles,
                "current_user_role": user_role,
                "csrf_token": csrf_token
            }
        )
    except Exception as e:
        log_error(e, "User management page")
        request.session.clear()
        return RedirectResponse(url="/login", status_code=302)

# API endpoints for user management
@app.get(
    "/api/user/{user_id}",
    response_model=UserResponse,
    responses={
        200: {"description": "Success", "model": UserResponse},
        401: {"description": "Unauthorized", "model": ErrorResponse},
        403: {"description": "Forbidden - требуется роль admin или manager", "model": ErrorResponse},
        404: {"description": "User not found", "model": ErrorResponse},
        429: {"description": "Rate limit exceeded", "model": ErrorResponse}
    },
    tags=["users"],
    summary="Получить пользователя по ID",
    description="""
    Возвращает информацию о пользователе по его ID.
    
    **Требования:**
    - Аутентификация: обязательна
    - Роль: admin или manager
    - Rate Limit: 20 запросов/минуту
    
    **Пример:**
    ```bash
    curl -H "Authorization: Bearer <token>" https://api.example.com/api/user/1
    ```
    """
)
async def get_user(request: Request, user_id: int, db: Database = Depends(get_db)):
    """Get user by ID"""
    rate_limit(request, max_requests=20, window_seconds=60, key_prefix="user_mgmt")
    authorize_request(request, require_roles=["admin", "manager"])
    
    user = db.get_web_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Remove password hash from response
    user.pop('password_hash', None)
    return user

@app.put(
    "/api/user/{user_id}",
    response_model=UserResponse,
    responses={
        200: {"description": "Success", "model": UserResponse},
        400: {"description": "Bad Request - ошибка валидации данных", "model": ErrorResponse},
        401: {"description": "Unauthorized", "model": ErrorResponse},
        403: {"description": "Forbidden - требуется роль admin/manager или неверный CSRF токен", "model": ErrorResponse},
        404: {"description": "User not found", "model": ErrorResponse},
        429: {"description": "Rate limit exceeded - превышен лимит (10/мин)", "model": ErrorResponse}
    },
    tags=["users"],
    summary="Обновить пользователя",
    description="""
    Обновляет информацию о пользователе.
    
    **Требования:**
    - Аутентификация: обязательна
    - Роль: admin или manager
    - CSRF токен: обязателен (заголовок `X-CSRF-Token`)
    - Rate Limit: 10 запросов/минуту
    
    **Валидация:**
    - `full_name`: 3-200 символов, только буквы, пробелы, дефисы
    - `role`: один из: user, admin, manager, hr, terminal
    - `password`: минимум 8 символов, должен содержать буквы и цифры
    - `department`, `position`: максимум 100 символов
    
    **Пример запроса:**
    ```json
    {
        "full_name": "Иванов Иван Иванович",
        "role": "user",
        "department": "IT",
        "is_active": true
    }
    ```
    
    **Пример curl:**
    ```bash
    curl -X PUT https://api.example.com/api/user/1 \\
      -H "Authorization: Bearer <token>" \\
      -H "X-CSRF-Token: <csrf_token>" \\
      -H "Content-Type: application/json" \\
      -d '{"full_name": "New Name", "role": "user"}'
    ```
    """
)
async def update_user(
    request: Request,
    user_id: int,
    db: Database = Depends(get_db)
):
    """Update user"""
    rate_limit(request, max_requests=10, window_seconds=60, key_prefix="user_mgmt")
    # Проверка CSRF токена
    await require_csrf_token(request)
    # Authorize and get payload once
    payload = authorize_request(request, require_roles=["admin", "manager"])
    
    # Get current user ID for audit
    current_username = payload.get("sub")
    current_user = db.get_web_user_by_username(current_username) if current_username else None
    updated_by = current_user.get("id") if current_user else None
    
    # Check if user exists
    user = db.get_web_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Parse JSON body
    try:
        body = await request.json()
        # For JSON requests, CSRF token should be in header (already checked by require_csrf_token)
    except:
        # Fallback to form data
        form = await request.form()
        body = dict(form)
        # For form data, CSRF token should be checked by require_csrf_token above
        # But we also check it here for form submissions
        form_csrf_token = body.get("csrf_token")
        if form_csrf_token:
            # Validate form CSRF token
            from utils.csrf import validate_csrf_token
            if not validate_csrf_token(request, form_csrf_token):
                raise HTTPException(status_code=403, detail="Invalid CSRF token")
        # Convert is_active string to boolean
        if 'is_active' in body:
            body['is_active'] = body['is_active'].lower() in ('true', '1', 'yes', 'on')
    
    # Extract fields (only update provided fields)
    full_name = body.get('full_name')
    role = body.get('role')
    department = body.get('department')
    position = body.get('position')
    is_active = body.get('is_active')
    password = body.get('password')
    
    # Валидация полей
    if full_name is not None:
        full_name = sanitize_string(str(full_name), max_length=200)
        is_valid, error_msg = validate_fio(full_name)
        if not is_valid:
            raise HTTPException(status_code=400, detail=f"Ошибка валидации ФИО: {error_msg}")
    
    if role is not None:
        is_valid, error_msg = validate_role(str(role))
        if not is_valid:
            raise HTTPException(status_code=400, detail=f"Ошибка валидации роли: {error_msg}")
        # Логируем изменение роли
        old_role = user.get("role")
        if old_role != role:
            client_ip = request.client.host if request.client else "unknown"
            log_role_change(current_username or "unknown", user.get("username", f"user_{user_id}"), old_role, role, client_ip)
    
    if department is not None:
        department = sanitize_string(str(department), max_length=100)
        is_valid, error_msg = validate_department(department)
        if not is_valid:
            raise HTTPException(status_code=400, detail=f"Ошибка валидации отдела: {error_msg}")
    
    if position is not None:
        position = sanitize_string(str(position), max_length=100)
        is_valid, error_msg = validate_position(position)
        if not is_valid:
            raise HTTPException(status_code=400, detail=f"Ошибка валидации должности: {error_msg}")
    
    # Remove empty password
    if password and password.strip() == '':
        password = None
    elif password:
        is_valid, error_msg = validate_password(password, min_length=8, require_complexity=True)
        if not is_valid:
            raise HTTPException(status_code=400, detail=f"Ошибка валидации пароля: {error_msg}")
    
    # Update user
    success = db.update_web_user(
        user_id=user_id,
        full_name=full_name,
        role=role,
        department=department,
        position=position,
        is_active=is_active,
        password=password,
        updated_by=updated_by
    )
    
    if not success:
        raise HTTPException(status_code=400, detail="Failed to update user")
    
    # Return updated user
    updated_user = db.get_web_user_by_id(user_id)
    updated_user.pop('password_hash', None)
    return updated_user

@app.get(
    "/api/employee/{employee_id}",
    responses={
        200: {"description": "Success"},
        401: {"description": "Unauthorized", "model": ErrorResponse},
        403: {"description": "Forbidden", "model": ErrorResponse},
        404: {"description": "Employee not found", "model": ErrorResponse}
    },
    tags=["analytics"],
    summary="Статистика по сотруднику",
    description="""
    Возвращает детальную статистику для конкретного сотрудника.
    
    **Параметры:**
    - `employee_id`: ID сотрудника (Telegram user ID)
    
    **Требования:**
    - Аутентификация: обязательна
    - Роль: admin, manager или hr
    
    **Пример:**
    ```bash
    curl -H "Authorization: Bearer <token>" \\
      https://api.example.com/api/employee/123456
    ```
    """
)
async def get_employee_stats(employee_id: int, db: Database = Depends(get_db)):
    """Get detailed statistics for a specific employee"""
    stats = db.get_employee_detailed_stats(employee_id)
    if not stats:
        raise HTTPException(status_code=404, detail="Employee not found")

    return stats

@app.get("/api/employees/date/{date}")
async def get_employees_by_date(request: Request, date: str, db: Database = Depends(get_db)):
    """Get list of employees who visited on a specific date (YYYY-MM-DD)"""
    rate_limit(request, max_requests=30, window_seconds=60, key_prefix="api_analytics")
    authorize_request(request, require_roles=["admin", "manager", "hr"])
    
    try:
        # Validate date format
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    
    employees = db.get_employees_by_date(date)
    return {
        "date": date,
        "employees": employees,
        "total": len(employees)
    }

@app.get(
    "/api/analytics/daily/{date}",
    responses={
        200: {"description": "Success"},
        400: {"description": "Bad Request - неверный формат даты", "model": ErrorResponse},
        401: {"description": "Unauthorized", "model": ErrorResponse},
        403: {"description": "Forbidden", "model": ErrorResponse},
        429: {"description": "Rate limit exceeded", "model": ErrorResponse}
    },
    tags=["analytics"],
    summary="Дневная аналитика",
    description="""
    Возвращает статистику посещаемости за указанную дату.
    
    **Параметры:**
    - `date`: Дата в формате YYYY-MM-DD
    
    **Требования:**
    - Аутентификация: обязательна
    - Роль: admin, manager или hr
    - Rate Limit: 30 запросов/минуту
    
    **Пример:**
    ```bash
    curl -H "Authorization: Bearer <token>" \\
      https://api.example.com/api/analytics/daily/2024-01-15
    ```
    """
)
async def analytics_daily(request: Request, date: str, db: Database = Depends(get_db)):
    """Daily analytics by date (YYYY-MM-DD)"""
    rate_limit(request, max_requests=30, window_seconds=60, key_prefix="api_analytics")
    authorize_request(request, require_roles=["admin", "manager", "hr"])
    stats = db.get_daily_stats(date)
    return {"date": date, **stats}

@app.get(
    "/api/analytics/weekly",
    responses={
        200: {"description": "Success"},
        401: {"description": "Unauthorized", "model": ErrorResponse},
        403: {"description": "Forbidden", "model": ErrorResponse},
        429: {"description": "Rate limit exceeded", "model": ErrorResponse}
    },
    tags=["analytics"],
    summary="Недельная аналитика",
    description="""
    Возвращает статистику посещаемости за последние 7 дней.
    
    **Требования:**
    - Аутентификация: обязательна
    - Роль: admin, manager или hr
    - Rate Limit: 30 запросов/минуту
    """
)
async def analytics_weekly(request: Request, db: Database = Depends(get_db)):
    """Weekly analytics for last 7 days"""
    rate_limit(request, max_requests=30, window_seconds=60, key_prefix="api_analytics")
    authorize_request(request, require_roles=["admin", "manager", "hr"])
    today = datetime.utcnow().date()
    start_date = (today - timedelta(days=6)).isoformat()
    end_date = today.isoformat()
    data = db.get_weekly_stats(start_date, end_date)
    return {
        "period": {"start": start_date, "end": end_date},
        "data": data,
        "daily_stats": data
    }

@app.get(
    "/api/analytics/locations",
    responses={
        200: {"description": "Success"},
        401: {"description": "Unauthorized", "model": ErrorResponse},
        403: {"description": "Forbidden", "model": ErrorResponse},
        429: {"description": "Rate limit exceeded", "model": ErrorResponse}
    },
    tags=["analytics"],
    summary="Аналитика по локациям",
    description="""
    Возвращает статистику по локациям (в текущей реализации все события глобальные).
    
    **Требования:**
    - Аутентификация: обязательна
    - Роль: admin, manager или hr
    - Rate Limit: 30 запросов/минуту
    """
)
async def analytics_locations(request: Request, db: Database = Depends(get_db)):
    """Analytics by locations (global in current implementation)"""
    rate_limit(request, max_requests=30, window_seconds=60, key_prefix="api_analytics")
    authorize_request(request, require_roles=["admin", "manager", "hr"])
    data = db.get_location_stats()
    return {"locations": data}

@app.get(
    "/api/analytics/users",
    responses={
        200: {"description": "Success"},
        401: {"description": "Unauthorized", "model": ErrorResponse},
        403: {"description": "Forbidden", "model": ErrorResponse},
        429: {"description": "Rate limit exceeded", "model": ErrorResponse}
    },
    tags=["analytics"],
    summary="Самые активные пользователи",
    description="""
    Возвращает список самых активных пользователей.
    
    **Параметры:**
    - `limit`: Количество пользователей (по умолчанию 10)
    
    **Требования:**
    - Аутентификация: обязательна
    - Роль: admin, manager или hr
    - Rate Limit: 30 запросов/минуту
    
    **Пример:**
    ```bash
    curl -H "Authorization: Bearer <token>" \\
      "https://api.example.com/api/analytics/users?limit=20"
    ```
    """
)
async def analytics_users(request: Request, limit: int = 10, db: Database = Depends(get_db)):
    """Most active users"""
    rate_limit(request, max_requests=30, window_seconds=60, key_prefix="api_analytics")
    authorize_request(request, require_roles=["admin", "manager", "hr"])
    data = db.get_user_stats(limit)
    return {"users": data}

@app.get(
    "/api/analytics/hourly/{date}",
    responses={
        200: {"description": "Success"},
        400: {"description": "Bad Request - неверный формат даты", "model": ErrorResponse},
        401: {"description": "Unauthorized", "model": ErrorResponse},
        403: {"description": "Forbidden", "model": ErrorResponse},
        429: {"description": "Rate limit exceeded", "model": ErrorResponse}
    },
    tags=["analytics"],
    summary="Почасовая аналитика",
    description="""
    Возвращает распределение посещаемости по часам за указанную дату.
    
    **Параметры:**
    - `date`: Дата в формате YYYY-MM-DD
    
    **Требования:**
    - Аутентификация: обязательна
    - Роль: admin, manager или hr
    - Rate Limit: 30 запросов/минуту
    
    **Пример:**
    ```bash
    curl -H "Authorization: Bearer <token>" \\
      https://api.example.com/api/analytics/hourly/2024-01-15
    ```
    """
)
async def analytics_hourly(request: Request, date: str, db: Database = Depends(get_db)):
    """Hourly analytics for a date (YYYY-MM-DD)"""
    rate_limit(request, max_requests=30, window_seconds=60, key_prefix="api_analytics")
    authorize_request(request, require_roles=["admin", "manager", "hr"])
    data = db.get_hourly_stats(date)
    return {"date": date, "hourly": data, "hourly_stats": data}

@app.get(
    "/api/health",
    response_model=HealthCheckResponse,
    responses={
        200: {"description": "System is healthy", "model": HealthCheckResponse},
        503: {"description": "System is degraded - некоторые сервисы недоступны", "model": HealthCheckResponse}
    },
    tags=["health"],
    summary="Проверка здоровья системы",
    description="""
    Проверяет состояние системы и всех зависимостей.
    
    **Проверяет:**
    - База данных (подключение, размер)
    - Redis (если включен)
    - Системные метрики (CPU, память, диск) - опционально
    
    **Статусы:**
    - `healthy` (200) - все сервисы работают
    - `degraded` (503) - некоторые сервисы недоступны
    
    **Использование:**
    - Docker health checks
    - Мониторинг систем
    - Load balancer health checks
    """
)
async def health_check(db: Database = Depends(get_db)):
    """Enhanced health check endpoint with detailed system information"""
    from utils.metrics import get_system_metrics, get_redis_metrics, get_database_metrics
    
    health_status = {
        "status": "healthy",
        "version": "1.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "checks": {}
    }
    
    overall_healthy = True
    
    # Database check
    try:
        db_metrics = get_database_metrics(db)
        health_status["checks"]["database"] = db_metrics
        if db_metrics.get("status") != "healthy":
            overall_healthy = False
    except Exception as e:
        health_status["checks"]["database"] = {"status": "error", "error": str(e)}
        overall_healthy = False
    
    # Redis check
    try:
        redis_metrics = get_redis_metrics()
        health_status["checks"]["redis"] = redis_metrics
        if cache.redis_enabled and not redis_metrics.get("connected"):
            overall_healthy = False
    except Exception as e:
        health_status["checks"]["redis"] = {"status": "error", "error": str(e)}
        if cache.redis_enabled:
            overall_healthy = False
    
    # System metrics (optional, don't fail if unavailable)
    try:
        system_metrics = get_system_metrics()
        if "error" not in system_metrics:
            health_status["system"] = system_metrics
    except:
        pass  # System metrics are optional
    
    if not overall_healthy:
        health_status["status"] = "degraded"
    
    status_code = 200 if overall_healthy else 503
    return Response(
        content=json.dumps(health_status, indent=2),
        media_type="application/json",
        status_code=status_code
    )

@app.get(
    "/api/metrics",
    response_model=MetricsResponse,
    responses={
        200: {"description": "Success", "model": MetricsResponse},
        401: {"description": "Unauthorized", "model": ErrorResponse}
    },
    tags=["health"],
    summary="Получить метрики производительности",
    description="""
    Возвращает детальные метрики производительности системы.
    
    **Включает:**
    - Метрики базы данных (статус, размер)
    - Метрики Redis (подключение, использование памяти)
    - Системные метрики (CPU, память, диск)
    - Статистика приложения (пользователи, события, токены)
    
    **Использование:**
    - Интеграция с Prometheus/Grafana
    - Мониторинг производительности
    - Анализ использования ресурсов
    
    **Пример:**
    ```bash
    curl -H "Authorization: Bearer <token>" https://api.example.com/api/metrics
    ```
    """
)
async def get_metrics(db: Database = Depends(get_db)):
    """Get detailed performance metrics (for monitoring systems)"""
    from utils.metrics import get_system_metrics, get_redis_metrics, get_database_metrics
    
    metrics = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "database": get_database_metrics(db),
        "redis": get_redis_metrics(),
        "system": get_system_metrics()
    }
    
    # Add system health stats if available
    try:
        health_stats = db.get_system_health_stats()
        metrics["application"] = health_stats
    except:
        pass
    
    return metrics

@app.get("/robots.txt", response_class=PlainTextResponse)
async def robots():
    return "User-agent: *\nDisallow:\n"

@app.get("/favicon.ico")
async def favicon():
    return Response(status_code=204)

if __name__ == "__main__":
    uvicorn.run(app, host=API_HOST, port=API_PORT)
