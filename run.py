#!/usr/bin/env python3
"""
Скрипт для запуска системы учета посещаемости
Запускает backend и bot в отдельных процессах
"""
import subprocess
import sys
import os
import signal
import time

def main():
    """Запуск backend и bot"""
    print("🚀 Запуск Attendance System...")
    print("=" * 50)
    
    # Проверка конфигурации
    if not os.path.exists("config/config.py"):
        print("❌ Файл config/config.py не найден!")
        print("   Создайте его из config.example.py:")
        print("   cp config.example.py config/config.py")
        sys.exit(1)
    
    # Проверка зависимостей
    try:
        import fastapi
        import telegram
    except ImportError:
        print("❌ Зависимости не установлены!")
        print("   Установите их: pip install -r requirements.txt")
        sys.exit(1)
    
    processes = []
    
    try:
        # Запуск backend
        print("📡 Запуск Backend (FastAPI)...")
        backend_process = subprocess.Popen(
            [sys.executable, "backend/main.py"],
            cwd=os.path.dirname(os.path.abspath(__file__))
        )
        processes.append(backend_process)
        print(f"   ✅ Backend запущен (PID: {backend_process.pid})")
        print("   🌐 Доступен на http://localhost:8000")
        
        # Небольшая задержка перед запуском бота
        time.sleep(2)
        
        # Запуск bot
        print("🤖 Запуск Telegram Bot...")
        bot_process = subprocess.Popen(
            [sys.executable, "bot/bot.py"],
            cwd=os.path.dirname(os.path.abspath(__file__))
        )
        processes.append(bot_process)
        print(f"   ✅ Bot запущен (PID: {bot_process.pid})")
        
        print("\n" + "=" * 50)
        print("✅ Система запущена!")
        print("\n📋 Компоненты:")
        print("   - Backend: http://localhost:8000")
        print("   - Admin: http://localhost:8000/admin")
        print("   - Login: http://localhost:8000/login")
        print("   - Bot: @qr_uchet_bot")
        print("\n⚠️  Для остановки нажмите Ctrl+C\n")
        
        # Ожидание завершения процессов
        while True:
            time.sleep(1)
            # Проверка, что процессы еще работают
            for proc in processes:
                if proc.poll() is not None:
                    print(f"❌ Процесс {proc.pid} завершился неожиданно")
                    raise KeyboardInterrupt
    
    except KeyboardInterrupt:
        print("\n\n🛑 Остановка системы...")
        for proc in processes:
            try:
                proc.terminate()
                proc.wait(timeout=5)
                print(f"   ✅ Процесс {proc.pid} остановлен")
            except subprocess.TimeoutExpired:
                proc.kill()
                print(f"   ⚠️  Процесс {proc.pid} принудительно завершен")
            except Exception as e:
                print(f"   ❌ Ошибка при остановке процесса {proc.pid}: {e}")
        
        print("✅ Система остановлена")
        sys.exit(0)
    
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        for proc in processes:
            try:
                proc.terminate()
            except:
                pass
        sys.exit(1)

if __name__ == "__main__":
    main()

