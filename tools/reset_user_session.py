#!/usr/bin/env python3
"""
Скрипт для сброса активной сессии пользователя в боте
Использование: python reset_user_session.py <telegram_user_id>
              python reset_user_session.py --list  # показать всех с активными сессиями
              python reset_user_session.py --all    # закрыть все активные сессии
"""
import sys
import os
from datetime import datetime, timezone

# Добавляем путь проекта
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from database import Database
from config import DB_PATH

def list_active_sessions(db: Database):
    """Показать всех пользователей с активными сессиями"""
    active_sessions = db.get_currently_present()
    
    if not active_sessions:
        print("✅ Нет активных сессий")
        return
    
    print(f"\n📋 Найдено активных сессий: {len(active_sessions)}\n")
    print(f"{'ID':<10} {'Telegram ID':<15} {'ФИО':<30} {'Локация':<15} {'Время прихода':<20}")
    print("-" * 100)
    
    for session in active_sessions:
        tg_user_id = session.get('user_id') or session.get('tg_user_id')
        fio = session.get('fio', 'N/A')
        location = session.get('location', 'global')
        ts = session.get('ts', '')
        
        # Форматируем время
        try:
            if 'T' in ts:
                dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
            else:
                dt = datetime.strptime(ts[:19], '%Y-%m-%d %H:%M:%S')
                dt = dt.replace(tzinfo=timezone.utc)
            time_str = dt.strftime('%Y-%m-%d %H:%M:%S')
        except:
            time_str = ts[:19] if ts else 'N/A'
        
        location_display = "Удалёнка" if location == "remote" else ("Офис" if location == "global" else location)
        
        print(f"{session.get('id', 'N/A'):<10} {tg_user_id:<15} {fio:<30} {location_display:<15} {time_str:<20}")

def close_user_session(db: Database, tg_user_id: int):
    """Закрыть активную сессию пользователя"""
    # Проверяем, есть ли у пользователя активная сессия
    active_sessions = db.get_currently_present()
    user_session = None
    
    for session in active_sessions:
        session_tg_id = session.get('user_id') or session.get('tg_user_id')
        if session_tg_id == tg_user_id:
            user_session = session
            break
    
    if not user_session:
        print(f"❌ У пользователя {tg_user_id} нет активной сессии")
        return False
    
    # Получаем информацию о пользователе
    person = db.get_person_by_tg_id(tg_user_id)
    if not person:
        print(f"❌ Пользователь {tg_user_id} не найден в базе данных")
        return False
    
    # Получаем локацию из последнего события
    location = user_session.get('location', 'global')
    
    # Создаем событие "out" для закрытия сессии
    try:
        db.create_event(
            user_id=tg_user_id,
            location=location,
            action="out",
            username=person.get('username'),
            full_name=person.get('fio')
        )
        
        print(f"✅ Сессия пользователя {tg_user_id} ({person.get('fio', 'N/A')}) успешно закрыта")
        print(f"   Локация: {'Удалёнка' if location == 'remote' else ('Офис' if location == 'global' else location)}")
        return True
    except Exception as e:
        print(f"❌ Ошибка при закрытии сессии: {e}")
        import traceback
        traceback.print_exc()
        return False

def close_all_sessions(db: Database):
    """Закрыть все активные сессии"""
    active_sessions = db.get_currently_present()
    
    if not active_sessions:
        print("✅ Нет активных сессий для закрытия")
        return
    
    print(f"\n🔄 Закрытие {len(active_sessions)} активных сессий...\n")
    
    success_count = 0
    for session in active_sessions:
        tg_user_id = session.get('user_id') or session.get('tg_user_id')
        if close_user_session(db, tg_user_id):
            success_count += 1
    
    print(f"\n✅ Закрыто сессий: {success_count}/{len(active_sessions)}")

def main():
    if len(sys.argv) < 2:
        print("Использование:")
        print("  python reset_user_session.py <telegram_user_id>  # закрыть сессию пользователя")
        print("  python reset_user_session.py --list              # показать активные сессии")
        print("  python reset_user_session.py --all             # закрыть все активные сессии")
        sys.exit(1)
    
    db = Database(str(DB_PATH))
    
    if sys.argv[1] == "--list":
        list_active_sessions(db)
    elif sys.argv[1] == "--all":
        confirm = input("⚠️  Вы уверены, что хотите закрыть ВСЕ активные сессии? (yes/no): ")
        if confirm.lower() == "yes":
            close_all_sessions(db)
        else:
            print("❌ Операция отменена")
    else:
        try:
            tg_user_id = int(sys.argv[1])
            close_user_session(db, tg_user_id)
        except ValueError:
            print(f"❌ Неверный формат Telegram User ID: {sys.argv[1]}")
            print("   Telegram User ID должен быть числом")
            sys.exit(1)

if __name__ == "__main__":
    main()
