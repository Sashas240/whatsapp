import os
import json
import re
from datetime import datetime

def load_history(db_file):
    """Загрузка истории из файла"""
    try:
        if os.path.exists(db_file):
            with open(db_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                phone_history = data.get('phone_history', {})
                # Конвертируем ключи обратно в int
                return {int(k): v for k, v in phone_history.items()}
    except Exception as e:
        return {}

def save_history(db_file, phone_history):
    """Сохранение истории в файл"""
    try:
        data = {
            'phone_history': phone_history,
            'last_updated': datetime.now().isoformat()
        }
        with open(db_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        pass

def validate_russian_phone(phone: str) -> bool:
    """Проверка корректности российского номера телефона"""
    # Проверяем, что строка не пустая
    if not phone.strip():
        return False
    
    # Проверяем наличие букв (если есть буквы - невалидный)
    if re.search(r'[а-яёА-ЯЁa-zA-Z]', phone):
        return False
    
    # Удаляем все символы кроме цифр и +
    phone_clean = re.sub(r'[^\d+]', '', phone)
    
    # Удаляем + для подсчета цифр
    phone_digits = re.sub(r'\D', '', phone_clean)
    
    # Проверяем российские номера
    if phone_digits.startswith('8') and len(phone_digits) == 11:
        return True
    elif phone_digits.startswith('7') and len(phone_digits) == 11:
        return True
    elif phone_clean.startswith('+7') and len(phone_digits) == 11:
        return True
    
    return False