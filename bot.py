import logging
import os
from config import load_environment
from handlers import setup_handlers
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application
from flask import Flask, request, jsonify

# Налаштування логування для виведення інформації в консоль
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Завантаження змінних оточення
config = load_environment()
BOT_TOKEN = config['BOT_TOKEN']
ADMIN_IDS = config['ADMIN_IDS']
GROUP_LINK = config['GROUP_LINK']

# Додаткові змінні для вебхука
WEBHOOK_URL = os.getenv('WEBHOOK_URL')
PORT = int(os.getenv('PORT', 5000))

class Bot:
    def __init__(self):
        # Завантаження конфігурації
        self.token = BOT_TOKEN
        self.admin_ids = ADMIN_IDS
        self.group_link = GROUP_LINK
        
        self.app = Application.builder().token(self.token).build()
        setup_handlers(self)
        self.admin_messages = {}  # Словник для зберігання ID повідомлень для кожного адміна
        self.processing_user = None # Користувач, чий номер зараз обробляється

    async def notify_admin_new_phone(self, phone_entry: dict):
        """Сповіщення адміністраторів про новий номер"""
        user_info = f"@{phone_entry['username']}" if phone_entry['username'] != f"user_{phone_entry['user_id']}" else f"ID: {phone_entry['user_id']}"
        
        # Якщо ніхто не обробляється, показуємо номер з кнопками
        if self.processing_user is None:
            text = f"📞 Новий номер: {phone_entry['phone']}\nВід: {user_info}\n\nОберіть дію:"
            keyboard = [
                [
                    InlineKeyboardButton("Взяти", callback_data=f"take_phone_{phone_entry['user_id']}"),
                    InlineKeyboardButton("Пропустити", callback_data=f"skip_phone_{phone_entry['user_id']}")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Відправляємо сповіщення всім адміністраторам
            for admin_id in self.admin_ids:
                try:
                    message = await self.app.bot.send_message(admin_id, text, reply_markup=reply_markup)
                    # Зберігаємо ID повідомлення для кожного адміна
                    if phone_entry['user_id'] not in self.admin_messages:
                        self.admin_messages[phone_entry['user_id']] = {}
                    self.admin_messages[phone_entry['user_id']][admin_id] = message.message_id
                except Exception as e:
                    logger.error(f"Помилка відправки сповіщення адміну {admin_id}: {e}")
        else:
            # Якщо хтось вже обробляється, додаємо в чергу БЕЗ сповіщення
            return

    async def delete_admin_messages(self, user_id: int, except_admin_id: int = None):
        """Видалення повідомлень про номер у всіх адміністраторів, крім зазначеного"""
        if user_id in self.admin_messages:
            for admin_id, message_id in self.admin_messages[user_id].items():
                if admin_id != except_admin_id:
                    try:
                        await self.app.bot.delete_message(chat_id=admin_id, message_id=message_id)
                    except Exception as e:
                        logger.error(f"Помилка видалення повідомлення у адміна {admin_id}: {e}")
            # Очищуємо повідомлення для даного user_id, крім того, хто забрав
            if except_admin_id:
                self.admin_messages[user_id] = {
                    except_admin_id: self.admin_messages[user_id].get(except_admin_id)
                }
            else:
                del self.admin_messages[user_id]

    def run(self):
        """Запуск бота як вебсервісу"""
        logger.info("Запуск бота в режимі webhook...")

        # Задаємо URL вебхука для Telegram
        webhook_url_full = f"{WEBHOOK_URL}/{BOT_TOKEN}"
        self.app.bot.set_webhook(url=webhook_url_full)
        logger.info(f"Вебхук встановлено на URL: {webhook_url_full}")

        # Створюємо і запускаємо веб-сервер Flask
        flask_app = Flask(__name__)

        @flask_app.route('/')
        def hello():
            return "Bot is running!"

        @flask_app.route(f"/{BOT_TOKEN}", methods=['POST'])
        async def webhook():
            """Обробка вхідних вебхуків"""
            update = Update.de_json(request.get_json(force=True), self.app.bot)
            await self.app.process_update(update)
            return jsonify({'status': 'ok'})

        # Запускаємо Flask-сервер на зазначеному порту
        flask_app.run(host="0.0.0.0", port=PORT)

def main():
    bot = Bot()
    bot.run()

if __name__ == "__main__":
    main()