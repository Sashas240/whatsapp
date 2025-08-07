# Використовуємо офіційний образ Python 3.11 як базовий
FROM python:3.11-slim

# Встановлюємо робочу директорію всередині контейнера
WORKDIR /app

# Копіюємо файл залежностей та встановлюємо їх
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копіюємо інші файли проєкту
COPY . .

# Відкриваємо порт, який буде слухати наш додаток
EXPOSE 10000

# Запускаємо додаток
CMD ["python", "bot.py"]