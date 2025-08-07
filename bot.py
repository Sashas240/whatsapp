import logging
from config import load_environment
from handlers import setup_handlers
from telegram.ext import Application
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class Bot:
    def __init__(self):
        # Загрузка конфигурации
        config = load_environment()
        self.token = config['BOT_TOKEN']
        self.admin_ids = config['ADMIN_IDS']
        self.group_link = config['GROUP_LINK']
        self.app_name = config.get('APP_NAME', 'my-telegram-bot')  # Имя приложения для webhook
        
        self.app = Application.builder().token(self.token).build()
        setup_handlers(self)
        self.admin_messages = {}  # Словарь для хранения ID сообщений для каждого админа

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
        """Запуск бота с использованием webhook"""
        logger.info("Запуск бота с webhook...")
        self.app.run_webhooks(
            listen="0.0.0.0",
            port=8080,
            url_path="/webhook",
            webhook_url=f"https://{self.app_name}.onrender.com/webhook"
        )

def main():
    bot = Bot()
    try:
        bot.run()
    except KeyboardInterrupt:
        logger.info("Бот остановлен")
    except Exception as e:
        logger.error(f"Ошибка: {e}")

if __name__ == "__main__":
    main()