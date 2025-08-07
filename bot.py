import logging
import os
from config import load_environment
from handlers import setup_handlers
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application
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
LISTEN_IP = "0.0.0.0"

class Bot:
    def __init__(self):
        self.token = BOT_TOKEN
        self.admin_ids = ADMIN_IDS
        self.group_link = GROUP_LINK
        
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
    
    bot_instance = Bot()
    
    # Настраиваем обработчики команд и сообщений
    setup_handlers(bot_instance)
    
    # Запускаем бота в режиме вебхука, используя встроенные возможности библиотеки python-telegram-bot
    try:
        if WEBHOOK_URL:
            # Обрати внимание, что app.run_webhook автоматически запускает веб-сервер и Flask
            bot_instance.app.run_webhook(
                listen=LISTEN_IP,
                port=PORT,
                url_path=BOT_TOKEN,
                webhook_url=f"{WEBHOOK_URL}/{BOT_TOKEN}"
            )
            logger.info(f"Вебхук запущен на {LISTEN_IP}:{PORT} с URL {WEBHOOK_URL}/{BOT_TOKEN}")
        else:
            logger.error("Переменная WEBHOOK_URL не найдена. Вебхук не будет запущен.")
    except Exception as e:
        logger.error(f"Ошибка при запуске вебхука: {e}")

if __name__ == "__main__":
    main()