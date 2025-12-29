import logging
import asyncio
from datetime import datetime, timezone, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

import sys
import os
# Add current directory and parent directory to path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)
sys.path.insert(0, current_dir)

from config.config import BOT_TOKEN, BOT_USERNAME, DB_PATH, TIMEZONE, TIMEZONE_OFFSET_HOURS
from database import Database
from utils.logger import bot_logger as logger
from utils.validators import validate_fio, sanitize_string

class AttendanceBot:
    def __init__(self, application=None):
        self.db = Database(str(DB_PATH))
        self.application = application
        self.reminder_sent = {}  # Track sent reminders: {user_id: message_id}
        
        # Main menu keyboard
        self.main_keyboard = ReplyKeyboardMarkup(
            [
                [KeyboardButton("📋 Мои последние события"), KeyboardButton("🏢 Кто в офисе")],
                [KeyboardButton("🔑 Восстановить пароль"), KeyboardButton("ℹ️ Помощь")],
                [KeyboardButton("🔄 Обновить меню")]
            ],
            resize_keyboard=True,
            one_time_keyboard=False
        )

    @staticmethod
    def utc_to_local(utc_time_str: str) -> str:
        """Convert UTC time string to local timezone (automatically detected)"""
        try:
            # Parse UTC time
            if 'T' in utc_time_str:
                dt = datetime.fromisoformat(utc_time_str.replace('Z', '+00:00'))
            else:
                # If format is 'YYYY-MM-DD HH:MM:SS', assume UTC
                dt = datetime.strptime(utc_time_str, '%Y-%m-%d %H:%M:%S')
                dt = dt.replace(tzinfo=timezone.utc)
            
            # Convert to local timezone
            local_time = dt.astimezone(TIMEZONE)
            return local_time.strftime('%Y-%m-%d %H:%M:%S')
        except Exception as e:
            # Fallback to simple offset if timezone conversion fails
            try:
                if 'T' in utc_time_str:
                    dt = datetime.fromisoformat(utc_time_str.replace('Z', '+00:00'))
                else:
                    dt = datetime.strptime(utc_time_str, '%Y-%m-%d %H:%M:%S')
                    dt = dt.replace(tzinfo=timezone.utc)
                local_time = dt + timedelta(hours=TIMEZONE_OFFSET_HOURS)
                return local_time.strftime('%Y-%m-%d %H:%M:%S')
            except Exception:
                # If all parsing fails, return original
                return utc_time_str

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        user = update.effective_user
        args = context.args

        if args:
            # /start with token
            token = args[0]
            await self.handle_token_start(update, context, token)
        else:
            # /start without parameters
            welcome_text = (
                "👋 Привет! Это бот для учёта рабочего времени.\n\n"
                "📱 Для отметки прихода/ухода отсканируйте QR-код у терминала на входе.\n\n"
                f"🤖 Мой username: @{BOT_USERNAME}\n\n"
                "💡 Используйте кнопки меню ниже для быстрого доступа к функциям."
            )
            await update.message.reply_text(
                welcome_text,
                reply_markup=self.main_keyboard
            )

    async def handle_token_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE, token: str):
        """Handle start with token"""
        user = update.effective_user
        logger.info(f"Token scan attempt by user {user.id} ({user.username}): token={token[:8]}...")

        # Check if token is valid
        if not self.db.is_token_valid(token):
            await update.message.reply_text(
                "❌ QR-код не распознан или уже использован.\n"
                "📱 Пожалуйста, отсканируйте новый код у терминала на входе."
            )
            return

        # All tokens are now global
        location = "global"

        # Check if user is registered
        person = self.db.get_person_by_tg_id(user.id)

        if person:
            # User is registered, show check-in/out buttons
            creds = self.db.ensure_web_user_for_person(user.id, person["fio"])
            if creds:
                await update.message.reply_text(
                    "🆕 Учетка для входа на сайт создана.\n"
                    f"👤 Логин: {creds['username']}\n"
                    f"🔑 Пароль: {creds['password']}\n"
                    "💾 Сохраните пароль — он показывается один раз.\n"
                    "🌐 Вход: откройте веб-панель и авторизуйтесь под этими данными."
                )
            await self.show_action_buttons(update, context, token, location, person)
        else:
            # User is new, ask for FIO
            context.user_data['pending_registration'] = {
                'token': token,
                'location': location
            }

            await update.message.reply_text(
                "👤 Вы впервые отмечаетесь в системе.\n"
                "📝 Пожалуйста, введите ваше ФИО одной строкой\n"
                "(например: Иванов Иван Иванович):"
            )

    async def handle_text_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text messages (for FIO input and menu buttons)"""
        user = update.effective_user
        text = update.message.text.strip()

        # Handle menu button clicks
        if text == "📋 Мои последние события":
            await self.my_last_command(update, context)
            return
        elif text == "🏢 Кто в офисе":
            await self.who_here_command(update, context)
            return
        elif text == "🔑 Восстановить пароль":
            await self.reset_password_command(update, context)
            return
        elif text == "ℹ️ Помощь":
            await self.help_command(update, context)
            return
        elif text == "🔄 Обновить меню":
            await update.message.reply_text(
                "✅ Меню обновлено!",
                reply_markup=self.main_keyboard
            )
            return

        # Check if user is in registration process
        if 'pending_registration' in context.user_data:
            registration_data = context.user_data['pending_registration']

            # Validate FIO
            text = sanitize_string(text, max_length=200)
            is_valid, error_msg = validate_fio(text)
            if not is_valid:
                await update.message.reply_text(
                    f"❌ {error_msg}\nПожалуйста, введите ваше ФИО:"
                )
                return

            # Create user record
            try:
                self.db.create_person(
                    tg_user_id=user.id,
                    fio=text,
                    username=user.username
                )

                # Create web credentials for portal login (role user)
                creds = self.db.provision_web_credentials(
                    tg_user_id=user.id,
                    fio=text
                )

                # Remove from pending registration
                del context.user_data['pending_registration']

                # Show action buttons
                person = self.db.get_person_by_tg_id(user.id)
                await self.show_action_buttons(
                    update, context,
                    registration_data['token'],
                    registration_data['location'],
                    person
                )

                if creds:
                    await update.message.reply_text(
                        "🆕 Учетка для входа на сайт создана.\n"
                        f"👤 Логин: {creds['username']}\n"
                        f"🔑 Пароль: {creds['password']}\n"
                        "💾 Сохраните пароль — он показывается один раз.\n"
                        "🌐 Вход: откройте веб-панель и авторизуйтесь под этими данными.",
                        reply_markup=self.main_keyboard
                    )

            except Exception as e:
                logger.error(f"Error creating person: {e}")
                await update.message.reply_text(
                    "❌ Ошибка при сохранении данных. Попробуйте ещё раз."
                )

    async def show_action_buttons(self, update, context, token: str, location: str, person: dict):
        """Show check-in/check-out buttons"""
        keyboard = [
            [
                InlineKeyboardButton("✅ Пришёл", callback_data=f"checkin:{token}"),
                InlineKeyboardButton("🚪 Ушёл", callback_data=f"checkout:{token}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        location_display = location.replace('_', ' ').title()

        await update.message.reply_text(
            f"🏢 Локация: {location_display}\n"
            f"👤 {person['fio']}\n\n"
            "Выберите действие:",
            reply_markup=reply_markup
        )

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle button callbacks"""
        query = update.callback_query
        await query.answer()

        user = update.effective_user
        data = query.data

        # Handle reminder checkout (no token needed)
        if data == "reminder_checkout":
            await self.handle_reminder_checkout(update, context, user)
            return

        try:
            action, token = data.split(':', 1)
        except ValueError:
            await query.edit_message_text("❌ Ошибка: некорректные данные.")
            return

        # Validate token
        if not self.db.is_token_valid(token):
            await query.edit_message_text(
                "❌ Этот QR-код уже использован.\n"
                "📱 Отсканируйте новый код у терминала."
            )
            return

        # Get location
        # All tokens are now global
        location = "global"

        # Get user info
        person = self.db.get_person_by_tg_id(user.id)
        if not person:
            await query.edit_message_text(
                "❌ Пользователь не найден. Начните заново с /start"
            )
            return

        # Determine action
        if action == "checkin":
            action_text = "приход"
            action_code = "in"
        elif action == "checkout":
            action_text = "уход"
            action_code = "out"
        else:
            await query.edit_message_text("❌ Неизвестное действие.")
            return

        # Prevent duplicate state (нельзя прийти дважды подряд или уйти дважды подряд)
        last_events = self.db.get_user_events(user.id, limit=1)
        if last_events:
            last_action = last_events[0]["action"]
            if action_code == "in" and last_action == "in":
                await query.edit_message_text(
                    "⚠️ Вы уже отметили приход. Сначала отметьте уход."
                )
                return
            if action_code == "out" and last_action == "out":
                await query.edit_message_text(
                    "⚠️ Вы уже отметили уход. Сначала отметьте приход."
                )
                return
        else:
            # No events yet — нельзя уйти, если не было прихода
            if action_code == "out":
                await query.edit_message_text(
                    "⚠️ Сначала отметьте приход, потом уход."
                )
                return

        # Create event
        try:
            self.db.create_event(
                user_id=user.id,
                location=location,
                action=action_code,
                username=user.username,
                full_name=person['fio']
            )

            # Mark token as used
            self.db.mark_token_used(token)

            # Create new active token for this location
            new_token = self.db.create_token()

            # Send confirmation
            location_display = location.replace('_', ' ').title()

            # Get timestamp safely
            try:
                user_events = self.db.get_user_events(user.id, 1)
                if user_events:
                    utc_timestamp = user_events[0]['ts'][:19].replace('T', ' ')
                    timestamp = self.utc_to_local(utc_timestamp)
                else:
                    # Fallback to current time if no events found
                    utc_now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
                    timestamp = self.utc_to_local(utc_now)
            except Exception as e:
                logger.warning(f"Could not get timestamp for user {user.id}: {e}")
                utc_now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
                timestamp = self.utc_to_local(utc_now)

            await query.edit_message_text(
                f"✅ Отмечено: {action_text}\n"
                f"🏢 Локация: {location_display}\n"
                f"👤 {person['fio']}\n"
                f"🕐 Время: {timestamp}"
            )

        except Exception as e:
            logger.error(f"Error creating event: {e}")
            await query.edit_message_text("❌ Ошибка при сохранении события.")

    async def my_last_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show user's recent events"""
        user = update.effective_user
        person = self.db.get_person_by_tg_id(user.id)

        if not person:
            await update.message.reply_text(
                "❌ Вы не зарегистрированы в системе.\n"
                "📱 Отсканируйте QR-код у терминала для регистрации.",
                reply_markup=self.main_keyboard
            )
            return

        events = self.db.get_user_events(user.id, limit=10)

        if not events:
            await update.message.reply_text(
                "📝 У вас пока нет событий.",
                reply_markup=self.main_keyboard
            )
            return

        text = f"📋 Последние события для {person['fio']}:\n\n"

        for event in events:
            utc_time_str = event['ts'][:19].replace('T', ' ')
            time_str = self.utc_to_local(utc_time_str)
            location_display = event['location'].replace('_', ' ').title()
            action_text = "Пришёл" if event['action'] == 'in' else "Ушёл"
            emoji = "✅" if event['action'] == 'in' else "🚪"

            text += f"{emoji} {time_str} - {location_display} ({action_text})\n"

        await update.message.reply_text(
            text,
            reply_markup=self.main_keyboard
        )

    async def who_here_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show who is currently present (admin only)"""
        # For now, allow anyone to see (in production, add admin check)
        present_users = self.db.get_currently_present()

        if not present_users:
            await update.message.reply_text("🏢 В данный момент в офисе никого нет.")
            return

        text = "🏢 Сейчас в офисе:\n\n"

        for user in present_users:
            utc_time_str = user['ts'][:19].replace('T', ' ')
            time_str = self.utc_to_local(utc_time_str)
            location_display = user['location'].replace('_', ' ').title()
            text += f"👤 {user['fio']} - {location_display} (с {time_str})\n"

        await update.message.reply_text(
            text,
            reply_markup=self.main_keyboard
        )

    async def reset_password_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Reset password for web portal access"""
        user = update.effective_user
        person = self.db.get_person_by_tg_id(user.id)

        if not person:
            await update.message.reply_text(
                "❌ Вы не зарегистрированы в системе.\n"
                "📱 Отсканируйте QR-код у терминала для регистрации.",
                reply_markup=self.main_keyboard
            )
            return

        # Find web user by tg_user_id pattern (username like "user{id}")
        base_username = f"user{user.id}"
        web_user = self.db.get_web_user_by_username(base_username)
        
        # If not found, try with suffix
        if not web_user:
            suffix = 1
            while not web_user and suffix < 10:
                candidate = f"{base_username}{suffix}"
                web_user = self.db.get_web_user_by_username(candidate)
                if web_user:
                    base_username = candidate
                    break
                suffix += 1

        if not web_user:
            # Create web user if doesn't exist
            creds = self.db.provision_web_credentials(
                tg_user_id=user.id,
                fio=person['fio']
            )
            await update.message.reply_text(
                "🆕 Учетная запись для веб-портала создана!\n\n"
                f"👤 Логин: {creds['username']}\n"
                f"🔑 Пароль: {creds['password']}\n\n"
                "💾 Сохраните пароль в безопасном месте.\n"
                "🌐 Вход: откройте веб-панель и авторизуйтесь под этими данными.",
                reply_markup=self.main_keyboard
            )
            return

        # Generate new password
        import secrets
        from auth.jwt_handler import JWTHandler
        
        new_password = secrets.token_urlsafe(10)
        password_hash = JWTHandler.get_password_hash(new_password)

        # Update password in database
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE web_users SET password_hash = ? WHERE username = ?",
                (password_hash, base_username)
            )
            conn.commit()

        await update.message.reply_text(
            "✅ Пароль успешно восстановлен!\n\n"
            f"👤 Логин: {base_username}\n"
            f"🔑 Новый пароль: {new_password}\n\n"
            "💾 Сохраните новый пароль в безопасном месте.\n"
            "🌐 Вход: откройте веб-панель и авторизуйтесь под этими данными.",
            reply_markup=self.main_keyboard
        )

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show help information"""
        help_text = (
            "📖 Помощь по использованию бота:\n\n"
            "🔹 **Отметка прихода/ухода:**\n"
            "   Отсканируйте QR-код у терминала на входе\n\n"
            "🔹 **Команды:**\n"
            "   /start - Начать работу с ботом\n"
            "   /my_last - Показать последние события\n"
            "   /who_here - Показать кто сейчас в офисе\n"
            "   /reset_password - Восстановить пароль для веб-портала\n\n"
            "🔹 **Кнопки меню:**\n"
            "   📋 Мои последние события - История ваших отметок\n"
            "   🏢 Кто в офисе - Список присутствующих\n"
            "   🔑 Восстановить пароль - Получить новый пароль для веб-портала\n"
            "   ℹ️ Помощь - Эта справка\n"
            "   🔄 Обновить меню - Обновить кнопки меню\n\n"
            "💡 Используйте кнопки меню для быстрого доступа к функциям!"
        )
        await update.message.reply_text(
            help_text,
            reply_markup=self.main_keyboard,
            parse_mode='Markdown'
        )

    async def handle_reminder_checkout(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user):
        """Handle checkout from reminder button"""
        query = update.callback_query
        
        # Get user info
        person = self.db.get_person_by_tg_id(user.id)
        if not person:
            await query.edit_message_text("❌ Пользователь не найден.")
            return

        # Check if user has open session
        last_events = self.db.get_user_events(user.id, limit=1)
        if not last_events or last_events[0]["action"] != "in":
            await query.edit_message_text(
                "✅ У вас нет открытой сессии. Возможно, вы уже отметили уход."
            )
            # Clear reminder tracking
            if user.id in self.reminder_sent:
                del self.reminder_sent[user.id]
            return

        # Create checkout event
        try:
            self.db.create_event(
                user_id=user.id,
                location="global",
                action="out",
                username=user.username,
                full_name=person['fio']
            )

            # Get timestamp
            user_events = self.db.get_user_events(user.id, 1)
            if user_events:
                utc_timestamp = user_events[0]['ts'][:19].replace('T', ' ')
                timestamp = self.utc_to_local(utc_timestamp)
            else:
                utc_now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
                timestamp = self.utc_to_local(utc_now)

            await query.edit_message_text(
                f"✅ Уход отмечен!\n"
                f"👤 {person['fio']}\n"
                f"🕐 Время: {timestamp}\n\n"
                f"💤 Хорошего отдыха!"
            )

            # Clear reminder tracking
            if user.id in self.reminder_sent:
                del self.reminder_sent[user.id]

        except Exception as e:
            logger.error(f"Error creating checkout event from reminder: {e}")
            await query.edit_message_text("❌ Ошибка при сохранении события.")

    async def check_and_send_reminders(self):
        """Check for open sessions older than 8 hours and send reminders"""
        if not self.application:
            return

        try:
            # Get open sessions older than 8 hours
            open_sessions = self.db.get_open_sessions_older_than(8.0)
            
            for session in open_sessions:
                user_id = session['tg_user_id']
                hours_open = session.get('hours_open', 0)
                
                # Skip if we already sent a reminder (to avoid spam)
                if user_id in self.reminder_sent:
                    continue

                try:
                    # Calculate time in local timezone for display
                    checkin_time = datetime.fromisoformat(session['ts'].replace('Z', '+00:00'))
                    local_time = checkin_time.astimezone(TIMEZONE)
                    time_str = local_time.strftime('%H:%M')

                    # Create reminder message with button
                    reminder_text = (
                        f"⏰ Напоминание\n\n"
                        f"Вы отметили приход в {time_str}\n"
                        f"Прошло уже {int(hours_open)} часов.\n\n"
                        f"🏠 Не забыли отметить уход?"
                    )

                    keyboard = [[InlineKeyboardButton("✅ Да, ушел", callback_data="reminder_checkout")]]
                    reply_markup = InlineKeyboardMarkup(keyboard)

                    # Send reminder
                    message = await self.application.bot.send_message(
                        chat_id=user_id,
                        text=reminder_text,
                        reply_markup=reply_markup
                    )

                    # Track sent reminder
                    self.reminder_sent[user_id] = message.message_id
                    logger.info(f"Sent reminder to user {user_id} ({session['fio']})")

                except Exception as e:
                    logger.error(f"Error sending reminder to user {user_id}: {e}")
                    # If user blocked bot or error, remove from tracking
                    if "blocked" in str(e).lower() or "chat not found" in str(e).lower():
                        if user_id in self.reminder_sent:
                            del self.reminder_sent[user_id]

        except Exception as e:
            logger.error(f"Error in check_and_send_reminders: {e}")

    async def cleanup_old_reminders(self):
        """Clean up reminder tracking for closed sessions"""
        try:
            open_sessions = self.db.get_currently_present()
            open_user_ids = {session['tg_user_id'] for session in open_sessions}
            
            # Remove tracking for users who closed their session
            closed_users = [uid for uid in self.reminder_sent.keys() if uid not in open_user_ids]
            for uid in closed_users:
                del self.reminder_sent[uid]
                logger.debug(f"Cleaned up reminder tracking for user {uid}")

        except Exception as e:
            logger.error(f"Error in cleanup_old_reminders: {e}")

def main():
    """Start the bot"""
    # Configure application with increased timeout settings for network issues
    application = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .connect_timeout(60.0)
        .read_timeout(60.0)
        .write_timeout(60.0)
        .pool_timeout(60.0)
        .build()
    )
    bot = AttendanceBot(application=application)

    # Add handlers
    application.add_handler(CommandHandler("start", bot.start_command))
    application.add_handler(CommandHandler("my_last", bot.my_last_command))
    application.add_handler(CommandHandler("who_here", bot.who_here_command))
    application.add_handler(CommandHandler("reset_password", bot.reset_password_command))
    application.add_handler(CommandHandler("help", bot.help_command))
    application.add_handler(CallbackQueryHandler(bot.handle_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_text_message))

    # Setup scheduler for reminders
    scheduler = AsyncIOScheduler()
    # Check every 30 minutes for open sessions older than 8 hours
    scheduler.add_job(
        bot.check_and_send_reminders,
        trigger=IntervalTrigger(minutes=30),
        id='check_reminders',
        replace_existing=True
    )
    # Cleanup reminder tracking every hour
    scheduler.add_job(
        bot.cleanup_old_reminders,
        trigger=IntervalTrigger(hours=1),
        id='cleanup_reminders',
        replace_existing=True
    )
    scheduler.start()

    # Start the bot
    logger.info("Starting bot with reminder scheduler...")
    max_retries = 5
    retry_count = 0
    
    try:
        while retry_count < max_retries:
            try:
                logger.info(f"Attempting to start bot (attempt {retry_count + 1}/{max_retries})...")
                application.run_polling(
                    allowed_updates=Update.ALL_TYPES,
                    drop_pending_updates=False,
                    close_loop=False
                )
                break  # Success, exit loop
            except KeyboardInterrupt:
                logger.info("Bot stopped by user")
                break
            except Exception as e:
                retry_count += 1
                logger.error(f"Error starting bot (attempt {retry_count}/{max_retries}): {e}", exc_info=True)
                if retry_count >= max_retries:
                    logger.error("Max retries reached. Bot failed to start.")
                    raise
                logger.info(f"Retrying in 10 seconds...")
                import time
                time.sleep(10)
    finally:
        try:
            if scheduler.running:
                scheduler.shutdown(wait=False)
        except RuntimeError:
            # Event loop already closed, ignore
            pass
        except Exception as e:
            logger.error(f"Error shutting down scheduler: {e}")

if __name__ == '__main__':
    main()
