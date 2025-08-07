import logging
import os
from config import load_environment
from handlers import setup_handlers
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application
from flask import Flask, request, jsonify
import asyncio

# Настройка логирования для вывода информации в консоль
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
config = load_environment()
BOT_TOKEN = config.get('BOT_TOKEN')
ADMIN_IDS = config.get('ADMIN_IDS')
GROUP_LINK = config.get('GROUP_LINK')

# Дополнительные переменные для вебхука
WEBHOOK_URL = os.getenv('WEBHOOK_URL')
PORT = int(os.getenv('PORT', 5000))

class Bot:
    def __init__(self):
        # Загрузка конфигурации
        self.token = BOT_TOKEN
        self.admin_ids = ADMIN_IDS
        self.group_link = GROUP_LINK
        
        # Создаем экземпляр Application
        self.app = Application.builder().token(self.token).build()
        setup_handlers(self)
        self.admin_messages = {}  # Словарь для хранения ID сообщений для каждого админа
        self.processing_user = None # Пользователь, чей номер сейчас обрабатывается

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

# Основная функция для запуска бота
def main():
    logger.info("Запуск бота в режиме webhook...")
    
    app = Application.builder().token(BOT_TOKEN).build()
    bot_instance = Bot()
    
    # Настраиваем обработчики команд и сообщений
    setup_handlers(bot_instance)
    
    flask_app = Flask(__name__)

    @flask_app.route('/')
    def hello():
        return "Bot is running!"

    @flask_app.route(f"/{BOT_TOKEN}", methods=['POST'])
    async def webhook():
        """Обработка входящих вебхуков"""
        update = Update.de_json(request.get_json(force=True), app.bot)
        async with app:
            await app.process_update(update)
        return jsonify({'status': 'ok'})
    
    # Задаем URL вебхука для Telegram
    async def set_telegram_webhook():
        webhook_url_full = f"{WEBHOOK_URL}/{BOT_TOKEN}"
        # Проверяем, что WEBHOOK_URL существует, прежде чем устанавливать его
        if WEBHOOK_URL:
            await app.bot.set_webhook(url=webhook_url_full)
            logger.info(f"Вебхук установлен на URL: {webhook_url_full}")
        else:
            logger.error("Переменная WEBHOOK_URL не найдена. Вебхук не будет установлен.")
        
    loop = asyncio.get_event_loop()
    loop.run_until_complete(set_telegram_webhook())
    
    # Запускаем Flask-сервер на указанном порту
    flask_app.run(host="0.0.0.0", port=PORT)

if __name__ == "__main__":
    main()