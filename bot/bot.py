import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters
)

import sys
import os
# Add current directory and parent directory to path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)
sys.path.insert(0, current_dir)

from config.config import BOT_TOKEN, BOT_USERNAME, DB_PATH
from database import Database
from utils.logger import bot_logger as logger

class AttendanceBot:
    def __init__(self):
        self.db = Database(str(DB_PATH))

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
                f"🤖 Мой username: @{BOT_USERNAME}"
            )
            await update.message.reply_text(welcome_text)

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
        """Handle text messages (for FIO input)"""
        user = update.effective_user
        text = update.message.text.strip()

        # Check if user is in registration process
        if 'pending_registration' in context.user_data:
            registration_data = context.user_data['pending_registration']

            # Validate FIO
            if len(text) < 3:
                await update.message.reply_text(
                    "❌ ФИО слишком короткое. Пожалуйста, введите полное имя:"
                )
                return

            # Create user record
            try:
                self.db.create_person(
                    tg_user_id=user.id,
                    fio=text,
                    username=user.username
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
                    timestamp = user_events[0]['ts'][:19].replace('T', ' ')
                else:
                    # Fallback to current time if no events found
                    from datetime import datetime
                    timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
            except Exception as e:
                logger.warning(f"Could not get timestamp for user {user.id}: {e}")
                from datetime import datetime
                timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')

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
                "📱 Отсканируйте QR-код у терминала для регистрации."
            )
            return

        events = self.db.get_user_events(user.id, limit=10)

        if not events:
            await update.message.reply_text("📝 У вас пока нет событий.")
            return

        text = f"📋 Последние события для {person['fio']}:\n\n"

        for event in events:
            time_str = event['ts'][:19].replace('T', ' ')
            location_display = event['location'].replace('_', ' ').title()
            action_text = "Пришёл" if event['action'] == 'in' else "Ушёл"
            emoji = "✅" if event['action'] == 'in' else "🚪"

            text += f"{emoji} {time_str} - {location_display} ({action_text})\n"

        await update.message.reply_text(text)

    async def who_here_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show who is currently present (admin only)"""
        # For now, allow anyone to see (in production, add admin check)
        present_users = self.db.get_currently_present()

        if not present_users:
            await update.message.reply_text("🏢 В данный момент в офисе никого нет.")
            return

        text = "🏢 Сейчас в офисе:\n\n"

        for user in present_users:
            time_str = user['ts'][:19].replace('T', ' ')
            location_display = user['location'].replace('_', ' ').title()
            text += f"👤 {user['fio']} - {location_display} (с {time_str})\n"

        await update.message.reply_text(text)

def main():
    """Start the bot"""
    bot = AttendanceBot()

    application = ApplicationBuilder().token(BOT_TOKEN).build()

    # Add handlers
    application.add_handler(CommandHandler("start", bot.start_command))
    application.add_handler(CommandHandler("my_last", bot.my_last_command))
    application.add_handler(CommandHandler("who_here", bot.who_here_command))
    application.add_handler(CallbackQueryHandler(bot.handle_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_text_message))

    # Start the bot
    logger.info("Starting bot...")
    application.run_polling()

if __name__ == '__main__':
    main()
