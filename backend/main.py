from fastapi import FastAPI, HTTPException, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
import uvicorn
import os

import sys
import os
# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from config import (
    BOT_USERNAME, WEB_USERNAME, WEB_PASSWORD,
    API_HOST, API_PORT, QR_UPDATE_INTERVAL
)
from database import Database
from auth.jwt_handler import JWTHandler
from utils.logger import log_error, log_request, log_auth_event
from auth.middleware import require_authenticated, require_admin, require_permission

app = FastAPI(title="Attendance System API")

# Add session middleware
app.add_middleware(SessionMiddleware, secret_key="your-secret-key-here")

# Mount static files (disabled - no static files needed)
# app.mount("/static", StaticFiles(directory="../static"), name="static")

# Templates
templates = Jinja2Templates(directory="../templates")

# Database instance
db = Database("../attendance.db")

# Dependency to get database
def get_db():
    return db

@app.get("/api/active_token")
async def get_active_token(db: Database = Depends(get_db)):
    """Get active token for attendance"""
    # Get active token or create new one (unified system)
    token_data = db.get_active_token()
    if not token_data:
        token = db.create_token()
    else:
        token = token_data['token']

    url = f"https://t.me/{BOT_USERNAME}?start={token}"

    return {
        "token": token,
        "url": url
    }

# Debug endpoint
@app.get("/debug")
async def debug():
    try:
        db = Database("../attendance.db")
        user = db.get_web_user_by_username("admin")
        return {"user_found": user is not None, "user_data": user}
    except Exception as e:
        return {"error": str(e)}

# Web terminal routes
@app.get("/", response_class=HTMLResponse)
async def home(request: Request, db: Database = Depends(get_db)):
    """Home page - show QR code for attendance marking"""
    # Получаем активный токен для QR-кода
    token_data = db.get_active_token()
    if not token_data:
        token = db.create_token()
    else:
        token = token_data['token']

    url = f"https://t.me/{BOT_USERNAME}?start={token}"

    # Проверяем авторизацию для отображения админских ссылок
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
        pass  # Игнорируем ошибки валидации токена

    return templates.TemplateResponse(
        "terminal.html",
        {
            "request": request,
            "token": token,
            "url": url,
            "update_interval": QR_UPDATE_INTERVAL * 1000,
            "user_info": user_info
        }
    )

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
    # Попытка логина через API
    try:
        user = db.get_web_user_by_username(username)
        if user and JWTHandler.verify_password(password, user["password_hash"]):
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
            return templates.TemplateResponse(
                "login.html",
                {"request": request, "error": "Invalid credentials"}
            )
    except Exception as e:
        log_error(f"Login error: {e}")
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Login failed"}
        )

@app.get("/terminal", response_class=HTMLResponse)
async def terminal_page(request: Request):
    """Terminal page - redirect to home page (QR code is public now)"""
    return RedirectResponse(url="/", status_code=302)

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

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "message": "Attendance System is running",
        "version": "1.1.0",
        "timestamp": "2025-12-09T19:44:00.000000Z"
    }

if __name__ == "__main__":
    uvicorn.run(app, host=API_HOST, port=API_PORT)
