#!/bin/bash
# Скрипт для сброса активной сессии пользователя в боте
# Использование:
#   ./reset_session.sh <telegram_user_id>  # закрыть сессию конкретного пользователя
#   ./reset_session.sh --list              # показать все активные сессии
#   ./reset_session.sh --all               # закрыть все активные сессии

CONTAINER="attendance_system-attendance_bot-1"

if [ -z "$1" ]; then
    echo "Использование:"
    echo "  $0 <telegram_user_id>  # закрыть сессию пользователя"
    echo "  $0 --list              # показать активные сессии"
    echo "  $0 --all               # закрыть все активные сессии"
    exit 1
fi

if [ "$1" = "--list" ]; then
    docker exec "$CONTAINER" python3 -c "
import sys
sys.path.insert(0, '/app')
from database import Database
from config import DB_PATH
from datetime import datetime, timezone

db = Database(str(DB_PATH))
active_sessions = db.get_currently_present()

if not active_sessions:
    print('✅ Нет активных сессий')
else:
    print(f'\n📋 Найдено активных сессий: {len(active_sessions)}\n')
    print(f'{'ID':<10} {'Telegram ID':<15} {'ФИО':<30} {'Локация':<15} {'Время прихода':<20}')
    print('-' * 100)
    
    for session in active_sessions:
        tg_user_id = session.get('user_id') or session.get('tg_user_id')
        fio = session.get('fio', 'N/A')
        location = session.get('location', 'global')
        ts = session.get('ts', '')
        
        try:
            if 'T' in ts:
                dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
            else:
                dt = datetime.strptime(ts[:19], '%Y-%m-%d %H:%M:%S')
                dt = dt.replace(tzinfo=timezone.utc)
            time_str = dt.strftime('%Y-%m-%d %H:%M:%S')
        except:
            time_str = ts[:19] if ts else 'N/A'
        
        location_display = 'Удалёнка' if location == 'remote' else ('Офис' if location == 'global' else location)
        
        print(f'{session.get(\"id\", \"N/A\"):<10} {tg_user_id:<15} {fio:<30} {location_display:<15} {time_str:<20}')
"
elif [ "$1" = "--all" ]; then
    read -p "⚠️  Вы уверены, что хотите закрыть ВСЕ активные сессии? (yes/no): " confirm
    if [ "$confirm" != "yes" ]; then
        echo "❌ Операция отменена"
        exit 0
    fi
    
    docker exec "$CONTAINER" python3 -c "
import sys
sys.path.insert(0, '/app')
from database import Database
from config import DB_PATH

db = Database(str(DB_PATH))
active_sessions = db.get_currently_present()

if not active_sessions:
    print('✅ Нет активных сессий для закрытия')
else:
    print(f'\n🔄 Закрытие {len(active_sessions)} активных сессий...\n')
    
    success_count = 0
    for session in active_sessions:
        tg_user_id = session.get('user_id') or session.get('tg_user_id')
        
        # Получаем информацию о пользователе
        person = db.get_person_by_tg_id(tg_user_id)
        if not person:
            print(f'❌ Пользователь {tg_user_id} не найден')
            continue
        
        # Получаем локацию из последнего события
        location = session.get('location', 'global')
        
        # Создаем событие \"out\" для закрытия сессии
        try:
            db.create_event(
                user_id=tg_user_id,
                location=location,
                action='out',
                username=person.get('username'),
                full_name=person.get('fio')
            )
            
            print(f'✅ {person.get(\"fio\", \"N/A\")} ({tg_user_id})')
            success_count += 1
        except Exception as e:
            print(f'❌ Ошибка для {tg_user_id}: {e}')
    
    print(f'\n✅ Закрыто сессий: {success_count}/{len(active_sessions)}')
"
else
    TG_USER_ID="$1"
    
    # Проверяем, что это число
    if ! [[ "$TG_USER_ID" =~ ^[0-9]+$ ]]; then
        echo "❌ Неверный формат Telegram User ID: $TG_USER_ID"
        echo "   Telegram User ID должен быть числом"
        exit 1
    fi
    
    docker exec "$CONTAINER" python3 -c "
import sys
sys.path.insert(0, '/app')
from database import Database
from config import DB_PATH

db = Database(str(DB_PATH))
tg_user_id = $TG_USER_ID

# Проверяем активную сессию
active_sessions = db.get_currently_present()
user_session = None

for session in active_sessions:
    session_tg_id = session.get('user_id') or session.get('tg_user_id')
    if session_tg_id == tg_user_id:
        user_session = session
        break

if not user_session:
    print(f'❌ У пользователя {tg_user_id} нет активной сессии')
else:
    # Получаем информацию о пользователе
    person = db.get_person_by_tg_id(tg_user_id)
    if not person:
        print(f'❌ Пользователь {tg_user_id} не найден в базе данных')
    else:
        # Получаем локацию из последнего события
        location = user_session.get('location', 'global')
        
        # Создаем событие \"out\" для закрытия сессии
        try:
            db.create_event(
                user_id=tg_user_id,
                location=location,
                action='out',
                username=person.get('username'),
                full_name=person.get('fio')
            )
            
            print(f'✅ Сессия пользователя {tg_user_id} ({person.get(\"fio\", \"N/A\")}) успешно закрыта')
            print(f'   Локация: {\"Удалёнка\" if location == \"remote\" else (\"Офис\" if location == \"global\" else location)}')
        except Exception as e:
            print(f'❌ Ошибка при закрытии сессии: {e}')
            import traceback
            traceback.print_exc()
"
fi
