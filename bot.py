import logging
import os
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
        self.app_name = config.get('APP_NAME', 'xvcen-whatsapp-bot')  # Имя приложения для webhook
        self.port = int(os.getenv('PORT', 8080))  # Порт из переменных окружения

        # Проверка токена
        if not self.token or not self.token.strip():
            logger.error("BOT_TOKEN не установлен или пустой!")
            raise ValueError("BOT_TOKEN не установлен или пустой!")
        if ":" not in self.token:
            logger.error(f"Недействительный формат BOT_TOKEN: {self.token}")
            raise ValueError("Недействительный формат BOT_TOKEN. Получите токен от @BotFather.")

        logger.info(f"Используемый BOT_TOKEN: {self.token[:10]}... (скрыт для безопасности)")
        
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

    async def setup_webhook(self):
        """Настройка webhook"""
        try:
            webhook_url = f"https://{self.app_name}.onrender.com/webhook"
            logger.info(f"Устанавливаем webhook: {webhook_url}")
            await self.app.bot.set_webhook(url=webhook_url)
            logger.info("Webhook успешно установлен")
        except Exception as e:
            logger.error(f"Ошибка установки webhook: {e}")
            raise

    def run(self):
        """Запуск бота с использованием webhook"""
        try:
            logger.info(f"Запуск бота с webhook на https://{self.app_name}.onrender.com/webhook")
            logger.info(f"Слушаем на порту: {self.port}")
            
            self.app.run_webhook(
                listen="0.0.0.0",
                port=self.port,
                url_path="/webhook",
                webhook_url=f"https://{self.app_name}.onrender.com/webhook"
            )
        except Exception as e:
            logger.error(f"Ошибка запуска webhook: {e}")
            # Fallback на polling для локальной разработки
            logger.info("Переключаемся на polling...")
            self.app.run_polling()

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