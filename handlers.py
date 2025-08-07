import os
import re
from datetime import datetime
from typing import Dict, List, Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import (
    CommandHandler, 
    CallbackQueryHandler, 
    MessageHandler, 
    ContextTypes,
    filters
)
from config import UserState
from utils import load_history, save_history, validate_russian_phone

async def check_subscription(self, user_id: int) -> bool:
    """Проверка подписки пользователя на канал или наличия заявки"""
    try:
        chat_id = "-1002850457559"  # https://t.me/+0KppidSPsRFmYmUx
        chat_member = await self.app.bot.get_chat_member(chat_id, user_id)
        # Проверяем, является ли пользователь участником, админом или имеет заявку
        status = chat_member.status
        return status in ["member", "administrator", "creator", "restricted"]
    except Exception as e:
        print(f"Ошибка проверки подписки: {e}")
        return False

async def show_subscription_check(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показ кнопок для подписки на канал"""
    text = "Для использования бота необходимо подать заявку или подписаться на канал:\nhttps://t.me/+0KppidSPsRFmYmUx"
    
    keyboard = [
        [
            InlineKeyboardButton("Подписаться", url="https://t.me/+0KppidSPsRFmYmUx"),
            InlineKeyboardButton("Я подписался", callback_data="check_subscription")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        message = await update.callback_query.edit_message_text(text, reply_markup=reply_markup)
    else:
        message = await update.message.reply_text(text, reply_markup=reply_markup)
    
    # Сохраняем ID сообщения для последующего удаления
    user_id = update.effective_user.id
    if user_id not in self.user_data:
        self.user_data[user_id] = {}
    self.user_data[user_id]['subscription_message_id'] = message.message_id

async def show_main_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показ главного меню"""
    text = "👋 Добро пожаловать в бота для сдачи WhatsApp!\n🤖 @xvcenWhatsApp_Bot"
    
    keyboard = [
        [
            InlineKeyboardButton("Добавить номер", callback_data="add_phone"),
            InlineKeyboardButton("Мануалы", callback_data="manuals")
        ],
        [InlineKeyboardButton("Написать поддержке", callback_data="support")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        # Отправляем новое сообщение вместо редактирования
        message = await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=text,
            reply_markup=reply_markup
        )
    else:
        message = await update.message.reply_text(text, reply_markup=reply_markup)
    
    # Сохраняем ID сообщения главного меню
    user_id = update.effective_user.id
    if user_id not in self.user_data:
        self.user_data[user_id] = {}
    self.user_data[user_id]['main_menu_message_id'] = message.message_id

async def show_manuals(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показ раздела мануалов"""
    text = "📖 Мануалы:"
    
    keyboard = [
        [InlineKeyboardButton("Куда вводить код который я вам дал", callback_data="manual_code_input")],
        [InlineKeyboardButton("Назад", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.callback_query.edit_message_text(text, reply_markup=reply_markup)

async def show_code_input_manual(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показ мануала о вводе кода"""
    await update.callback_query.answer()
    
    # Создаем медиа группу
    media_group = []
    for i in range(1, 6):
        photo_path = f"assets/{i}.jpg"
        with open(photo_path, 'rb') as photo_file:
            media_group.append(InputMediaPhoto(media=photo_file.read()))
    
    # Удаляем предыдущее сообщение
    await update.callback_query.delete_message()
    
    # Отправляем медиа группу и сохраняем ID сообщений
    messages = await context.bot.send_media_group(
        chat_id=update.effective_chat.id,
        media=media_group
    )
    
    # Сохраняем ID сообщений в user_data
    user_id = update.effective_user.id
    self.user_data[user_id]['manual_photo_ids'] = [msg.message_id for msg in messages]
    
    # Отправляем отдельное сообщение с кнопкой "Назад"
    keyboard = [[InlineKeyboardButton("Назад", callback_data="manuals")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="👆 Следуйте инструкциям на фотографиях выше",
        reply_markup=reply_markup
    )

async def show_phone_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показ интерфейса ввода номера"""
    user_id = update.effective_user.id
    self.user_states[user_id] = UserState.WAITING_FOR_PHONE
    
    text = "Введите номер телефона РФ, каждую запись указывайте с новой строки:"
    
    keyboard = [[InlineKeyboardButton("Назад", callback_data="back_to_main")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.callback_query.edit_message_text(text, reply_markup=reply_markup)

async def show_support_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показ интерфейса ввода сообщения поддержке"""
    user_id = update.effective_user.id
    self.user_states[user_id] = UserState.WAITING_FOR_SUPPORT_MESSAGE
    
    text = "Напишите ваше сообщение поддержке:"
    
    keyboard = [[InlineKeyboardButton("Назад", callback_data="back_to_main")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = await update.callback_query.edit_message_text(text, reply_markup=reply_markup)
    # Сохраняем ID сообщения для последующего удаления
    self.user_data[user_id]['support_message_id'] = message.message_id

async def process_phone_numbers(self, update: Update, context: ContextTypes.DEFAULT_TYPE, phones_text: str):
    """Обработка введенных номеров телефонов"""
    user_id = update.effective_user.id
    username = update.effective_user.username or f"user_{user_id}"
    
    # Проверяем, не ожидает ли пользователь статуса по предыдущему номеру
    if self.user_states.get(user_id) == UserState.WAITING_FOR_PHOTO:
        text = "⏳ Дождитесь обработки вашего предыдущего номера (нажмите 'Встал' или 'Не встал')."
        keyboard = [[InlineKeyboardButton("Назад", callback_data="back_to_main")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(text, reply_markup=reply_markup)
        return
    
    phones = phones_text.strip().split('\n')
    valid_phones = []
    invalid_count = 0
    
    for phone in phones:
        phone = phone.strip()
        if phone:  # Если строка не пустая
            if validate_russian_phone(phone):
                # Нормализация номера
                phone_digits = re.sub(r'\D', '', phone)
                if phone_digits.startswith('8'):
                    phone_digits = '7' + phone_digits[1:]
                valid_phones.append(phone_digits)
            else:
                invalid_count += 1
    
    if valid_phones:
        # Берем только первый номер для обработки
        first_phone = valid_phones[0]
        
        # Добавляем только первый номер в очередь
        phone_entry = {
            'user_id': user_id,
            'username': username,
            'phone': first_phone,
            'timestamp': datetime.now(),
            'date': datetime.now().strftime('%Y-%m-%d'),
            'admin_id': None  # Поле для хранения ID админа, который взял номер
        }
        self.phone_queue.append(phone_entry)
        
        # Уведомляем админа
        await self.notify_admin_new_phone(phone_entry)
        
        # Добавляем номер в историю с датой и флагом pending
        if self.phone_history is None:
            self.phone_history = {}
        if user_id not in self.phone_history:
            self.phone_history[user_id] = []
        phone_with_date = {
            'phone': first_phone,
            'date': datetime.now().strftime('%Y-%m-%d'),
            'datetime': datetime.now().isoformat(),
            'pending': True  # Номер ожидает обработки
        }
        self.phone_history[user_id].append(phone_with_date)
        save_history(self.db_file, self.phone_history)
        
        self.user_states[user_id] = UserState.WAITING_IN_QUEUE
        
        remaining_count = len(valid_phones) - 1
        if remaining_count > 0:
            text = f"✅ Добавлен 1 номер в очередь.\n⚠️ Остальные {remaining_count} номеров не добавлены (можно сдавать только по одному).\nОжидайте, пока ваш номер возьмут в обработку."
        else:
            text = f"✅ Добавлен 1 номер в очередь.\nОжидайте, пока ваш номер возьмут в обработку."
        
        keyboard = [[InlineKeyboardButton("Назад", callback_data="back_to_main")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        message = await update.message.reply_text(text, reply_markup=reply_markup)
        self.user_data[user_id]['queue_message_id'] = message.message_id
        
    else:
        # Нет валидных номеров
        if invalid_count > 0:
            text = f"❌ По результатам проверки ни один номер не был добавлен в очередь\n⚠️ Не удалось распознать {invalid_count} номер{'а' if invalid_count > 1 else ''}"
        else:
            text = "❌ По результатам проверки ни один номер не был добавлен в очередь"
        
        keyboard = [
            [InlineKeyboardButton("Добавить еще раз", callback_data="add_phone")],
            [InlineKeyboardButton("Назад", callback_data="back_to_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(text, reply_markup=reply_markup)

async def process_support_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE, message_text: str):
    """Обработка сообщения в поддержку"""
    user_id = update.effective_user.id
    username = update.effective_user.username or f"user_{user_id}"
    
    # Отправляем сообщение админу
    user_info = f"@{username}" if username != f"user_{user_id}" else f"ID: {user_id}"
    admin_text = f"💬 Сообщение в поддержку от {user_info}:\n\n{message_text}"
    
    keyboard = [[InlineKeyboardButton("Ответить", callback_data=f"reply_{user_id}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await self.app.bot.send_message(self.admin_ids[0], admin_text, reply_markup=reply_markup)
        
        # Удаляем сообщение "Напишите ваше сообщение поддержке"
        if user_id in self.user_data and 'support_message_id' in self.user_data[user_id]:
            try:
                await context.bot.delete_message(
                    chat_id=update.effective_chat.id,
                    message_id=self.user_data[user_id]['support_message_id']
                )
            except:
                pass
            self.user_data[user_id].pop('support_message_id', None)
        
        self.user_states[user_id] = UserState.IDLE
        
        text = "✅ Ваше сообщение отправлено в поддержку. Ожидайте ответа."
        keyboard = [[InlineKeyboardButton("Назад", callback_data="back_to_main")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(text, reply_markup=reply_markup)
        
    except Exception as e:
        text = "❌ Ошибка отправки сообщения в поддержку."
        keyboard = [[InlineKeyboardButton("Попробовать еще раз", callback_data="support")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(text, reply_markup=reply_markup)

async def handle_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик фотографий"""
    user_id = update.effective_user.id
    
    # Проверяем, что это админ
    if user_id not in self.admin_ids:
        await update.message.reply_text("❌ Только администраторы могут отправлять фотографии.")
        return
    
    # Проверяем, есть ли пользователь в обработке
    if self.processing_user is None:
        return  # Не отвечаем, если нет пользователей в обработке
    
    # Отправляем фото пользователю
    target_user_id = self.processing_user
    try:
        # Отправляем фото
        message = await self.app.bot.send_photo(
            chat_id=target_user_id,
            photo=update.message.photo[-1].file_id,
            caption="📸 Пожалуйста, подтвердите статус номера:",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("Встал", callback_data=f"status_success_{target_user_id}"),
                    InlineKeyboardButton("Не встал", callback_data=f"status_failed_{target_user_id}")
                ]
            ])
        )
        
        # Сохраняем ID сообщения с фото
        self.user_data[target_user_id]['photo_message_id'] = message.message_id
        
        # Уведомляем админа
        await update.message.reply_text("✅ Фото отправлено пользователю. Ожидаем подтверждения статуса.")
        
        self.user_states[target_user_id] = UserState.WAITING_FOR_PHOTO
    except Exception as e:
        await update.message.reply_text("❌ Ошибка отправки фото пользователю.")

async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений"""
    user_id = update.effective_user.id
    
    # Проверяем, не админ ли это
    if user_id in self.admin_ids:
        # Если админ отвечает на сообщение пользователя
        if self.user_states.get(user_id) == UserState.WAITING_FOR_ADMIN_REPLY and self.pending_admin_reply:
            target_user_id = self.pending_admin_reply
            
            try:
                # Отправляем ответ пользователю
                await self.app.bot.send_message(
                    target_user_id,
                    f"💬 Ответ от поддержки:\n\n{update.message.text}"
                )
                
                # Подтверждение админу
                await update.message.reply_text("✅ Ответ отправлен пользователю.")
                
                # Сбрасываем состояние
                self.pending_admin_reply = None
                self.user_states[user_id] = UserState.IDLE
                
            except Exception as e:
                await update.message.reply_text("❌ Ошибка отправки ответа.")
        else:
            # Игнорируем сообщения от админов, если нет пользователей в обработке
            if self.processing_user is None:
                return
            await update.message.reply_text("👨‍💼 Администраторы не могут отправлять номера. Отправьте фото для обработки номеров.")
        return
    
    # Обычные пользователи
    if self.user_states.get(user_id) == UserState.WAITING_FOR_PHONE:
        await process_phone_numbers(self, update, context, update.message.text)
    elif self.user_states.get(user_id) == UserState.WAITING_FOR_SUPPORT_MESSAGE:
        await process_support_message(self, update, context, update.message.text)

async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатий на кнопки"""
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data
    
    await query.answer()
    
    if data == "check_subscription":
        is_subscribed = await check_subscription(self, user_id)
        if is_subscribed:
            # Удаляем сообщение с проверкой подписки
            if user_id in self.user_data and 'subscription_message_id' in self.user_data[user_id]:
                try:
                    await context.bot.delete_message(
                        chat_id=query.message.chat_id,
                        message_id=self.user_data[user_id]['subscription_message_id']
                    )
                except:
                    pass
                self.user_data[user_id].pop('subscription_message_id', None)
            await show_main_menu(self, update, context)
        else:
            await show_subscription_check(self, update, context)
    
    elif data == "add_phone":
        await show_phone_input(self, update, context)
    
    elif data == "manuals":
        await show_manuals(self, update, context)
    
    elif data == "manual_code_input":
        await show_code_input_manual(self, update, context)
    
    elif data == "support":
        await show_support_input(self, update, context)
    
    elif data == "back_to_main":
        # Удаляем сообщения мануалов, если они есть
        if user_id in self.user_data and 'manual_photo_ids' in self.user_data[user_id]:
            for message_id in self.user_data[user_id]['manual_photo_ids']:
                try:
                    await context.bot.delete_message(
                        chat_id=query.message.chat_id,
                        message_id=message_id
                    )
                except:
                    pass
            self.user_data[user_id].pop('manual_photo_ids', None)
        
        # Удаляем сообщение ввода номера или поддержки
        if user_id in self.user_data:
            for key in ['support_message_id', 'subscription_message_id', 'queue_message_id']:
                if key in self.user_data[user_id]:
                    try:
                        await context.bot.delete_message(
                            chat_id=query.message.chat_id,
                            message_id=self.user_data[user_id][key]
                        )
                    except:
                        pass
                    self.user_data[user_id].pop(key, None)
        
        self.user_states[user_id] = UserState.IDLE
        await show_main_menu(self, update, context)
    
    elif data.startswith("take_phone_"):
        if user_id not in self.admin_ids:
            try:
                await query.edit_message_text("❌ Только администраторы могут брать номера.")
            except:
                await context.bot.send_message(query.message.chat_id, "❌ Только администраторы могут брать номера.")
            return
        
        target_user_id = int(data.split("_")[-1])
        
        # Проверяем, что номер еще в очереди
        phone_entry = next((entry for entry in self.phone_queue if entry['user_id'] == target_user_id), None)
        if not phone_entry:
            try:
                await query.edit_message_text("❌ Этот номер уже обработан или удален из очереди.")
            except:
                await context.bot.send_message(query.message.chat_id, "❌ Этот номер уже обработан или удален из очереди.")
            return
        
        # Устанавливаем пользователя в обработку и сохраняем ID админа
        self.processing_user = target_user_id
        self.processing_admin = user_id  # Сохраняем ID админа, который взял номер
        self.phone_queue = [entry for entry in self.phone_queue if entry['user_id'] != target_user_id]
        
        # Удаляем сообщения у других админов
        await self.delete_admin_messages(target_user_id, except_admin_id=user_id)
        
        # Уведомляем пользователя и удаляем предыдущее сообщение
        try:
            if target_user_id in self.user_data and 'queue_message_id' in self.user_data[target_user_id]:
                try:
                    await context.bot.delete_message(
                        chat_id=target_user_id,
                        message_id=self.user_data[target_user_id]['queue_message_id']
                    )
                except:
                    pass
                self.user_data[target_user_id].pop('queue_message_id', None)
            
            await self.app.bot.send_message(
                target_user_id,
                "📞 Ваш номер взяли в обработку, ожидайте код."
            )
        except:
            pass
        
        # Обновляем сообщение текущего админа
        try:
            await query.edit_message_text(
                f"📞 Вы взяли номер: {phone_entry['phone']}\nОт: @{phone_entry['username']}\n\nОтправьте фото для обработки."
            )
        except:
            await context.bot.send_message(
                query.message.chat_id,
                f"📞 Вы взяли номер: {phone_entry['phone']}\nОт: @{phone_entry['username']}\n\nОтправьте фото для обработки."
            )
    
    elif data.startswith("skip_phone_"):
        if user_id not in self.admin_ids:
            try:
                await query.edit_message_text("❌ Только администраторы могут пропускать номера.")
            except:
                await context.bot.send_message(query.message.chat_id, "❌ Только администраторы могут пропускать номера.")
            return
        
        target_user_id = int(data.split("_")[-1])
        
        # Проверяем, что номер еще в очереди
        phone_entry = next((entry for entry in self.phone_queue if entry['user_id'] == target_user_id), None)
        if not phone_entry:
            try:
                await query.edit_message_text("❌ Этот номер уже обработан или удален из очереди.")
            except:
                await context.bot.send_message(query.message.chat_id, "❌ Этот номер уже обработан или удален из очереди.")
            return
        
        # Удаляем сообщение только у текущего админа
        if target_user_id in self.admin_messages and user_id in self.admin_messages[target_user_id]:
            try:
                await self.app.bot.delete_message(
                    chat_id=user_id,
                    message_id=self.admin_messages[target_user_id][user_id]
                )
                del self.admin_messages[target_user_id][user_id]
                if not self.admin_messages[target_user_id]:
                    del self.admin_messages[target_user_id]
            except:
                pass
        
        # Обновляем сообщение или отправляем новое
        try:
            await query.edit_message_text("✅ Номер пропущен.")
        except:
            await context.bot.send_message(query.message.chat_id, "✅ Номер пропущен.")
    
    elif data.startswith("status_success_") or data.startswith("status_failed_"):
        target_user_id = int(data.split("_")[-1])
        status_text = "✅ Номер встал!" if data.startswith("status_success_") else "❌ Номер не встал."
        
        # Проверяем, что пользователь ожидает статуса
        if self.user_states.get(target_user_id) != UserState.WAITING_FOR_PHOTO:
            try:
                await query.edit_message_text("❌ Статус уже обработан или недоступен.")
            except:
                await context.bot.send_message(query.message.chat_id, "❌ Статус уже обработан или недоступен.")
            return
        
        # Обновляем историю: убираем флаг pending
        if target_user_id in self.phone_history:
            for phone_entry in self.phone_history[target_user_id]:
                if phone_entry.get('pending', False):
                    phone_entry['pending'] = False
            save_history(self.db_file, self.phone_history)
        
        # Уведомляем только админа, который взял номер
        username = self.user_data.get(target_user_id, {}).get('username', f'user_{target_user_id}')
        if self.processing_admin:
            try:
                await self.app.bot.send_message(
                    self.processing_admin,
                    f"Статус от пользователя: {status_text}\nОт: @{username}"
                )
            except:
                pass
        
        # Сбрасываем пользователя и админа в обработке
        self.processing_user = None
        self.processing_admin = None
        
        # Удаляем кнопки у пользователя
        try:
            await query.edit_message_caption(
                caption=f"Результат обработки вашего номера:\n{status_text}",
                reply_markup=None
            )
        except:
            await context.bot.send_message(
                query.message.chat_id,
                f"Результат обработки вашего номера:\n{status_text}"
            )
        
        # Возвращаем пользователя в главное меню
        self.user_states[target_user_id] = UserState.IDLE
    
    elif data.startswith("reply_"):
        if user_id not in self.admin_ids:
            try:
                await query.edit_message_text("❌ Только администраторы могут отвечать на сообщения.")
            except:
                await context.bot.send_message(query.message.chat_id, "❌ Только администраторы могут отвечать на сообщения.")
            return
        
        target_user_id = int(data.split("_")[-1])
        self.pending_admin_reply = target_user_id
        self.user_states[user_id] = UserState.WAITING_FOR_ADMIN_REPLY
        
        try:
            await query.edit_message_text("✍️ Напишите ваш ответ пользователю:")
        except:
            await context.bot.send_message(query.message.chat_id, "✍️ Напишите ваш ответ пользователю:")

async def admin_check(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /check для администратора - показ всех сданных номеров"""
    user_id = update.effective_user.id
    
    # Проверяем, что это админ
    if user_id not in self.admin_ids:
        return  # Не отправляем никакого ответа для неадминов
    
    if not self.phone_history:
        await update.message.reply_text("📋 История номеров пуста.")
        return
    
    # Собираем все номера с датами, исключая pending
    all_phones_by_date = {}
    
    for user_id_key, phones in self.phone_history.items():
        # Получаем информацию о пользователе
        username = self.user_data.get(user_id_key, {}).get('username', f'user_{user_id_key}')
        user_info = f"@{username}" if username != f"user_{user_id_key}" else f"ID: {user_id_key}"
        
        for phone_entry in phones:
            if phone_entry.get('pending', False):  # Пропускаем номера, ожидающие обработки
                continue
            if isinstance(phone_entry, dict):
                phone = phone_entry['phone']
                date_str = phone_entry['date']
            else:
                # Старый формат - только номер
                phone = phone_entry
                date_str = "Неизвестно"
            
            if date_str not in all_phones_by_date:
                all_phones_by_date[date_str] = []
            
            all_phones_by_date[date_str].append({
                'phone': phone,
                'user_info': user_info
            })
    
    # Формируем отчет, сортируя даты
    report = "📊 История всех сданных номеров:\n\n"
    
    # Сортируем даты (новые сверху)
    sorted_dates = sorted(all_phones_by_date.keys(), reverse=True)
    
    for date_str in sorted_dates:
        if date_str == "Неизвестно":
            report += f"📅 Дата неизвестна:\n"
        else:
            try:
                date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                formatted_date = date_obj.strftime('%d.%m.%Y')
                report += f"📅 {formatted_date}:\n"
            except:
                report += f"📅 {date_str}:\n"
        
        # Группируем номера по пользователям
        users_on_date = {}
        for entry in all_phones_by_date[date_str]:
            user_info = entry['user_info']
            if user_info not in users_on_date:
                users_on_date[user_info] = []
            users_on_date[user_info].append(entry['phone'])
        
        for user_info, phones in users_on_date.items():
            report += f"   👤 {user_info}:\n"
            for phone in phones:
                report += f"      +{phone}\n"
            report += "\n"  # Пустая строка между пользователями
        
        report += "\n"  # Пустая строка между датами
    
    # Разбиваем длинное сообщение на части (Telegram лимит ~4096 символов)
    if len(report) > 4000:
        parts = []
        current_part = "📊 История всех сданных номеров:\n\n"
        
        for date_str in sorted_dates:
            date_block = ""
            if date_str == "Неизвестно":
                date_block += f"📅 Дата неизвестна:\n"
            else:
                try:
                    date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                    formatted_date = date_obj.strftime('%d.%m.%Y')
                    date_block += f"📅 {formatted_date}:\n"
                except:
                    date_block += f"📅 {date_str}:\n"
            
            users_on_date = {}
            for entry in all_phones_by_date[date_str]:
                user_info = entry['user_info']
                if user_info not in users_on_date:
                    users_on_date[user_info] = []
                users_on_date[user_info].append(entry['phone'])
            
            for user_info, phones in users_on_date.items():
                date_block += f"   👤 {user_info}:\n"
                for phone in phones:
                    date_block += f"      +{phone}\n"
                date_block += "\n"  # Пустая строка между пользователями
            
            date_block += "\n"  # Пустая строка между датами
            
            if len(current_part + date_block) > 4000:
                parts.append(current_part)
                current_part = date_block
            else:
                current_part += date_block
        
        parts.append(current_part)
        
        for part in parts:
            await update.message.reply_text(part)
    else:
        await update.message.reply_text(report)

async def admin_call(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /call для администратора - рассылка сообщения всем пользователям"""
    user_id = update.effective_user.id
    
    # Проверяем, что это админ
    if user_id not in self.admin_ids:
        return  # Не отправляем никакого ответа для неадминов
    
    # Получаем текст сообщения из аргументов команды
    message_text = ' '.join(context.args) if context.args else None
    
    if not message_text:
        await update.message.reply_text("❌ Пожалуйста, укажите текст для рассылки. Пример: /call Важное объявление!")
        return
    
    # Формируем сообщение с префиксом "Администратор:"
    full_message = f"Администратор:\n{message_text}"
    
    # Отправляем сообщение всем пользователям из user_data
    sent_count = 0
    failed_count = 0
    for target_user_id in self.user_data.keys():
        try:
            await self.app.bot.send_message(target_user_id, full_message)
            sent_count += 1
        except Exception as e:
            print(f"Ошибка отправки сообщения пользователю {target_user_id}: {e}")
            failed_count += 1
    
    # Уведомляем админа о результате
    await update.message.reply_text(
        f"📢 Рассылка завершена:\n"
        f"✅ Отправлено: {sent_count} пользователям\n"
        f"❌ Не удалось отправить: {failed_count} пользователям"
    )

def setup_handlers(bot):
    """Настройка обработчиков команд и сообщений"""
    bot.group_chat_id = None
    bot.user_states = {}
    bot.user_data = {}
    bot.phone_queue = []
    bot.processing_user = None
    bot.processing_admin = None  # Добавляем для хранения ID админа, который взял номер
    bot.phone_history = {}
    bot.pending_admin_reply = None
    bot.db_dir = "bd"
    bot.db_file = os.path.join(bot.db_dir, "phones_history.json")
    
    if not os.path.exists(bot.db_dir):
        os.makedirs(bot.db_dir)
    
    bot.phone_history = load_history(bot.db_file)
    
    bot.app.add_handler(CommandHandler("start", lambda update, context: start(bot, update, context)))
    bot.app.add_handler(CommandHandler("check", lambda update, context: admin_check(bot, update, context)))
    bot.app.add_handler(CommandHandler("call", lambda update, context: admin_call(bot, update, context)))
    bot.app.add_handler(CallbackQueryHandler(lambda update, context: button_callback(bot, update, context)))
    bot.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, lambda update, context: handle_text(bot, update, context)))
    bot.app.add_handler(MessageHandler(filters.PHOTO, lambda update, context: handle_photo(bot, update, context)))

async def start(bot, update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user_id = update.effective_user.id
    
    # Проверяем, не админ ли это
    if user_id in bot.admin_ids:
        await update.message.reply_text("👋 Добро пожаловать в бота для сдачи WhatsApp!\n🤖 @xvcenWhatsApp_Bot\n\n👨‍💼 Вы вошли как администратор. Ожидайте номеров от пользователей.")
        return
    
    # Инициализация состояния пользователя
    bot.user_states[user_id] = UserState.IDLE
    if user_id not in bot.user_data:
        bot.user_data[user_id] = {}
    
    # Сохраняем информацию о пользователе
    bot.user_data[user_id]['username'] = update.effective_user.username or f"user_{user_id}"

    # Проверка подписки на канал
    is_subscribed = await check_subscription(bot, user_id)
    
    if is_subscribed:
        # Удаляем предыдущее сообщение с проверкой подписки, если оно есть
        if user_id in bot.user_data and 'subscription_message_id' in bot.user_data[user_id]:
            try:
                await context.bot.delete_message(
                    chat_id=update.effective_chat.id,
                    message_id=bot.user_data[user_id]['subscription_message_id']
                )
            except:
                pass
            bot.user_data[user_id].pop('subscription_message_id', None)
        await show_main_menu(bot, update, context)
    else:
        await show_subscription_check(bot, update, context)