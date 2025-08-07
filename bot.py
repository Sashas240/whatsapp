import logging
import os
from config import load_environment
from handlers import setup_handlers
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application
from flask import Flask, request, jsonify

# Настройка логирования для вывода информации в консоль
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
config = load_environment()
BOT_TOKEN = config['BOT_TOKEN']
WEBHOOK_URL = config['WEBHOOK_URL']
PORT = int(config.get('PORT', 5000))
ADMIN_IDS = config['ADMIN_IDS']
GROUP_LINK = config['GROUP_LINK']

class Bot:
    def __init__(self):
        # Загрузка конфигурации
        self.token = BOT_TOKEN
        self.admin_ids = ADMIN_IDS
        self.group_link = GROUP_LINK
        
        self.app = Application.builder().token(self.token).build()
        self.admin_messages = {}  # Словарь для хранения ID сообщений для каждого админа
        self.processing_user = None # Пользователь, чей номер сейчас обрабатывается
        setup_handlers(self)

    async def notify_admin_new_phone(self, phone_entry: dict):
        """Уведомление администраторов о новом номере"""
        user_info = f"@{phone_entry['username']}" if phone_entry['username'] != f"user_{phone_entry['user_id']}" else f"ID: {phone_entry['user_id']}"
        
        # Если никто не обрабатывается, показываем номер с кнопками
        if self.processing_user is None:
            text = f"📞 Новый номер: {phone_entry['phone']}\nОт: {user_info}\n\nВыберите действие:"
            keyboard = [
                [
                    InlineKeyboardButton("Взять", callback_data=f"take_phone_{phone_entry['user_id']}"),
                    InlineKeyboardButton("Пропустить", callback_data=f"skip_phone_{phone_entry['user_id']}")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Отправляем уведомление всем администраторам
            for admin_id in self.admin_ids:
                try:
                    message = await self.app.bot.send_message(admin_id, text, reply_markup=reply_markup)
                    # Сохраняем ID сообщения для каждого админа
                    if phone_entry['user_id'] not in self.admin_messages:
                        self.admin_messages[phone_entry['user_id']] = {}
                    self.admin_messages[phone_entry['user_id']][admin_id] = message.message_id
                except Exception as e:
                    logger.error(f"Ошибка отправки уведомления админу {admin_id}: {e}")
        else:
            # Если кто-то уже обрабатывается, добавляем в очередь БЕЗ уведомления
            return

    async def delete_admin_messages(self, user_id: int, except_admin_id: int = None):
        """Удаление сообщений о номере у всех администраторов, кроме указанного"""
        if user_id in self.admin_messages:
            for admin_id, message_id in self.admin_messages[user_id].items():
                if admin_id != except_admin_id:
                    try:
                        await self.app.bot.delete_message(chat_id=admin_id, message_id=message_id)
                    except Exception as e:
                        logger.error(f"Ошибка удаления сообщения у админа {admin_id}: {e}")
            # Очищаем сообщения для данного user_id, кроме того, кто забрал
            if except_admin_id:
                self.admin_messages[user_id] = {
                    except_admin_id: self.admin_messages[user_id].get(except_admin_id)
                }
            else:
                del self.admin_messages[user_id]
    
    def run(self):
        """Запуск бота как вебсервиса"""
        logger.info("Запуск бота в режиме webhook...")

        # Задаем URL вебхука для Telegram
        webhook_url_full = f"{WEBHOOK_URL}/{BOT_TOKEN}"
        self.app.bot.set_webhook(url=webhook_url_full)
        logger.info(f"Вебхук установлен на URL: {webhook_url_full}")

        # Создаем и запускаем веб-сервер Flask
        flask_app = Flask(__name__)

        @flask_app.route('/')
        def hello():
            return "Bot is running!"

        @flask_app.route(f"/{BOT_TOKEN}", methods=['POST'])
        async def webhook():
            """Обработка входящих вебхуков"""
            update = Update.de_json(request.get_json(force=True), self.app.bot)
            await self.app.process_update(update)
            return jsonify({'status': 'ok'})

        # Запускаем Flask-сервер на указанном порту
        flask_app.run(host="0.0.0.0", port=PORT)

def main():
    bot = Bot()
    main_async_loop = bot.app.loop
    main_async_loop.run_until_complete(bot.run())

if __name__ == "__main__":
    main()