import os
from dotenv import load_dotenv
from enum import Enum

class UserState(Enum):
    IDLE = "idle"
    WAITING_FOR_PHONE = "waiting_for_phone"
    WAITING_IN_QUEUE = "waiting_in_queue"
    WAITING_FOR_PHOTO = "waiting_for_photo"
    WAITING_FOR_SUPPORT_MESSAGE = "waiting_for_support_message"
    WAITING_FOR_ADMIN_REPLY = "waiting_for_admin_reply"

def load_environment():
    """Загрузка переменных окружения"""
    load_dotenv()
    admin_ids = os.getenv('ADMIN_IDS', '').split(',')
    admin_ids = [int(admin_id) for admin_id in admin_ids if admin_id.strip().isdigit()]
    return {
        'BOT_TOKEN': os.getenv('BOT_TOKEN'),
        'ADMIN_IDS': admin_ids,
        'GROUP_LINK': "https://t.me/+0KppidSPsRFmYmUx",
        'WEBHOOK_URL': os.getenv('WEBHOOK_URL'),
        'PORT': os.getenv('PORT')
    }