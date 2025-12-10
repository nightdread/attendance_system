from fastapi import FastAPI, HTTPException, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, PlainTextResponse, Response
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
    BOT_USERNAME, WEB_USERNAME, WEB_PASSWORD,
    API_HOST, API_PORT, QR_UPDATE_INTERVAL, SECRET_KEY, API_KEY
)
from database import Database
from auth.jwt_handler import JWTHandler
from utils.logger import log_error, log_request, log_auth_event

app = FastAPI(title="Attendance System API")

# Add session middleware (use project secret)
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

# Simple in-memory login rate limiter (per IP)
LOGIN_ATTEMPTS = defaultdict(list)
MAX_LOGIN_ATTEMPTS = 5
LOGIN_WINDOW_SEC = 300  # 5 minutes


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
        raise HTTPException(status_code=401, detail="Unauthorized")

    payload = JWTHandler.verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Unauthorized")

    role = payload.get("role", "user")
    if require_roles and role not in require_roles:
        raise HTTPException(status_code=403, detail="Forbidden")

    return payload

# Mount static files (disabled - no static files needed)
# app.mount("/static", StaticFiles(directory="../static"), name="static")

# Resolve paths that work both locally and inside Docker
BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = BASE_DIR / "templates"
DB_PATH = BASE_DIR / "attendance.db"

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
            "update_interval": QR_UPDATE_INTERVAL * 1000,
            "user_info": user_info
        }


@app.get("/api/active_token")
async def get_active_token(request: Request, db: Database = Depends(get_db)):
    """Get active token for attendance"""
    # Авторизация: API key или сессия терминала/пользователя
    # allow_terminal_session=True — для публичного терминала с сессионной кукой
    authorize_request(request, allow_terminal_session=True)

    token_data = db.get_active_token()
    token = token_data['token'] if token_data else db.create_token()
    url = f"https://t.me/{BOT_USERNAME}?start={token}"
    return {"token": token, "url": url}

# Web terminal routes
@app.get("/", response_class=HTMLResponse)
async def home(request: Request, db: Database = Depends(get_db)):
    """Главная: публичный терминал с QR-кодом"""
    # Помечаем сессию как разрешённую для публичного терминала (для /api/active_token)
    request.session.setdefault("terminal_allowed", True)
    context = build_terminal_context(request, db)
    return templates.TemplateResponse("terminal.html", context)

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Database = Depends(get_db)
):
    # Rate limit by client IP
    client_ip = request.client.host if request.client else "unknown"
    now = time.time()
    attempts = LOGIN_ATTEMPTS[client_ip]
    LOGIN_ATTEMPTS[client_ip] = [t for t in attempts if now - t < LOGIN_WINDOW_SEC]
    if len(LOGIN_ATTEMPTS[client_ip]) >= MAX_LOGIN_ATTEMPTS:
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "error": "Слишком много попыток. Попробуйте позже."
            }
        )

    # Попытка логина через API
    try:
        user = db.get_web_user_by_username(username)
        if user and JWTHandler.verify_password(password, user["password_hash"]):
            # Сброс счетчика попыток при успехе
            LOGIN_ATTEMPTS.pop(client_ip, None)
            # Генерируем JWT токен
            access_token = JWTHandler.create_access_token(
                data={"sub": username, "role": user.get("role", "user")}
            )
            # Сохраняем токен в сессии
            request.session["access_token"] = access_token
            request.session["authenticated"] = True
            request.session["user_role"] = user.get("role", "user")

            # Админы попадают в админку, остальные - на главную страницу с QR
            if user.get("role") in ["admin", "manager", "hr"]:
                return RedirectResponse(url="/admin", status_code=302)
            else:
                return RedirectResponse(url="/", status_code=302)
        else:
            LOGIN_ATTEMPTS[client_ip].append(now)
            return templates.TemplateResponse(
                "login.html",
                {"request": request, "error": "Invalid credentials"}
            )
    except Exception as e:
        log_error(f"Login error: {e}")
        LOGIN_ATTEMPTS[client_ip].append(now)
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Login failed"}
        )

@app.get("/terminal", response_class=HTMLResponse)
async def terminal_page(request: Request, db: Database = Depends(get_db)):
    """Публичный терминал без авторизации"""
    request.session.setdefault("terminal_allowed", True)
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

    # Get currently present users
    present_users = db.get_currently_present()

    return templates.TemplateResponse(
        "admin.html",
        {
            "request": request,
            "present_users": present_users
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
        log_error(f"Analytics page token validation error: {e}")
        request.session.clear()
        return RedirectResponse(url="/login", status_code=302)

@app.get("/users", response_class=HTMLResponse)
async def user_management(request: Request, db: Database = Depends(get_db)):
    """User management page"""
    token = request.session.get("access_token")
    if not token:
        return RedirectResponse(url="/login", status_code=302)

    try:
        payload = JWTHandler.verify_token(token)
        user_role = payload.get("role", "user")

        # Проверяем права доступа (только админ и менеджер)
        if user_role not in ["admin", "manager"]:
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
                "current_user_role": user_role
            }
        )
    except Exception as e:
        log_error(f"User management page error: {e}")
        request.session.clear()
        return RedirectResponse(url="/login", status_code=302)

@app.get("/api/employee/{employee_id}")
async def get_employee_stats(employee_id: int, db: Database = Depends(get_db)):
    """Get detailed statistics for a specific employee"""
    stats = db.get_employee_detailed_stats(employee_id)
    if not stats:
        raise HTTPException(status_code=404, detail="Employee not found")

    return stats

@app.get("/api/analytics/daily/{date}")
async def analytics_daily(request: Request, date: str, db: Database = Depends(get_db)):
    """Daily analytics by date (YYYY-MM-DD)"""
    authorize_request(request, require_roles=["admin", "manager", "hr"])
    stats = db.get_daily_stats(date)
    return {"date": date, **stats}

@app.get("/api/analytics/weekly")
async def analytics_weekly(request: Request, db: Database = Depends(get_db)):
    """Weekly analytics for last 7 days"""
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

@app.get("/api/analytics/locations")
async def analytics_locations(request: Request, db: Database = Depends(get_db)):
    """Analytics by locations (global in current implementation)"""
    authorize_request(request, require_roles=["admin", "manager", "hr"])
    data = db.get_location_stats()
    return {"locations": data}

@app.get("/api/analytics/users")
async def analytics_users(request: Request, limit: int = 10, db: Database = Depends(get_db)):
    """Most active users"""
    authorize_request(request, require_roles=["admin", "manager", "hr"])
    data = db.get_user_stats(limit)
    return {"users": data}

@app.get("/api/analytics/hourly/{date}")
async def analytics_hourly(request: Request, date: str, db: Database = Depends(get_db)):
    """Hourly analytics for a date (YYYY-MM-DD)"""
    authorize_request(request, require_roles=["admin", "manager", "hr"])
    data = db.get_hourly_stats(date)
    return {"date": date, "hourly": data, "hourly_stats": data}

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "message": "Attendance System is running",
        "version": "1.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

@app.get("/robots.txt", response_class=PlainTextResponse)
async def robots():
    return "User-agent: *\nDisallow:\n"

@app.get("/favicon.ico")
async def favicon():
    return Response(status_code=204)

if __name__ == "__main__":
    uvicorn.run(app, host=API_HOST, port=API_PORT)
