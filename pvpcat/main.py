import asyncio
import random
import hashlib
import hmac
import secrets
import time
import os
import json
import logging
from functools import wraps
from datetime import datetime, timedelta
from telegram import (
    ReplyKeyboardMarkup,
    Update,
    Bot,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
    CallbackQueryHandler,
    ConversationHandler,
    CallbackContext
)

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)
PROMOCODES = {
    "NEWERA": {
        "reward": {"money": 1000000, "coins": 0},
        "max_uses": 100,
        "used": 0,
        "expires": None,
        "min_level": 0
    },
    "PVPBOT": {
        "reward": {"money": 1000000, "coins": 20},
        "max_uses": 100,
        "used": 0,
        "expires": None,
        "min_level": 0
    },
    "URARELEASE": {  # Заменили кириллицу на латиницу
        "reward": {"money": 20000000, "coins": 0},
        "max_uses": 100,
        "used": 0,
        "expires": None,
        "min_level": 0
    },
    "ADMINBEST": {  # Заменили кириллицу на латиницу
        "reward": {"money": 30000000, "coins": 5},
        "max_uses": 100,
        "used": 0,
        "expires": None,
        "min_level": 0
    }
}

# Загрузка данных админов
if os.path.exists('admins.json'):
    with open('admins.json', 'r') as f:
        saved_admins = json.load(f)
        for username, data in saved_admins.items():
            if username in ADMINS:
                ADMINS[username].update(data)

# ==================== КОНФИГУРАЦИЯ БЕЗОПАСНОСТИ ====================
SECRET_KEY = secrets.token_hex(32)
RATE_LIMIT = 3
BLACKLIST_TIME = 3600
SESSION_TIMEOUT = 8 * 3600

# Хранилища данных
request_log = {}
blacklist = {}
active_sessions = {}
user_warns = {}
banned_users = set()
user_data = {}
trade_offers = {}
active_trades = {}

# Администраторы
ADMINS = {
    'citic_at22_828': {  # Владелец
        'password_hash': hashlib.sha256('pvpcat1203930394944844838484'.encode()).hexdigest(),
        'telegram_id':7665179923,
        '2fa_secret': secrets.token_hex(16),
        'last_login': None,
        'failed_attempts': 0,
        'last_attempt': None,
        'level': 3  # Уровень доступа (3 - владелец)
    },
    'MINE638293': {  # Модератор
        'password_hash': hashlib.sha256('sashamix'.encode()).hexdigest(),
        'last_login': None,
        'failed_attempts': 0,
        'last_attempt': None,
        'level': 1  # Уровень доступа (1 - модератор)
    }
}
# Группа администраторов (публичная)
ADMIN_GROUP_ID = "-1002775661295"  # ID группы
ADMIN_GROUP_LINK = "https://t.me/tigr228585"  # Ссылка на публичную группу

# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================
async def setup_admin_group(bot: Bot):
    """Настройка группы администраторов"""
    global ADMIN_GROUP_ID
    
    try:
        # Пробуем подключиться по ID
        try:
            chat = await bot.get_chat(ADMIN_GROUP_ID)
            logging.info(f"Группа администраторов найдена по ID: {chat.title} (ID: {chat.id})")
            ADMIN_GROUP_ID = str(chat.id)  # Сохраняем как строку
            return True
        except Exception as e:
            logging.warning(f"Не удалось подключиться по ID, пробуем по ссылке: {str(e)}")
            
            # Пробуем подключиться по ссылке
            chat = await bot.get_chat(ADMIN_GROUP_LINK)
            ADMIN_GROUP_ID = str(chat.id)
            logging.info(f"Группа администраторов найдена по ссылке: {chat.title} (ID: {chat.id})")
            return True
            
    except Exception as e:
        logging.error(f"Ошибка настройки группы администраторов: {str(e)}")
        return False

async def send_admin_notification(context: ContextTypes.DEFAULT_TYPE, message: str, parse_mode: str = 'HTML') -> bool:
    """Отправляет уведомление в группу администраторов"""
    try:
        if not ADMIN_GROUP_ID:
            logging.warning("ADMIN_GROUP_ID не установен")
            return False
            
        await context.bot.send_message(
            chat_id=ADMIN_GROUP_ID,
            text=message,
            parse_mode=parse_mode
        )
        return True
    except Exception as e:
        logging.error(f"Ошибка при отправке в группу: {str(e)}")
        return False

def load_data():
    global user_data, banned_users, trade_offers, active_trades
    if os.path.exists('data.json'):
        with open('data.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            user_data = data.get('user_data', {})
            banned_users = set(data.get('banned_users', []))
            trade_offers = data.get('trade_offers', {})
            active_trades = data.get('active_trades', {})
            return data
    return {'user_data': {}, 'banned_users': [], 'trade_offers': {}, 'active_trades': {}}

def save_data(data=None):
    if data is None:
        data = {
            'user_data': user_data, 
            'banned_users': list(banned_users),
            'trade_offers': trade_offers,
            'active_trades': active_trades
        }
    with open('data.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def get_user_data(user_id):
    user_id = str(user_id)
    if user_id not in user_data:
        user_data[user_id] = {
            'balance': 100000,
            'coins': 0,
            'accountant_uses': 0,
            'last_accountant_date': None,
            'businesses': [],
            'last_taxi_time': None,
            'last_business_income': None,
            'username': None,
            'last_active': time.time(),
            'referral_code': secrets.token_hex(4),
            'referred_by': None,
            'referrals': [],
            'business_count': 0,
            'inventory': {
                'boxes': 0,
                'items': []
            },
            'used_promocodes': [],
            'promocode_used':0
        }
    return user_data[user_id]

def rate_limit_check(user_id):
    now = time.time()
    
    if user_id in blacklist:
        if now - blacklist[user_id] < BLACKLIST_TIME:
            return False
        del blacklist[user_id]
    
    if user_id in request_log:
        last_requests = [t for t in request_log[user_id] if now - t < 1]
        if len(last_requests) >= RATE_LIMIT:
            blacklist[user_id] = now
            log_security_event(f"User {user_id} rate limited and blacklisted")
            return False
        request_log[user_id].append(now)
    else:
        request_log[user_id] = [now]
    return True

def generate_csrf_token(user_id, session_token):
    return hmac.new(
        SECRET_KEY.encode(), 
        f"{user_id}:{session_token}".encode(), 
        hashlib.sha256
    ).hexdigest()

def verify_csrf_token(user_id, session_token, csrf_token):
    expected_token = generate_csrf_token(user_id, session_token)
    return hmac.compare_digest(expected_token, csrf_token)

def log_security_event(event):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open("security.log", "a") as f:
        f.write(f"[{timestamp}] {event}\n")

def parse_bet_amount(bet_str):
    bet_str = bet_str.lower().replace(',', '').replace(' ', '')
    
    k_count = 0
    while bet_str.endswith('к'):
        k_count += 1
        bet_str = bet_str[:-1]
    
    if k_count > 0:
        try:
            num_part = float(bet_str) if '.' in bet_str else int(bet_str)
            return int(num_part * (1000 ** k_count))
        except ValueError:
            return None
    
    multipliers = {
        'm': 1_000_000,
        'b': 1_000_000_000
    }
    
    for suffix, mult in multipliers.items():
        if bet_str.endswith(suffix):
            num_part = bet_str[:-len(suffix)]
            try:
                return int(float(num_part) * mult)
            except ValueError:
                return None
    
    try:
        return int(bet_str)
    except ValueError:
        return None

# ==================== КОНФИГУРАЦИЯ БИЗНЕСОВ ====================
BUSINESS_TYPES = {
    1: {
        "name": "Малый бизнес",
        "price": 5_000_000,
        "income": 30_000,
        "description": "Небольшой бизнес с стабильным доходом",
        "emoji": "🏪"
    },
    2: {
        "name": "Средний бизнес",
        "price": 20_000_000,
        "income": 70_000,
        "description": "Прибыльный бизнес с хорошим доходом",
        "emoji": "🏢"
    },
    3: {
        "name": "Крупный бизнес",
        "price": 100_000_000,
        "income": 300_000,
        "description": "Серьезное предприятие с высоким доходом",
        "emoji": "🏭"
    },
    4: {
        "name": "Премиум бизнес",
        "price": 500_000_000,
        "income": 1_000_000,
        "description": "Элитный бизнес с огромной прибылью",
        "emoji": "💎"
    }
}

# ==================== КОНФИГУРАЦИЯ БОКСОВ ====================
BOX_PRICE = 10  # Стоимость бокса в койнах
BOX_REWARDS = [
    {"min": 1_000_000, "max": 5_000_000, "chance": 40, "emoji": "🎁"},
    {"min": 5_000_001, "max": 10_000_000, "chance": 30, "emoji": "🎁"},
    {"min": 10_000_001, "max": 50_000_000, "chance": 20, "emoji": "🎁"},
    {"min": 50_000_001, "max": 100_000_000, "chance": 7, "emoji": "💎"},
    {"min": 100_000_001, "max": 500_000_000, "chance": 2.5, "emoji": "💎"},
    {"min": 500_000_001, "max": 1_000_000_000, "chance": 0.4, "emoji": "💰"},
    {"min": 1_000_000_001, "max": 10_000_000_000, "chance": 0.1, "emoji": "💰"}
]

def calculate_box_reward():
    total_chance = sum(reward["chance"] for reward in BOX_REWARDS)
    rand = random.uniform(0, total_chance)
    cumulative = 0
    
    for reward in BOX_REWARDS:
        cumulative += reward["chance"]
        if rand <= cumulative:
            amount = random.randint(reward["min"], reward["max"])
            return amount, reward["emoji"]
    
    return BOX_REWARDS[0]["min"], BOX_REWARDS[0]["emoji"]

# ==================== СОСТОЯНИЯ ДЛЯ ConversationHandler ====================
(
    AWAITING_PASSWORD,
    ADMIN_PANEL,
    AWAITING_USER_ID,
    AWAITING_AMOUNT,
    BET,
    BUY_BUSINESS,
    BUSINESS_NAME,
    TRADE_MENU,
    TRADE_CREATE,
    TRADE_OFFER,
    TRADE_ACCEPT,
    BOX_MENU,
    BOX_OPEN
) = range(13)

# ==================== КОМАНДЫ АДМИНИСТРАТОРА ====================
async def admin_login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user:
        await update.message.reply_text("⛔ Пользователь не найден!")
        return ConversationHandler.END
        
    await update.message.reply_text("🔑 Введите пароль администратора:")
    return AWAITING_PASSWORD

async def process_admin_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    password = update.message.text.strip()
    
    admin_data = ADMINS.get(user.username)
    if not admin_data:
        await update.message.reply_text("⛔ Ошибка доступа!")
        return ConversationHandler.END
        
    input_hash = hashlib.sha256(password.encode()).hexdigest()
    if not hmac.compare_digest(input_hash, admin_data['password_hash']):
        admin_data['failed_attempts'] += 1
        admin_data['last_attempt'] = time.time()
        remaining_attempts = 3 - admin_data['failed_attempts']
        
        if remaining_attempts > 0:
            await update.message.reply_text(
                f"❌ Неверный пароль! Осталось попыток: {remaining_attempts}"
            )
        else:
            await update.message.reply_text(
                "🔒 Слишком много неудачных попыток. Попробуйте через час."
            )
        return AWAITING_PASSWORD
        
    admin_data['failed_attempts'] = 0
    admin_data['last_login'] = time.time()
    
    session_token = secrets.token_hex(32)
    active_sessions[user.id] = {
        'session_token': session_token,
        'start_time': time.time(),
        'last_activity': time.time(),
        'username': user.username
    }
    
    await update.message.reply_text("✅ Успешный вход в админ-панель!")
    return await show_admin_panel(update, context)

async def show_admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user = update.effective_user
        session = active_sessions.get(user.id)
        
        if not session:
            await update.message.reply_text("⛔ Сессия истекла. Пожалуйста, войдите снова.")
            return ConversationHandler.END
        
        admin_data = ADMINS.get(user.username, {})
        admin_level = admin_data.get('level', 0)
        csrf_token = generate_csrf_token(user.id, session['session_token'])[:16]
        
        keyboard = [
            [
                InlineKeyboardButton("📊 Статистика", callback_data=f"adm:stats:{csrf_token}"),
                InlineKeyboardButton("👥 Пользователи", callback_data=f"adm:users:{csrf_token}")
            ]
        ]
        
        if admin_level >= 1:
            keyboard.append([
                InlineKeyboardButton("⚠️ Варн", callback_data=f"adm:warn:{csrf_token}"),
                InlineKeyboardButton("🔨 Бан", callback_data=f"adm:ban:{csrf_token}")
            ])
        
        if admin_level >= 2:
            keyboard.append([
                InlineKeyboardButton("🔓 Разбан", callback_data=f"adm:unban:{csrf_token}"),
                InlineKeyboardButton("📝 Логи", callback_data=f"adm:logs:{csrf_token}")
            ])
        
        if admin_level >= 3:
            keyboard.extend([
                [
                    InlineKeyboardButton("💰 Начислить", callback_data=f"adm:add:{csrf_token}"),
                    InlineKeyboardButton("➖ Снять", callback_data=f"adm:rem:{csrf_token}")
                ],
                [
                    InlineKeyboardButton("👑 Админы", callback_data=f"adm:admins:{csrf_token}")
                ]
            ])
        
        keyboard.append([
            InlineKeyboardButton("🔄 Обновить", callback_data=f"adm:ref:{csrf_token}"),
            InlineKeyboardButton("🔒 Выход", callback_data=f"adm:out:{csrf_token}")
        ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        level_names = {
            1: "Модератор",
            2: "Администратор",
            3: "Владелец"
        }
        
        message_text = (
            "👑 <b>Админ-панель</b>\n"
            f"👤 Пользователь: {user.username}\n"
            f"🛡 Уровень: {level_names.get(admin_level, 'Неизвестно')}\n"
            f"🕒 Активна до: {(datetime.now() + timedelta(seconds=SESSION_TIMEOUT)).strftime('%d.%m.%Y %H:%M')}"
        )
        
        if update.callback_query:
            await update.callback_query.edit_message_text(
                message_text,
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
        else:
            await update.message.reply_text(
                message_text,
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
            
    except Exception as e:
        logging.error(f"Error in show_admin_panel: {e}")
        if update.message:
            await update.message.reply_text("⚠️ Произошла ошибка при отображении админ-панели")
    
    return ADMIN_PANEL

async def admin_actions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    try:
        # Защита от действий с владельцем
        if query.data.startswith(('adm:ban:', 'adm:warn:')) and is_owner(int(query.data.split(':')[2])):
            await query.answer("⛔ Нельзя воздействовать на владельца!", show_alert=True)
            return ADMIN_PANEL
            
        # Остальная часть функции без изменений...
        data = query.data.split(':')
        if len(data) != 3:
            await query.edit_message_text("⚠️ Ошибка безопасности! Неверный формат callback_data.")
            return
        
        prefix, action, received_short_token = data
        
        if prefix != 'adm':
            await query.edit_message_text("⚠️ Неизвестное действие!")
            return
        
        user_id = query.from_user.id
        session = active_sessions.get(user_id)
        
        if not session:
            await query.edit_message_text("⛔ Сессия истекла. Пожалуйста, войдите снова.")
            return ConversationHandler.END
        
        admin_data = ADMINS.get(query.from_user.username, {})
        admin_level = admin_data.get('level', 0)
        
        full_token = generate_csrf_token(user_id, session['session_token'])
        expected_short_token = full_token[:16]
        
        if not hmac.compare_digest(expected_short_token, received_short_token):
            await query.edit_message_text("⚠️ Ошибка безопасности! Неверный CSRF токен.")
            return
        
        if action in ('ban', 'unban', 'warn') and admin_level < 1:
            await query.answer("⛔ Недостаточно прав!", show_alert=True)
            return
        if action in ('add', 'rem', 'admins') and admin_level < 3:
            await query.answer("⛔ Только для владельца!", show_alert=True)
            return

        if action == 'stats':
            total_users = len(user_data)
            active_users = sum(1 for u in user_data.values() if 'last_active' in u and time.time() - u['last_active'] < 86400)
            total_balance = sum(u.get('balance', 0) for u in user_data.values())
            total_coins = sum(u.get('coins', 0) for u in user_data.values())
            total_businesses = sum(u.get('business_count', 0) for u in user_data.values())
            total_referrals = sum(len(u.get('referrals', [])) for u in user_data.values())
            total_promocodes_used = sum(u.get('promocodes_used', 0) for u in user_data.values())
            
            stats_text = (
                f"📊 <b>Статистика бота</b>\n\n"
                f"👥 Всего пользователей: {total_users}\n"
                f"🟢 Активных за сутки: {active_users}\n"
                f"💰 Общий баланс: {total_balance:,} ₽\n"
                f"🪙 Всего койнов: {total_coins:,}\n"
                f"🏢 Всего бизнесов: {total_businesses}\n"
                f"📨 Всего рефералов: {total_referrals}\n"
                f"🎫 Использовано промокодов: {total_promocodes_used}\n"
                f"🔨 Забанено: {len(banned_users)}"
            )
            await query.edit_message_text(stats_text, parse_mode='HTML')
            return ADMIN_PANEL         
        elif action == 'users':
            active_users = sorted(
                [(uid, u) for uid, u in user_data.items() if 'last_active' in u],
                key=lambda x: x[1]['last_active'],
                reverse=True
            )[:10]
            
            users_text = "👥 <b>Последние активные пользователи</b>\n\n"
            for i, (uid, user) in enumerate(active_users, 1):
                username = user.get('username', 'N/A')
                last_active = datetime.fromtimestamp(user['last_active']).strftime('%d.%m %H:%M')
                referrals = len(user.get('referrals', []))
                businesses = user.get('business_count', 0)
                users_text += (
                    f"{i}. <code>{uid}</code> - @{username}\n"
                    f"   💰 {user.get('balance', 0):,} ₽ | 🪙 {user.get('coins', 0):,} | 🏢 {businesses} | 📨 {referrals} | 🕒 {last_active}\n\n"
                )
            await query.edit_message_text(users_text, parse_mode='HTML')
            return ADMIN_PANEL
            
        elif action in ('ban', 'unban', 'warn'):
            context.user_data['admin_action'] = action
            await query.edit_message_text(f"Введите ID пользователя для действия '{action}':")
            return AWAITING_USER_ID
            
        elif action == 'add':
            context.user_data['admin_action'] = 'add_money'
            await query.edit_message_text("Введите ID пользователя для начисления:")
            return AWAITING_USER_ID
            
        elif action == 'rem':
            context.user_data['admin_action'] = 'remove_money'
            await query.edit_message_text("Введите ID пользователя для снятия:")
            return AWAITING_USER_ID
            
        elif action == 'logs':
            try:
                with open("security.log", "r") as f:
                    logs = f.read()[-4000:]  # Последние ~4000 символов
                await query.edit_message_text(f"📝 Последние действия:\n<code>{logs}</code>", parse_mode='HTML')
            except Exception as e:
                await query.edit_message_text(f"❌ Ошибка чтения логов: {str(e)}")
            return ADMIN_PANEL
            
        elif action == 'admins':
            admins_text = "👑 Список администраторов:\n\n"
            for username, data in ADMINS.items():
                level = data.get('level', 0)
                level_name = {
                    1: "Модератор",
                    2: "Администратор",
                    3: "Владелец"
                }.get(level, "Неизвестно")
                last_login = datetime.fromtimestamp(data['last_login']).strftime('%d.%m.%Y %H:%M') if data.get('last_login') else "Никогда"
                admins_text += f"🔹 @{username} - {level_name} (последний вход: {last_login})\n"
            
            await query.edit_message_text(admins_text)
            return ADMIN_PANEL
            
        elif action == 'ref':
            return await show_admin_panel(update, context)
            
        elif action == 'out':
            user_id = query.from_user.id
            if user_id in active_sessions:
                del active_sessions[user_id]
            await query.edit_message_text("✅ Сессия завершена.")
            return ConversationHandler.END

    except Exception as e:
        logging.error(f"Error in admin_actions: {e}", exc_info=True)
        await query.edit_message_text("⚠️ Произошла ошибка при обработке запроса.")
        return ConversationHandler.END

async def process_user_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text
    admin = update.effective_user
    action = context.user_data.get('admin_action')
    
    try:
        target_user_id = int(user_input)
    except ValueError:
        await update.message.reply_text("❌ Неверный формат ID. Введите числовой ID пользователя.")
        return AWAITING_USER_ID
    
    # Защита владельца
    owner_id = ADMINS['citic_at22_828'].get('telegram_id')
    if str(target_user_id) == str(owner_id):
        await update.message.reply_text("⛔ Нельзя воздействовать на владельца бота!")
        log_security_event(f"Попытка {action} владельца админом @{admin.username}")
        return await show_admin_panel(update, context)
    
    target_user = get_user_data(target_user_id)
    if not target_user:
        await update.message.reply_text("❌ Пользователь не найден.")
        return AWAITING_USER_ID
    
    target_username = target_user.get('username', str(target_user_id))
    
    admin_data = ADMINS.get(admin.username, {})
    admin_level = admin_data.get('level', 0)
    
    if action == 'ban':
        if admin_level < 1:
            await update.message.reply_text("⛔ Недостаточно прав!")
            return await show_admin_panel(update, context)
            
        # Дополнительная проверка для админов
        target_admin_data = None
        for admin_username, admin_info in ADMINS.items():
            if admin_info.get('telegram_id') == target_user_id:
                target_admin_data = admin_info
                break
        
        if target_admin_data:
            if target_admin_data['level'] >= admin_level:
                await update.message.reply_text("⛔ Вы не можете забанить администратора равного или выше уровня!")
                return await show_admin_panel(update, context)
                
        if target_user_id in banned_users:
            await update.message.reply_text("⚠️ Этот пользователь уже забанен.")
        else:
            banned_users.add(target_user_id)
            await update.message.reply_text(f"✅ Пользователь {target_username} забанен.")
            
            notification_text = (
                f"🔨 <b>Администратор @{admin.username} забанил пользователя</b>\n"
                f"👤 Пользователь: @{target_username}\n"
                f"🆔 ID: <code>{target_user_id}</code>\n"
                f"🕒 Время: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
            )
            await send_admin_notification(context, notification_text)
            
            save_data()
        
        return await show_admin_panel(update, context) 
            
    elif action == 'unban':
        if admin_level < 1:
            await update.message.reply_text("⛔ Недостаточно прав!")
            return await show_admin_panel(update, context)
            
        if target_user_id not in banned_users:
            await update.message.reply_text("⚠️ Этот пользователь не забанен.")
        else:
            banned_users.remove(target_user_id)
            await update.message.reply_text(f"✅ Пользователь {target_username} разбанен.")
            
            notification_text = (
                f"🔓 <b>Администратор @{admin.username} разбанил пользователя</b>\n"
                f"👤 Пользователь: @{target_username}\n"
                f"🆔 ID: <code>{target_user_id}</code>\n"
                f"🕒 Время: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
            )
            await send_admin_notification(context, notification_text)
            
            save_data()
            
    elif action == 'warn':
        if admin_level < 1:
            await update.message.reply_text("⛔ Недостаточно прав!")
            return await show_admin_panel(update, context)
            
        warn_count = user_warns.get(target_user_id, 0) + 1
        user_warns[target_user_id] = warn_count
        
        await update.message.reply_text(
            f"⚠️ Пользователю @{target_username} выдано предупреждение\n"
            f"Всего предупреждений: {warn_count}/3"
        )
        
        notification_text = (
            f"⚠️ <b>Администратор @{admin.username} выдал предупреждение</b>\n"
            f"👤 Пользователь: @{target_username}\n"
            f"🆔 ID: <code>{target_user_id}</code>\n"
            f"📊 Всего предупреждений: {warn_count}/3\n"
            f"🕒 Время: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
        )
        await send_admin_notification(context, notification_text)
        
        if warn_count >= 3:
            banned_users.add(target_user_id)
            await update.message.reply_text(
                f"🚨 Пользователь @{target_username} получил 3 предупреждения и был автоматически забанен!"
            )
            
            ban_notification = (
                f"🚨 <b>Автоматический бан за 3 предупреждения</b>\n"
                f"👤 Пользователь: @{target_username}\n"
                f"🆔 ID: <code>{target_user_id}</code>\n"
                f"⚠️ Последнее предупреждение от: @{admin.username}\n"
                f"🕒 Время: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
            )
            await send_admin_notification(context, ban_notification)
            
            save_data()
    
    elif action in ('add_money', 'remove_money'):
        context.user_data['target_user'] = target_user_id
        await update.message.reply_text(
            "Введите сумму (для койнов добавьте 'c' в конце):\n"
            "Примеры:\n"
            "1000000 - 1 миллион денег\n"
            "50c - 50 койнов"
        )
        return AWAITING_AMOUNT
    
    return await show_admin_panel(update, context)

async def process_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    amount_str = update.message.text
    user_id = context.user_data['target_user']
    action = context.user_data.get('admin_action')
    admin = update.effective_user
    
    try:
        # Проверяем, указана ли валюта (койны через "c" в конце)
        if amount_str.lower().endswith('c'):
            is_coins = True
            amount_str = amount_str[:-1].strip()
        else:
            is_coins = False
            
        amount = parse_bet_amount(amount_str)
        if not amount or amount <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text(
            "❌ Неверный формат суммы. Введите положительное число.\n"
            "Для койнов добавьте 'c' в конце (например: 100c)"
        )
        return AWAITING_AMOUNT
    
    user = get_user_data(user_id)
    username = user.get('username', str(user_id))
    
    # Инициализация coins, если их нет
    if 'coins' not in user:
        user['coins'] = 0
    
    if action == 'add_money':
        if is_coins:
            user['coins'] += amount
            operation = "начислено койнов"
            operation_emoji = "➕🪙"
            currency = "койнов"
        else:
            user['balance'] += amount
            operation = "начислено денег"
            operation_emoji = "➕💰"
            currency = "₽"
            
    elif action == 'remove_money':
        if is_coins:
            if user.get('coins', 0) < amount:
                await update.message.reply_text("❌ У пользователя недостаточно койнов.")
                return AWAITING_AMOUNT
            user['coins'] -= amount
            operation = "списано койнов"
            operation_emoji = "➖🪙"
            currency = "койнов"
        else:
            if user['balance'] < amount:
                await update.message.reply_text("❌ У пользователя недостаточно средств.")
                return AWAITING_AMOUNT
            user['balance'] -= amount
            operation = "списано денег"
            operation_emoji = "➖💰"
            currency = "₽"
    
    save_data()
    
    await update.message.reply_text(
        f"✅ {operation.capitalize()}: {amount:,} {currency} пользователю @{username}\n"
        f"Новый баланс: {user['balance']:,} ₽ | Койны: {user.get('coins', 0)}"
    )
    
    if amount >= (1_000_000 if not is_coins else 100):
        notification_text = (
            f"{operation_emoji} <b>Администратор @{admin.username} {operation}</b>\n"
            f"👤 Пользователь: @{username}\n"
            f"🆔 ID: <code>{user_id}</code>\n"
            f"💰 Сумма: {amount:,} {currency}\n"
            f"💳 Новый баланс: {user['balance']:,} ₽ | Койны: {user.get('coins', 0)}\n"
            f"🕒 Время: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
        )
        await send_admin_notification(context, notification_text)
    
    return await show_admin_panel(update, context)

# ==================== ОСНОВНЫЕ КОМАНДЫ ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    if user_id in banned_users:
        await update.message.reply_text("⛔ Вы заблокированы и не можете использовать бота.")
        return
        
    user = get_user_data(user_id)
    username = update.message.from_user.username or update.message.from_user.full_name
    user['username'] = username
    user['last_active'] = time.time()
    
    if 'referral_code' not in user:
        user['referral_code'] = secrets.token_hex(4)
    
    if context.args and context.args[0].startswith('ref_'):
        ref_code = context.args[0][4:]
        if not user.get('referred_by'):
            for uid, u_data in user_data.items():
                if u_data.get('referral_code') == ref_code and int(uid) != user_id:
                    if 'last_active' not in user or (time.time() - user['last_active']) > 86400 * 30:
                        user['referred_by'] = int(uid)
                        u_data.setdefault('referrals', []).append(user_id)
                        u_data['coins'] += 5
                        user['coins'] += 2
                        await update.message.reply_text(
                            f"🎉 Вы зарегистрировались по реферальной ссылке пользователя @{u_data.get('username', 'unknown')}!\n"
                            f"🪙 Вы получили 2 койна, а пригласивший вас получил 5 койнов!"
                        )
                        save_data()
                    break
    
    business_count = user.get('business_count', 0)
    business_income = sum(BUSINESS_TYPES.get(i, {}).get('income', 0) for i in range(1, business_count + 1))
    
    welcome_text = (
        f"👋 Привет, {username}!\n\n"
        f"💰 Твой баланс: {user['balance']:,} ₽\n"
        f"🪙 Твои койны: {user.get('coins', 0)}\n"
        f"🏢 Бизнесы: {business_count} (Доход: {business_income:,} ₽/час)\n"
        f"📨 Рефералов: {len(user.get('referrals', []))}\n\n"
        f"🔗 Твоя реферальная ссылка: https://t.me/{(await context.bot.get_me()).username}?start=ref_{user['referral_code']}\n"
        f"🪙 За каждого приглашенного друга ты получишь 5 койнов!"
    )
    
    keyboard = [
        ["🎰 Казино", "💼 Работа"],
        ["🏢 Бизнесы", "📊 Профиль"],
        ["💰 Баланс", "🏆 Топы"],
        ["🔄 Трейды", "🎁 Боксы"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(welcome_text, reply_markup=reply_markup)
    save_data()
    return ConversationHandler.END
    
async def set_nick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id in banned_users:
        await update.message.reply_text("⛔ Вы заблокированы и не можете использовать бота.")
        return
        
    if not context.args:
        await update.message.reply_text("Использование: /set_nick [новый ник]")
        return
    
    new_nick = ' '.join(context.args)
    if len(new_nick) > 25:
        await update.message.reply_text("❌ Ник не может быть длиннее 25 символов!")
        return
    
    user = get_user_data(user_id)
    user['username'] = new_nick
    save_data()
    
    await update.message.reply_text(
        f"✅ Ваш ник успешно изменен на: {new_nick}\n"
        f"Теперь другие игроки смогут находить вас по этому нику."
    )

async def pay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id in banned_users:
        await update.message.reply_text("⛔ Вы заблокированы и не можете использовать бота.")
        return
        
    user = get_user_data(user_id)
    
    if len(context.args) != 2:
        await update.message.reply_text("Использование: /pay @username сумма")
        return
    
    recipient_username = context.args[0].lstrip('@')
    try:
        amount = int(context.args[1])
        if amount <= 0:
            await update.message.reply_text("Сумма должна быть положительной!")
            return
    except ValueError:
        await update.message.reply_text("Пожалуйста, укажите корректную сумму!")
        return
    
    if amount > user['balance']:
        await update.message.reply_text("Недостаточно средств на балансе!")
        return
    
    recipient = None
    for uid, u_data in user_data.items():
        if u_data.get('username', '').lower() == recipient_username.lower() or uid == recipient_username:
            recipient = u_data
            break
    
    if not recipient:
        await update.message.reply_text("Пользователь не найден!")
        return
        
    if int(uid) == user_id:
        await update.message.reply_text("Нельзя переводить самому себе!")
        return
    
    user['balance'] -= amount
    recipient['balance'] += amount
    
    await update.message.reply_text(
        f"✅ Вы перевели {amount:,} ₽ пользователю @{recipient_username}\n"
        f"Ваш баланс: {user['balance']:,} ₽"
    )
    
    try:
        await context.bot.send_message(
            chat_id=int(uid),
            text=f"💸 Вам перевели {amount:,} ₽ от @{user['username']}\n"
                 f"Ваш баланс: {recipient['balance']:,} ₽"
        )
    except:
        pass
    
    save_data()
async def promo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id in banned_users:
        await update.message.reply_text("⛔ Вы заблокированы и не можете использовать бота.")
        return
        
    if not context.args:
        await update.message.reply_text("Использование: /promo [код]")
        return
    
    promo_code = context.args[0].upper()
    user = get_user_data(user_id)
    
    # Автоматическая замена кириллицы на латиницу (если нужно)
    promo_code = promo_code.replace("ПВПБОТ", "PVPBOT")
    
    # Проверяем существование промокода
    if promo_code not in PROMOCODES:
        await update.message.reply_text("❌ Неверный промокод!")
        return
    
    promo_data = PROMOCODES[promo_code]
    
    # Проверка срока действия
    if promo_data['expires']:
        try:
            expire_date = datetime.strptime(promo_data['expires'], "%Y-%m-%d").date()
            if datetime.now().date() > expire_date:
                await update.message.reply_text("❌ Промокод истек!")
                return
        except ValueError as e:
            print(f"Ошибка в формате даты промокода {promo_code}: {e}")
            await update.message.reply_text("❌ Ошибка в промокоде (неправильная дата)")
            return
    
    # Остальные проверки (уровень, лимит и т.д.)
    user_level = user.get('level', 0)
    if user_level < promo_data.get('min_level', 0):
        await update.message.reply_text("❌ Ваш уровень слишком низок для этого промокода!")
        return
    
    if promo_data['used'] >= promo_data['max_uses']:
        await update.message.reply_text("❌ Лимит использования этого промокода исчерпан!")
        return
    
    # Начисляем награду
    reward = promo_data['reward']
    if 'money' in reward:
        user['balance'] += reward['money']
    if 'coins' in reward:
        user['coins'] += reward.get('coins', 0)
    
    # Обновляем статистику
    promo_data['used'] += 1
    user.setdefault('used_promocodes', []).append(promo_code)
    user['promocode_used'] = user.get('promocode_used', 0) + 1
    
    save_data()
    
    # Формируем сообщение
    reward_text = []
    if 'money' in reward:
        reward_text.append(f"{reward['money']:,} ₽")
    if 'coins' in reward:
        reward_text.append(f"{reward['coins']} койнов")
    
    await update.message.reply_text(
        f"🎉 Промокод активирован!\n"
        f"Вы получили: {', '.join(reward_text)}\n"
        f"💰 Ваш баланс: {user['balance']:,} ₽\n"
        f"🪙 Ваши койны: {user.get('coins', 0)}"
    )

async def casino(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id in banned_users:
        await update.message.reply_text("⛔ Вы заблокированы и не можете использовать бота.")
        return
        
    await update.message.reply_text(
        "🎰 Используйте формат: рул [цвет/чет/зеро] [ставка]\n"
        "Доступные варианты:\n"
        "- чёрное/красное (x2)\n"
        "- чётное/нечётное (x2)\n"
        "- зеро (x36, шанс 1/37)\n\n"
        "Примеры:\n"
        "рул чёрное 100к\n"
        "рул зеро 1кк (при выигрыше: 36кк)\n"
        "рул чет 500ккк (500ккк = 500 миллиардов)\n\n"
        "Сокращения:\n"
        "к = 1,000\nкк = 1,000,000\nккк = 1,000,000,000\n"
        "кккк = 1,000,000,000,000\nккккк = 1,000,000,000,000,000\n\n"
        "Для отмены введите /cancel"
    )
    return BET

async def process_bet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id in banned_users:
        await update.message.reply_text("⛔ Вы заблокированы и не можете использовать бота.")
        return ConversationHandler.END
        
    user = get_user_data(user_id)
    user['last_active'] = time.time()
    
    if not user.get('username'):
        await update.message.reply_text(
            "❌ У вас не установлен никнейм!\n"
            "Пожалуйста, установите ник командой /set_nick [ваш ник]\n"
            "Это нужно для отображения в рейтингах и при взаимодействиях с другими игроками."
        )
        return ConversationHandler.END
    
    message_text = update.message.text
    bet_amount = None
    
    if message_text.lower().startswith('рул '):
        parts = message_text.split()[1:]
        
        if len(parts) < 2:
            await update.message.reply_text("❌ Неверный формат. Используйте: рул [цвет/чет/зеро] [ставка]")
            return BET
            
        bet_type = parts[0].lower()
        bet_amount_str = ' '.join(parts[1:])
        
        valid_bet_types = {
            'чёрное': 'black', 'черное': 'black', 'чер': 'black',
            'красное': 'red', 'крас': 'red', 'кра': 'red',
            'чётное': 'even', 'четное': 'even', 'чет': 'even',
            'нечётное': 'odd', 'нечетное': 'odd', 'нечет': 'odd',
            'зеро': 'zero', 'zero': 'zero', '0': 'zero'
        }
        
        if bet_type not in valid_bet_types:
            await update.message.reply_text(
                "❌ Неверный тип ставки. Доступные варианты:\n"
                "- чёрное/красное\n"
                "- чётное/нечётное\n"
                "- зеро"
            )
            return BET
            
        bet_type = valid_bet_types[bet_type]
        bet_amount = parse_bet_amount(bet_amount_str)
        
        if not bet_amount or bet_amount <= 0:
            await update.message.reply_text("❌ Неверная сумма ставки!")
            return BET
    
    if not bet_amount:
        await update.message.reply_text("❌ Неверный формат ставки!")
        return BET
    
    if bet_amount > user['balance']:
        await update.message.reply_text("❌ Недостаточно средств на балансе!")
        return BET
    
    username = user['username']
    win_number = random.randint(0, 36)
    is_red = win_number in {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}
    is_black = win_number in {2, 4, 6, 8, 10, 11, 13, 15, 17, 20, 22, 24, 26, 28, 29, 31, 33, 35}
    is_even = win_number % 2 == 0 and win_number != 0
    is_odd = win_number % 2 == 1
    is_zero = win_number == 0
    
    win = False
    multiplier = 1
    result_text = f"🎲 Игрок: @{username}\nВыпало: {win_number} "
    
    if is_zero:
        result_text += "(зеро)"
        if bet_type == 'zero':
            win = True
            multiplier = 36
    elif bet_type == 'black' and is_black:
        win = True
        multiplier = 2
        result_text += "(чёрное)"
    elif bet_type == 'red' and is_red:
        win = True
        multiplier = 2
        result_text += "(красное)"
    elif bet_type == 'even' and is_even:
        win = True
        multiplier = 2
        result_text += "(чётное)"
    elif bet_type == 'odd' and is_odd:
        win = True
        multiplier = 2
        result_text += "(нечётное)"
    else:
        win = False
        if is_red:
            result_text += "(красное)"
        elif is_black:
            result_text += "(чёрное)"
    
    if win:
        win_amount = bet_amount * multiplier
        user['balance'] += win_amount
        result_text += (
            f"\n🎉 Поздравляем! Вы выиграли {win_amount:,} ₽ (x{multiplier})\n"
            f"💰 Ваш баланс: {user['balance']:,} ₽"
        )
    else:
        user['balance'] -= bet_amount
        result_text += (
            f"\n😢 К сожалению, вы проиграли {bet_amount:,} ₽\n"
            f"💰 Ваш баланс: {user['balance']:,} ₽"
        )
    
    await update.message.reply_text(result_text)
    save_data()
    return ConversationHandler.END

async def work_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id in banned_users:
        await update.message.reply_text("⛔ Вы заблокированы и не можете использовать бота.")
        return
        
    user = get_user_data(user_id)
    user['last_active'] = time.time()
        
    keyboard = [
        [InlineKeyboardButton("🚕 Таксист", callback_data="work_taxi")],
        [InlineKeyboardButton("📊 Бухгалтер", callback_data="work_accountant")],
        [InlineKeyboardButton("👷 Строитель", callback_data="work_builder")],
        [InlineKeyboardButton("👨‍💼 Бизнесмен", callback_data="work_businessman")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "💼 Выберите профессию:",
        reply_markup=reply_markup
    )

async def work_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    if user_id in banned_users:
        await query.answer("⛔ Вы заблокированы", show_alert=True)
        return
        
    user = get_user_data(user_id)
    user['last_active'] = time.time()
    
    await query.answer()
    
    if query.data == "work_taxi":
        if user.get('last_taxi_time') and (datetime.now() - datetime.fromisoformat(user['last_taxi_time'])) < timedelta(minutes=5):
            await query.edit_message_text("⏳ Вы уже работали таксистом недавно. Подождите 5 минут.")
            return
        
        earnings = 20000
        user['balance'] += earnings
        user['last_taxi_time'] = datetime.now().isoformat()
        
        await query.edit_message_text(
            f"🚖 Вы завершили рейс и заработали {earnings:,} ₽!\n"
            f"Ваш баланс: {user['balance']:,} ₽"
        )
    
    elif query.data == "work_accountant":
        today = datetime.now().date()
        
        if user.get('last_accountant_date') != today.strftime('%Y-%m-%d'):
            user['accountant_uses'] = 0
            user['last_accountant_date'] = today.strftime('%Y-%m-%d')
        
        if user['accountant_uses'] >= 14:
            await query.edit_message_text("❌ Вы исчерпали лимит на сегодня (14 использований).")
            return
        
        earnings = random.randint(1_000_000, 4_000_000)
        user['balance'] += earnings
        user['accountant_uses'] += 1
        
        await query.edit_message_text(
            f"📈 Вы поработали бухгалтером и заработали {earnings:,} ₽!\n"
            f"Использовано сегодня: {user['accountant_uses']}/14\n"
            f"Ваш баланс: {user['balance']:,} ₽"
        )
    
    elif query.data == "work_builder":
        if user.get('last_builder_time') and (datetime.now() - datetime.fromisoformat(user['last_builder_time'])) < timedelta(minutes=30):
            await query.edit_message_text("⏳ Вы уже работали строителем недавно. Подождите 30 минут.")
            return
        
        earnings = random.randint(50_000, 150_000)
        user['balance'] += earnings
        user['last_builder_time'] = datetime.now().isoformat()
        
        await query.edit_message_text(
            f"👷 Вы завершили строительный проект и заработали {earnings:,} ₽!\n"
            f"Ваш баланс: {user['balance']:,} ₽"
        )
    
    elif query.data == "work_businessman":
        if user.get('last_businessman_time') and (datetime.now() - datetime.fromisoformat(user['last_businessman_time'])) < timedelta(hours=1):
            await query.edit_message_text("⏳ Вы уже работали бизнесменом недавно. Подождите 1 час.")
            return
        
        earnings = random.randint(500_000, 2_000_000)
        user['balance'] += earnings
        user['last_businessman_time'] = datetime.now().isoformat()
        
        await query.edit_message_text(
            f"👨‍💼 Вы провели успешную сделку и заработали {earnings:,} ₽!\n"
            f"Ваш баланс: {user['balance']:,} ₽"
        )
    
    save_data()

async def businesses_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user_data(user_id)
    
    keyboard = [
        [InlineKeyboardButton("📊 Мои бизнесы", callback_data="business_list")],
    ]
    
    for biz_id, biz_info in BUSINESS_TYPES.items():
        if biz_id > user.get('business_count', 0):
            keyboard.append([InlineKeyboardButton(
                f"🛒 Купить {biz_info['name']} - {biz_info['price']:,}₽",
                callback_data=f"business_buy_{biz_id}"
            )])
    
    if user.get('business_count', 0) > 0:
        last_income = datetime.fromisoformat(user['last_business_income']) if user.get('last_business_income') else None
        if not last_income or (datetime.now() - last_income) >= timedelta(hours=1):
            keyboard.append([InlineKeyboardButton("💰 Получить доход", callback_data="business_income")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        await update.callback_query.edit_message_text(
            "🏢 Управление бизнесами:",
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(
            "🏢 Управление бизнесами:",
            reply_markup=reply_markup
        )
    return BUY_BUSINESS

async def business_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user = get_user_data(user_id)
    
    if query.data == "business_list":
        business_count = user.get('business_count', 0)
        if business_count == 0:
            await query.edit_message_text(
                "❌ У вас пока нет бизнесов.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🛒 Купить бизнес", callback_data="business_show_buy")],
                    [InlineKeyboardButton("🔙 Назад", callback_data="business_back")]
                ])
            )
            return BUY_BUSINESS
            
        businesses_text = "📊 Ваши бизнесы:\n\n"
        for i in range(1, business_count + 1):
            biz_type = BUSINESS_TYPES.get(i, {})
            businesses_text += (
                f"{i}. {biz_type.get('emoji', '🏢')} {biz_type.get('name', 'Бизнес')}\n"
                f"   💰 Доход: {biz_type.get('income', 0):,} ₽/час\n\n"
            )
        
        keyboard = [
            [InlineKeyboardButton("🛒 Купить бизнес", callback_data="business_show_buy")],
            [InlineKeyboardButton("💰 Получить доход", callback_data="business_income")],
            [InlineKeyboardButton("🔙 Назад", callback_data="business_back")]
        ]
        
        await query.edit_message_text(
            businesses_text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return BUY_BUSINESS
    
    elif query.data == "business_show_buy":
        keyboard = []
        for biz_id, biz_info in BUSINESS_TYPES.items():
            if biz_id > user.get('business_count', 0):
                keyboard.append([InlineKeyboardButton(
                    f"🛒 {biz_info['emoji']} {biz_info['name']} - {biz_info['price']:,}₽",
                    callback_data=f"business_buy_{biz_id}"
                )])
        
        if not keyboard:
            await query.answer("У вас уже все бизнесы куплены!", show_alert=True)
            return await businesses_menu(update, context)
        
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="business_back")])
        
        await query.edit_message_text(
            "🛒 Выберите бизнес для покупки:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return BUY_BUSINESS
    
    elif query.data.startswith("business_buy_"):
        business_type = int(query.data.split('_')[2])
        biz_info = BUSINESS_TYPES.get(business_type)
        
        if not biz_info:
            await query.answer("❌ Ошибка: тип бизнеса не найден", show_alert=True)
            return await businesses_menu(update, context)
        
        if user['balance'] < biz_info['price']:
            await query.answer(f"❌ Недостаточно средств! Нужно {biz_info['price']:,} ₽", show_alert=True)
            return BUY_BUSINESS
        
        keyboard = [
            [InlineKeyboardButton("✅ Подтвердить покупку", callback_data=f"business_confirm_{business_type}")],
            [InlineKeyboardButton("❌ Отмена", callback_data="business_show_buy")]
        ]
        
        await query.edit_message_text(
            f"🛒 Подтвердите покупку бизнеса:\n\n"
            f"{biz_info['emoji']} {biz_info['name']}\n"
            f"💵 Стоимость: {biz_info['price']:,} ₽\n"
            f"💰 Доход: {biz_info['income']:,} ₽/час\n\n"
            f"Ваш баланс: {user['balance']:,} ₽",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return BUY_BUSINESS
    
    elif query.data.startswith("business_confirm_"):
        business_type = int(query.data.split('_')[2])
        biz_info = BUSINESS_TYPES.get(business_type)
        
        user['balance'] -= biz_info['price']
        user['business_count'] = max(user.get('business_count', 0), business_type)
        user['last_business_income'] = datetime.now().isoformat()
        
        await query.edit_message_text(
            f"✅ Вы успешно купили бизнес: {biz_info['emoji']} {biz_info['name']}\n"
            f"💰 Доход: {biz_info['income']:,} ₽/час\n"
            f"💳 Ваш баланс: {user['balance']:,} ₽"
        )
        save_data()
        return await businesses_menu(update, context)
    
    elif query.data == "business_income":
        last_income = datetime.fromisoformat(user['last_business_income']) if user.get('last_business_income') else None
        if last_income and (datetime.now() - last_income) < timedelta(hours=1):
            await query.answer("Доход можно собирать раз в час!", show_alert=True)
            return BUY_BUSINESS
        
        business_count = user.get('business_count', 0)
        if business_count == 0:
            await query.answer("У вас нет бизнесов!", show_alert=True)
            return BUY_BUSINESS
        
        business_income = 0
        for i in range(1, business_count + 1):
            business_income += BUSINESS_TYPES.get(i, {}).get('income', 0)
        
        user['balance'] += business_income
        user['last_business_income'] = datetime.now().isoformat()
        
        keyboard = [
            [InlineKeyboardButton("📊 Мои бизнесы", callback_data="business_list")],
            [InlineKeyboardButton("🛒 Купить бизнес", callback_data="business_show_buy")]
        ]
        
        await query.edit_message_text(
            f"💰 Вы получили {business_income:,} ₽ с ваших бизнесов!\n"
            f"Ваш баланс: {user['balance']:,} ₽",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        save_data()
        return BUY_BUSINESS
    
    elif query.data == "business_back":
        return await businesses_menu(update, context)
    
    return BUY_BUSINESS

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id in banned_users:
        await update.message.reply_text("⛔ Вы заблокированы и не можете использовать бота.")
        return
        
    user = get_user_data(user_id)
    user['last_active'] = time.time()
    business_count = user.get('business_count', 0)
    business_income = 0
    for i in range(1, business_count + 1):
        business_income += BUSINESS_TYPES.get(i, {}).get('income', 0)
    
    await update.message.reply_text(
        f"💰 Ваш баланс: {user['balance']:,} ₽\n"
        f"🪙 Ваши койны: {user.get('coins', 0)}\n"
        f"🏢 Бизнесы: {business_count} (Доход: {business_income:,} ₽/час)\n"
        f"📨 Рефералов: {len(user.get('referrals', []))}"
    )

async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id in banned_users:
        await update.message.reply_text("⛔ Вы заблокированы и не можете использовать бота.")
        return
        
    user = get_user_data(user_id)
    user['last_active'] = time.time()
    username = user.get('username') or update.message.from_user.username or update.message.from_user.full_name
    
    if 'referral_code' not in user:
        user['referral_code'] = secrets.token_hex(4)
        save_data()
    
    total_income = sum(BUSINESS_TYPES.get(i, {}).get('income', 0) for i in range(1, user.get('business_count', 0) + 1))
    
    first_seen = datetime.now()
    for action in ['last_taxi_time', 'last_business_income', 'last_accountant_date']:
        if user.get(action):
            action_time = datetime.fromisoformat(user[action]) if isinstance(user[action], str) else user[action]
            if action_time < first_seen:
                first_seen = action_time
    
    days_in_game = (datetime.now() - first_seen).days
    
    referred_by = ""
    if user.get('referred_by'):
        referrer = user_data.get(str(user['referred_by']), {})
        referred_by = f"\n👥 Пригласил: @{referrer.get('username', 'Unknown')}"
    
    await update.message.reply_text(
        f"📊 Профиль @{username}\n\n"
        f"💰 Баланс: {user['balance']:,} ₽\n"
        f"🪙 Койны: {user.get('coins', 0)}\n"
        f"🏢 Бизнесы: {user.get('business_count', 0)} (Доход: {total_income:,} ₽/час)\n"
        f"📨 Рефералов: {len(user.get('referrals', []))}\n"
        f"📅 В игре: {days_in_game} дней{referred_by}\n\n"
        f"🔗 Реферальная ссылка:\n"
        f"https://t.me/{(await context.bot.get_me()).username}?start=ref_{user['referral_code']}\n"
        f"🪙 За каждого приглашенного друга вы получите 5 койнов!"
    )

async def top_balance(update: Update, context: ContextTypes.DEFAULT_TYPE, is_callback=False):
    user_id = update.effective_user.id if is_callback else update.message.from_user.id
    if user_id in banned_users:
        if is_callback:
            await update.callback_query.message.reply_text("⛔ Вы заблокированы и не можете использовать бота.")
        else:
            await update.message.reply_text("⛔ Вы заблокированы и не можете использовать бота.")
        return
        
    all_users = sorted(
        [(uid, u_data) for uid, u_data in user_data.items() if int(uid) not in banned_users],
        key=lambda x: x[1]['balance'],
        reverse=True
    )
    
    if not all_users:
        if is_callback:
            await update.callback_query.message.reply_text("❌ Нет данных для топа.")
        else:
            await update.message.reply_text("❌ Нет данных для топа.")
        return
    
    user_position = None
    user_balance = None
    for i, (uid, data) in enumerate(all_users, 1):
        if int(uid) == user_id:
            user_position = i
            user_balance = data['balance']
            break
    
    top_text = "🏆 Топ 10 по балансу:\n\n"
    for i, (uid, user) in enumerate(all_users[:10], 1):
        username = user.get('username', uid)
        top_text += f"{i}. @{username} - {user['balance']:,} ₽\n"
    
    if user_position is not None:
        if user_position <= 10:
            top_text += f"\n🎯 Вы на {user_position} месте!"
        else:
            top_text += (
                f"\n🎯 Ваша позиция: {user_position}\n"
                f"💰 Ваш баланс: {user_balance:,} ₽\n"
                f"📊 Отставание от топ-10: {all_users[9][1]['balance'] - user_balance:,} ₽"
            )
    else:
        top_text += "\n❌ Ваш баланс не найден в статистике"
    
    if is_callback:
        await update.callback_query.edit_message_text(top_text)
    else:
        await update.message.reply_text(top_text)

async def top_referrals(update: Update, context: ContextTypes.DEFAULT_TYPE, is_callback=False):
    user_id = update.effective_user.id if is_callback else update.message.from_user.id
    if user_id in banned_users:
        if is_callback:
            await update.callback_query.message.reply_text("⛔ Вы заблокированы и не можете использовать бота.")
        else:
            await update.message.reply_text("⛔ Вы заблокированы и не можете использовать бота.")
        return
        
    all_users = sorted(
        [(uid, data) for uid, data in user_data.items() if int(uid) not in banned_users],
        key=lambda x: len(x[1].get('referrals', [])),
        reverse=True
    )
    
    if not all_users:
        if is_callback:
            await update.callback_query.message.reply_text("❌ Нет данных для топа.")
        else:
            await update.message.reply_text("❌ Нет данных для топа.")
        return
    
    user_position = None
    user_refs = None
    for i, (uid, data) in enumerate(all_users, 1):
        if int(uid) == user_id:
            user_position = i
            user_refs = len(data.get('referrals', []))
            break
    
    top_text = "🏆 Топ 10 по рефералам:\n\n"
    for i, (uid, user) in enumerate(all_users[:10], 1):
        username = user.get('username', uid)
        referrals = len(user.get('referrals', []))
        top_text += f"{i}. {username} - {referrals} рефералов\n"
    
    if user_position is not None:
        if user_position <= 10:
            top_text += f"\n🎯 Вы на {user_position} месте!"
        else:
            top_text += (
                f"\n🎯 Ваша позиция: {user_position}\n"
                f"📨 Ваши рефералы: {user_refs}\n"
                f"📊 Отставание от топ-10: {len(all_users[9][1].get('referrals', [])) - user_refs}"
            )
    else:
        top_text += "\n❌ Ваши данные не найдены в статистике"
    
    if is_callback:
        await update.callback_query.edit_message_text(top_text)
    else:
        await update.message.reply_text(top_text)

async def top_coins(update: Update, context: ContextTypes.DEFAULT_TYPE, is_callback=False):
    user_id = update.effective_user.id if is_callback else update.message.from_user.id
    if user_id in banned_users:
        if is_callback:
            await update.callback_query.message.reply_text("⛔ Вы заблокированы и не можете использовать бота.")
        else:
            await update.message.reply_text("⛔ Вы заблокированы и не можете использовать бота.")
        return
        
    all_users = sorted(
        [(uid, u_data) for uid, u_data in user_data.items() if int(uid) not in banned_users],
        key=lambda x: x[1].get('coins', 0),
        reverse=True
    )
    
    if not all_users:
        if is_callback:
            await update.callback_query.message.reply_text("❌ Нет данных для топа.")
        else:
            await update.message.reply_text("❌ Нет данных для топа.")
        return
    
    user_position = None
    user_coins = None
    for i, (uid, data) in enumerate(all_users, 1):
        if int(uid) == user_id:
            user_position = i
            user_coins = data.get('coins', 0)
            break
    
    top_text = "🏆 Топ 10 по койнам:\n\n"
    for i, (uid, user) in enumerate(all_users[:10], 1):
        username = user.get('username', uid)
        top_text += f"{i}. @{username} - {user.get('coins', 0)} койнов\n"
    
    if user_position is not None:
        if user_position <= 10:
            top_text += f"\n🎯 Вы на {user_position} месте!"
        else:
            top_text += (
                f"\n🎯 Ваша позиция: {user_position}\n"
                f"🪙 Ваши койны: {user_coins}\n"
                f"📊 Отставание от топ-10: {all_users[9][1].get('coins', 0) - user_coins}"
            )
    else:
        top_text += "\n❌ Ваши койны не найдены в статистике"
    
    if is_callback:
        await update.callback_query.edit_message_text(top_text)
    else:
        await update.message.reply_text(top_text)

async def handle_group_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat.type not in ('group', 'supergroup'):
        return
        
    user_id = update.message.from_user.id
    if user_id in banned_users:
        return
        
    text = update.message.text.lower()
    
    if text.startswith('рул '):
        try:
            user = get_user_data(user_id)
            if not user.get('username'):
                await update.message.reply_text(
                    "❌ У вас не установлен никнейм!\n"
                    "Пожалуйста, напишите боту в личные сообщения и установите ник командой /set_nick [ваш ник]"
                )
                return
            
            parts = text.split()
            if len(parts) < 3:
                await update.message.reply_text("❌ Неверный формат. Используйте: рул [цвет/чет/зеро] [ставка]")
                return
                
            bet_type = parts[1].lower()
            bet_amount_str = ' '.join(parts[2:])
            
            valid_bet_types = {
                'чёрное': 'black', 'черное': 'black', 'чер': 'black',
                'красное': 'red', 'крас': 'red', 'кра': 'red',
                'чётное': 'even', 'четное': 'even', 'чет': 'even',
                'нечётное': 'odd', 'нечетное': 'odd', 'нечет': 'odd',
                'зеро': 'zero', 'zero': 'zero', '0': 'zero'
            }
            
            if bet_type not in valid_bet_types:
                await update.message.reply_text(
                    "❌ Неверный тип ставки. Доступные варианты:\n"
                    "- чёрное/красное\n"
                    "- чётное/нечётное\n"
                    "- зеро"
                )
                return
                
            bet_type = valid_bet_types[bet_type]
            bet_amount = parse_bet_amount(bet_amount_str)
            
            if not bet_amount or bet_amount <= 0:
                await update.message.reply_text("❌ Неверная сумма ставки!")
                return
            
            if bet_amount > user['balance']:
                await update.message.reply_text("❌ Недостаточно средств на балансе!")
                return
            
            username = user['username']
            win_number = random.randint(0, 36)
            is_red = win_number in {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}
            is_black = win_number in {2, 4, 6, 8, 10, 11, 13, 15, 17, 20, 22, 24, 26, 28, 29, 31, 33, 35}
            is_even = win_number % 2 == 0 and win_number != 0
            is_odd = win_number % 2 == 1
            is_zero = win_number == 0
            
            win = False
            multiplier = 1
            result_text = f"🎲 Игрок: {username}\nВыпало: {win_number} "
            
            if is_zero:
                result_text += "(зеро)"
                if bet_type == 'zero':
                    win = True
                    multiplier = 36
            elif bet_type == 'black' and is_black:
                win = True
                multiplier = 2
                result_text += "(чёрное)"
            elif bet_type == 'red' and is_red:
                win = True
                multiplier = 2
                result_text += "(красное)"
            elif bet_type == 'even' and is_even:
                win = True
                multiplier = 2
                result_text += "(чётное)"
            elif bet_type == 'odd' and is_odd:
                win = True
                multiplier = 2
                result_text += "(нечётное)"
            else:
                win = False
                if is_red:
                    result_text += "(красное)"
                elif is_black:
                    result_text += "(чёрное)"
            
            if win:
                win_amount = bet_amount * multiplier
                user['balance'] += win_amount
                result_text += (
                    f"\n🎉 Поздравляем! Вы выиграли {win_amount:,} ₽ (x{multiplier})\n"
                    f"💰 Ваш баланс: {user['balance']:,} ₽"
                )
            else:
                user['balance'] -= bet_amount
                result_text += (
                    f"\n😢 К сожалению, вы проиграли {bet_amount:,} ₽\n"
                    f"💰 Ваш баланс: {user['balance']:,} ₽"
                )
            
            await update.message.reply_text(result_text)
            save_data()
            return
        except Exception as e:
            logging.error(f"Error processing bet in group: {e}")
            await update.message.reply_text("⚠️ Произошла ошибка при обработке ставки")
            return
    
    if text in ('я', 'топ'):
        if text == 'я':
            user = get_user_data(user_id)
            user['last_active'] = time.time()
            username = user.get('username') or update.message.from_user.username or update.message.from_user.full_name
            
            if not username:
                await update.message.reply_text(
                    "❌ У вас не установлен никнейм!\n"
                    "Пожалуйста, напишите боту в личные сообщения и установите ник командой /set_nick [ваш ник]"
                )
                return
                
            balance = user['balance']
            coins = user.get('coins', 0)
            
            all_users = sorted(
                [(uid, u_data) for uid, u_data in user_data.items() if int(uid) not in banned_users],
                key=lambda x: x[1]['balance'],
                reverse=True
            )
            
            position = None
            for i, (uid, _) in enumerate(all_users, 1):
                if int(uid) == user_id:
                    position = i
                    break
            
            response = (
                f"👋 Привет, {username}!\n"
                f"💰 Твой баланс: {balance:,} ₽\n"
                f"🪙 Твои койны: {coins}\n"
                f"🏆 Позиция в топе: {position or 'N/A'}\n\n"
                f"Доступные команды в группе:\n"
                f"• `рул чёрное 100к` - сделать ставку (x2)\n"
                f"• `рул зеро 1кк` - ставка на зеро (x36)\n"
                f"• `я` - показать свой профиль\n"
                f"• `топ` - показать топ игроков\n\n"
                f"Для полного функционала напишите боту в личные сообщения!"
            )
            
            await update.message.reply_text(response)
        
        elif text == 'топ':
            keyboard = [
                [InlineKeyboardButton("🏆 Топ по балансу", callback_data="top_balance")],
                [InlineKeyboardButton("📨 Топ по рефералам", callback_data="top_referrals")],
                [InlineKeyboardButton("🪙 Топ по койнам", callback_data="top_coins")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                "📊 Выберите тип топа:",
                reply_markup=reply_markup
            )

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Действие отменено.")
    return ConversationHandler.END

async def handle_work_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await work_menu(update, context)

async def handle_businesses_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await businesses_menu(update, context)

async def handle_balance_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await balance(update, context)

async def handle_profile_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await profile(update, context)

async def handle_casino_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await casino(update, context)

async def handle_tops_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id in banned_users:
        await update.message.reply_text("⛔ Вы заблокированы и не можете использовать бота.")
        return
        
    keyboard = [
        [InlineKeyboardButton("🏆 Топ по балансу", callback_data="top_balance")],
        [InlineKeyboardButton("📨 Топ по рефералам", callback_data="top_referrals")],
        [InlineKeyboardButton("🪙 Топ по койнам", callback_data="top_coins")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "📊 Выберите тип топа:",
        reply_markup=reply_markup
    )

async def top_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "top_balance":
        await top_balance(update, context, is_callback=True)
    elif query.data == "top_referrals":
        await top_referrals(update, context, is_callback=True)
    elif query.data == "top_coins":
        await top_coins(update, context, is_callback=True)

# ==================== ФУНКЦИИ ТРЕЙДОВ ====================
async def trade_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in banned_users:
        if update.callback_query:
            await update.callback_query.answer("⛔ Вы заблокированы", show_alert=True)
            return
        else:
            await update.message.reply_text("⛔ Вы заблокированы и не можете использовать бота.")
            return
        
    user = get_user_data(user_id)
    user['last_active'] = time.time()
    
    keyboard = [
        [InlineKeyboardButton("🔄 Создать трейд", callback_data="trade_create")],
        [InlineKeyboardButton("📨 Мои предложения", callback_data="trade_my_offers")],
        [InlineKeyboardButton("📥 Входящие предложения", callback_data="trade_incoming")],
        [InlineKeyboardButton("📊 Активные трейды", callback_data="trade_active")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        await update.callback_query.edit_message_text(
            "🔄 Меню трейдов:",
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(
            "🔄 Меню трейдов:",
            reply_markup=reply_markup
        )
    return TRADE_MENU

async def trade_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "trade_create":
        context.user_data.clear()
        context.user_data['trade_data'] = {
            'user_id': query.from_user.id,
            'offer': {'money': 0, 'coins': 0, 'items': []},
            'request': {'money': 0, 'coins': 0, 'items': []},
            'recipient': None
        }
        return await show_trade_create_menu(update, context)
    
    elif query.data == "trade_my_offers":
        return await show_my_trade_offers(update, context)
    
    elif query.data == "trade_incoming":
        return await show_incoming_trade_offers(update, context)
    
    elif query.data == "trade_active":
        return await show_active_trades(update, context)
    
    return TRADE_MENU

async def show_trade_create_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query if hasattr(update, 'callback_query') else None
    
    trade_data = context.user_data.get('trade_data', {
        'user_id': update.effective_user.id,
        'offer': {'money': 0, 'coins': 0, 'items': []},
        'request': {'money': 0, 'coins': 0, 'items': []},
        'recipient': None
    })
    
    user = get_user_data(update.effective_user.id)
    
    keyboard = [
        [InlineKeyboardButton("💰 Добавить деньги", callback_data="trade_add_money")],
        [InlineKeyboardButton("🪙 Добавить койны", callback_data="trade_add_coins")],
        [InlineKeyboardButton("🎁 Добавить предметы", callback_data="trade_add_items")],
        [InlineKeyboardButton("👤 Выбрать получателя", callback_data="trade_select_recipient")],
        [InlineKeyboardButton("✅ Подтвердить трейд", callback_data="trade_confirm")],
        [InlineKeyboardButton("🔙 Назад", callback_data="trade_back")]
    ]
    
    offer_text = (
        f"💰 Деньги: {trade_data['offer']['money']:,} ₽\n"
        f"🪙 Койны: {trade_data['offer']['coins']}\n"
        f"🎁 Предметы: {', '.join(trade_data['offer']['items']) or 'нет'}"
    )
    
    request_text = (
        f"💰 Деньги: {trade_data['request']['money']:,} ₽\n"
        f"🪙 Койны: {trade_data['request']['coins']}\n"
        f"🎁 Предметы: {', '.join(trade_data['request']['items']) or 'нет'}"
    )
    
    recipient_text = f"👤 Получатель: @{trade_data['recipient']}" if trade_data['recipient'] else "👤 Получатель: не выбран"
    
    message_text = (
        f"🔄 Создание трейда:\n\n"
        f"📤 Вы предлагаете:\n{offer_text}\n\n"
        f"📥 Вы запрашиваете:\n{request_text}\n\n"
        f"{recipient_text}"
    )
    
    if query:
        await query.edit_message_text(
            message_text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await context.bot.send_message(
            chat_id=update.effective_user.id,
            text=message_text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    return TRADE_CREATE

async def trade_create_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user = get_user_data(user_id)
    
    if not context.user_data.get('trade_data'):
        context.user_data['trade_data'] = {
            'user_id': user_id,
            'offer': {'money': 0, 'coins': 0, 'items': []},
            'request': {'money': 0, 'coins': 0, 'items': []},
            'recipient': None
        }
    
    trade_data = context.user_data['trade_data']
    
    if query.data == "trade_add_money":
        context.user_data['trade_action'] = 'add_money'
        await query.edit_message_text("Введите сумму денег, которую хотите предложить:")
        return TRADE_OFFER
    
    elif query.data == "trade_add_coins":
        context.user_data['trade_action'] = 'add_coins'
        await query.edit_message_text("Введите количество койнов, которые хотите предложить:")
        return TRADE_OFFER
    
    elif query.data == "trade_add_items":
        inventory = user.get('inventory', {'items': []})
        if not inventory['items']:
            await query.answer("❌ У вас нет предметов для обмена", show_alert=True)
            return await show_trade_create_menu(update, context)
        
        keyboard = []
        for item in inventory['items']:
            keyboard.append([InlineKeyboardButton(f"🎁 {item}", callback_data=f"trade_item_{item}")])
        
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="trade_create_back")])
        
        await query.edit_message_text(
            "🎁 Выберите предметы для обмена:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return TRADE_OFFER
    
    elif query.data == "trade_select_recipient":
        context.user_data['trade_action'] = 'select_recipient'
        await query.edit_message_text("Введите @username или ID пользователя, с которым хотите обменяться:")
        return TRADE_OFFER
    
    elif query.data == "trade_confirm":
        if not trade_data['recipient']:
            await query.answer("❌ Выберите получателя!", show_alert=True)
            return await show_trade_create_menu(update, context)
        
        recipient = None
        for uid, u_data in user_data.items():
            if str(u_data.get('username', '')).lower() == trade_data['recipient'].lower() or uid == trade_data['recipient']:
                recipient = {'id': uid, 'username': u_data.get('username', uid)}
                break
        
        if not recipient:
            await query.answer("❌ Пользователь не найден!", show_alert=True)
            return await show_trade_create_menu(update, context)
        
        if int(recipient['id']) == user_id:
            await query.answer("❌ Нельзя обмениваться с самим собой!", show_alert=True)
            return await show_trade_create_menu(update, context)
        
        if trade_data['offer']['money'] > user['balance']:
            await query.answer("❌ Недостаточно денег для предложения!", show_alert=True)
            return await show_trade_create_menu(update, context)
        
        if trade_data['offer']['coins'] > user.get('coins', 0):
            await query.answer("❌ Недостаточно койнов для предложения!", show_alert=True)
            return await show_trade_create_menu(update, context)
        
        inventory_items = user.get('inventory', {'items': []})['items']
        for item in trade_data['offer']['items']:
            if item not in inventory_items:
                await query.answer(f"❌ У вас нет предмета {item}!", show_alert=True)
                return await show_trade_create_menu(update, context)
        
        offer_id = secrets.token_hex(8)
        trade_offers[offer_id] = {
            'sender_id': user_id,
            'sender_name': user['username'],
            'recipient_id': recipient['id'],
            'recipient_name': recipient['username'],
            'offer': trade_data['offer'],
            'request': trade_data['request'],
            'created_at': datetime.now().isoformat()
        }
        
        await query.edit_message_text(
            f"✅ Предложение обмена создано!\n"
            f"👤 Для: @{recipient['username']}\n"
            f"💰 Вы предлагаете: {trade_data['offer']['money']:,} ₽ + {trade_data['offer']['coins']} койнов\n"
            f"🎁 Предметы: {', '.join(trade_data['offer']['items']) or 'нет'}\n"
            f"🔄 Вы запрашиваете: {trade_data['request']['money']:,} ₽ + {trade_data['request']['coins']} койнов\n"
            f"🎁 Предметы: {', '.join(trade_data['request']['items']) or 'нет'}"
        )
        
        try:
            await context.bot.send_message(
                chat_id=recipient['id'],
                text=(
                    f"📥 У вас новое предложение обмена от @{user['username']}!\n"
                    f"💰 Предлагает: {trade_data['offer']['money']:,} ₽ + {trade_data['offer']['coins']} койнов\n"
                    f"🎁 Предметы: {', '.join(trade_data['offer']['items']) or 'нет'}\n"
                    f"🔄 Запрашивает: {trade_data['request']['money']:,} ₽ + {trade_data['request']['coins']} койнов\n"
                    f"🎁 Предметы: {', '.join(trade_data['request']['items']) or 'нет'}\n\n"
                    f"Используйте команду /trade для просмотра и принятия предложения."
                )
            )
        except Exception as e:
            logging.error(f"Не удалось отправить уведомление о трейде: {e}")
        
        save_data()
        return await trade_menu(update, context)
    
    elif query.data == "trade_create_back":
        return await show_trade_create_menu(update, context)
    
    elif query.data == "trade_back":
        return await trade_menu(update, context)
    
    return TRADE_CREATE

async def show_my_trade_offers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    
    user_offers = [offer_id for offer_id, offer in trade_offers.items() if offer['sender_id'] == user_id]
    
    if not user_offers:
        await query.edit_message_text(
            "❌ У вас нет активных предложений обмена.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="trade_back")]])
        )
        return TRADE_MENU
    
    offers_text = "📨 Ваши предложения обмена:\n\n"
    for i, offer_id in enumerate(user_offers[:5], 1):
        offer = trade_offers[offer_id]
        offers_text += (
            f"{i}. ID: {offer_id}\n"
            f"👤 Для: @{offer['recipient_name']}\n"
            f"💰 Предложение: {offer['offer']['money']:,} ₽ + {offer['offer']['coins']} койнов\n"
            f"🎁 Предметы: {', '.join(offer['offer']['items']) or 'нет'}\n"
            f"🔄 Запрос: {offer['request']['money']:,} ₽ + {offer['request']['coins']} койнов\n"
            f"🎁 Предметы: {', '.join(offer['request']['items']) or 'нет'}\n\n"
        )
    
    keyboard = [
        [InlineKeyboardButton("❌ Отменить предложение", callback_data="trade_reject_offer")],
        [InlineKeyboardButton("🔙 Назад", callback_data="trade_back")]
    ]
    
    await query.edit_message_text(
        offers_text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return TRADE_MENU

async def show_incoming_trade_offers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    
    incoming_offers = [offer_id for offer_id, offer in trade_offers.items() if offer['recipient_id'] == str(user_id)]
    
    if not incoming_offers:
        await query.edit_message_text(
            "❌ У вас нет входящих предложений обмена.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="trade_back")]])
        )
        return TRADE_MENU
    
    offers_text = "📥 Входящие предложения обмена:\n\n"
    for i, offer_id in enumerate(incoming_offers[:5], 1):
        offer = trade_offers[offer_id]
        offers_text += (
            f"{i}. ID: {offer_id}\n"
            f"👤 От: @{offer['sender_name']}\n"
            f"💰 Предложение: {offer['offer']['money']:,} ₽ + {offer['offer']['coins']} койнов\n"
            f"🎁 Предметы: {', '.join(offer['offer']['items']) or 'нет'}\n"
            f"🔄 Запрос: {offer['request']['money']:,} ₽ + {offer['request']['coins']} койнов\n"
            f"🎁 Предметы: {', '.join(offer['request']['items']) or 'нет'}\n\n"
        )
    
    keyboard = [
        [InlineKeyboardButton("✅ Принять предложение", callback_data="trade_accept_offer")],
        [InlineKeyboardButton("❌ Отклонить предложение", callback_data="trade_reject_offer")],
        [InlineKeyboardButton("🔙 Назад", callback_data="trade_back")]
    ]
    
    await query.edit_message_text(
        offers_text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return TRADE_MENU

async def show_active_trades(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    
    user_trades = [trade_id for trade_id, trade in active_trades.items() 
                  if trade['user1'] == user_id or trade['user2'] == user_id]
    
    if not user_trades:
        await query.edit_message_text(
            "❌ У вас нет активных трейдов.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="trade_back")]])
        )
        return TRADE_MENU
    
    trades_text = "📊 Активные трейды:\n\n"
    for i, trade_id in enumerate(user_trades[:5], 1):
        trade = active_trades[trade_id]
        other_user_id = trade['user1'] if trade['user1'] != user_id else trade['user2']
        other_user = get_user_data(other_user_id)
        other_name = other_user.get('username', other_user_id)
        
        trades_text += (
            f"{i}. ID: {trade_id}\n"
            f"👤 С: @{other_name}\n"
            f"🔄 Статус: {'ожидает подтверждения' if not trade['confirmed'] else 'подтвержден'}\n\n"
        )
    
    keyboard = [
        [InlineKeyboardButton("✅ Подтвердить трейд", callback_data="trade_confirm_active")],
        [InlineKeyboardButton("❌ Отменить трейд", callback_data="trade_cancel_active")],
        [InlineKeyboardButton("🔙 Назад", callback_data="trade_back")]
    ]
    
    await query.edit_message_text(
        trades_text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return TRADE_MENU

async def trade_offer_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query if hasattr(update, 'callback_query') else None
    
    if query:
        await query.answer()
        user_id = query.from_user.id
        data = query.data
        
        if data == "trade_create_back":
            return await trade_create_handler(update, context)
        
        if data.startswith("trade_item_"):
            item = data.split('_')[2]
            trade_data = context.user_data['trade_data']
            
            if item in trade_data['offer']['items']:
                trade_data['offer']['items'].remove(item)
            else:
                trade_data['offer']['items'].append(item)
            
            return await show_trade_create_menu(update, context)
    
    else:
        user_id = update.message.from_user.id
        text = update.message.text
        trade_data = context.user_data['trade_data']
        action = context.user_data.get('trade_action')
        
        if action == 'add_money':
            try:
                amount = int(text)
                if amount < 0:
                    raise ValueError
                
                trade_data['offer']['money'] = amount
                await update.message.reply_text(
                    f"💰 Вы предложили {amount:,} ₽. Теперь введите количество койнов:"
                )
                context.user_data['trade_action'] = 'add_coins'
                return TRADE_OFFER
            except ValueError:
                await update.message.reply_text("❌ Введите корректную сумму денег!")
                return TRADE_OFFER
        
        elif action == 'add_coins':
            try:
                coins = int(text)
                if coins < 0:
                    raise ValueError
                
                trade_data['offer']['coins'] = coins
                await update.message.reply_text(
                    f"🪙 Вы предложили {coins} койнов. Теперь введите @username получателя:"
                )
                context.user_data['trade_action'] = 'select_recipient'
                return TRADE_OFFER
            except ValueError:
                await update.message.reply_text("❌ Введите корректное количество койнов!")
                return TRADE_OFFER
        
        elif action == 'select_recipient':
            trade_data['recipient'] = text
            del context.user_data['trade_action']
            
            await update.message.reply_text(
                f"👤 Получатель: {text}. Теперь настройте запрашиваемые ресурсы."
            )
            return await show_trade_create_menu(update, context)
    
    return TRADE_OFFER

async def trade_accept_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user = get_user_data(user_id)
    
    if query.data == "trade_accept_offer":
        context.user_data['trade_action'] = 'accept_offer'
        await query.edit_message_text("Введите ID предложения, которое хотите принять:")
        return TRADE_ACCEPT
    
    elif query.data == "trade_reject_offer":
        context.user_data['trade_action'] = 'reject_offer'
        await query.edit_message_text("Введите ID предложения, которое хотите отклонить:")
        return TRADE_ACCEPT
    
    elif query.data == "trade_confirm_active":
        context.user_data['trade_action'] = 'confirm_active'
        await query.edit_message_text("Введите ID трейда, который хотите подтвердить:")
        return TRADE_ACCEPT
    
    elif query.data == "trade_cancel_active":
        context.user_data['trade_action'] = 'cancel_active'
        await query.edit_message_text("Введите ID трейда, который хотите отменить:")
        return TRADE_ACCEPT
    
    return TRADE_ACCEPT

async def process_trade_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user = get_user_data(user_id)
    text = update.message.text
    
    action = context.user_data.get('trade_action')
    if not action:
        await update.message.reply_text("❌ Неизвестное действие. Начните заново.")
        return await trade_menu(update, context)
    
    try:
        if action == 'accept_offer':
            offer = trade_offers.get(text)
            if not offer:
                await update.message.reply_text("❌ Предложение не найдено!")
                return await trade_menu(update, context)
            
            if offer['recipient_id'] != str(user_id):
                await update.message.reply_text("❌ Это предложение не для вас!")
                return await trade_menu(update, context)
            
            sender = get_user_data(offer['sender_id'])
            
            if offer['offer']['money'] > sender['balance']:
                await update.message.reply_text("❌ У отправителя недостаточно денег!")
                return await trade_menu(update, context)
            
            if offer['offer']['coins'] > sender.get('coins', 0):
                await update.message.reply_text("❌ У отправителя недостаточно койнов!")
                return await trade_menu(update, context)
            
            if offer['request']['money'] > user['balance']:
                await update.message.reply_text("❌ У вас недостаточно денег для обмена!")
                return await trade_menu(update, context)
            
            if offer['request']['coins'] > user.get('coins', 0):
                await update.message.reply_text("❌ У вас недостаточно койнов для обмена!")
                return await trade_menu(update, context)
            
            sender_inventory = sender.get('inventory', {'items': []})
            for item in offer['offer']['items']:
                if item not in sender_inventory['items']:
                    await update.message.reply_text(f"❌ У отправителя нет предмета {item}!")
                    return await trade_menu(update, context)
            
            user_inventory = user.get('inventory', {'items': []})
            for item in offer['request']['items']:
                if item not in user_inventory['items']:
                    await update.message.reply_text(f"❌ У вас нет предмета {item}!")
                    return await trade_menu(update, context)
            
            trade_id = secrets.token_hex(8)
            active_trades[trade_id] = {
                'user1': offer['sender_id'],
                'user2': user_id,
                'offer': offer['offer'],
                'request': offer['request'],
                'confirmed': False,
                'confirmed_user1': False,
                'confirmed_user2': False,
                'created_at': datetime.now().isoformat()
            }
            
            del trade_offers[text]
            
            await update.message.reply_text(
                f"✅ Вы приняли предложение обмена! Трейд создан (ID: {trade_id}).\n"
                f"Теперь обе стороны должны подтвердить трейд."
            )
            
            try:
                await context.bot.send_message(
                    chat_id=offer['sender_id'],
                    text=(
                        f"✅ Пользователь @{user['username']} принял ваше предложение обмена!\n"
                        f"🔄 Трейд создан (ID: {trade_id}).\n"
                        f"Подтвердите трейд командой /trade."
                    )
                )
            except Exception as e:
                logging.error(f"Не удалось отправить уведомление о принятии трейда: {e}")
        
        elif action == 'reject_offer':
            if text not in trade_offers:
                await update.message.reply_text("❌ Предложение не найдено!")
                return await trade_menu(update, context)
            
            offer = trade_offers[text]
            if offer['recipient_id'] != str(user_id):
                await update.message.reply_text("❌ Это предложение не для вас!")
                return await trade_menu(update, context)
            
            del trade_offers[text]
            await update.message.reply_text("❌ Вы отклонили предложение обмена.")
            
            try:
                sender = get_user_data(offer['sender_id'])
                await context.bot.send_message(
                    chat_id=offer['sender_id'],
                    text=f"❌ Пользователь @{user['username']} отклонил ваше предложение обмена."
                )
            except Exception as e:
                logging.error(f"Не удалось отправить уведомление об отклонении трейда: {e}")
        
        elif action == 'confirm_active':
            if text not in active_trades:
                await update.message.reply_text("❌ Трейд не найден!")
                return await trade_menu(update, context)
            
            trade = active_trades[text]
            if user_id not in [trade['user1'], trade['user2']]:
                await update.message.reply_text("❌ Это не ваш трейд!")
                return await trade_menu(update, context)
            
            if user_id == trade['user1']:
                trade['confirmed_user1'] = True
            else:
                trade['confirmed_user2'] = True
            
            if trade['confirmed_user1'] and trade['confirmed_user2']:
                await execute_trade(update, context, text)
            else:
                await update.message.reply_text(
                    f"✅ Вы подтвердили трейд. Ожидаем подтверждения второй стороны."
                )
                
                other_user_id = trade['user1'] if user_id == trade['user2'] else trade['user2']
                try:
                    other_user = get_user_data(other_user_id)
                    await context.bot.send_message(
                        chat_id=other_user_id,
                        text=(
                            f"🔄 Пользователь @{user['username']} подтвердил трейд {text}.\n"
                            f"Подтвердите трейд для завершения обмена."
                        )
                    )
                except Exception as e:
                    logging.error(f"Не удалось отправить уведомление о подтверждении трейда: {e}")
        
        elif action == 'cancel_active':
            if text not in active_trades:
                await update.message.reply_text("❌ Трейд не найдён!")
                return await trade_menu(update, context)
            
            trade = active_trades[text]
            if user_id not in [trade['user1'], trade['user2']]:
                await update.message.reply_text("❌ Это не ваш трейд!")
                return await trade_menu(update, context)
            
            other_user_id = trade['user1'] if user_id == trade['user2'] else trade['user2']
            del active_trades[text]
            await update.message.reply_text("❌ Вы отменили трейд.")
            
            try:
                other_user = get_user_data(other_user_id)
                await context.bot.send_message(
                    chat_id=other_user_id,
                    text=f"❌ Пользователь @{user['username']} отменил трейд {text}."
                )
            except Exception as e:
                logging.error(f"Не удалось отправить уведомление об отмене трейда: {e}")
        
        save_data()
    
    except Exception as e:
        logging.error(f"Ошибка при обработке трейда: {e}")
        await update.message.reply_text("⚠️ Произошла ошибка при обработке трейда. Попробуйте снова.")
    
    return await trade_menu(update, context)

async def execute_trade(update: Update, context: ContextTypes.DEFAULT_TYPE, trade_id):
    trade = active_trades.get(trade_id)
    if not trade:
        await update.message.reply_text("❌ Трейд не найден!")
        return await trade_menu(update, context)
    
    user1 = get_user_data(trade['user1'])
    user2 = get_user_data(trade['user2'])
    
    if trade['offer']['money'] > user1['balance']:
        await update.message.reply_text("❌ У отправителя недостаточно денег!")
        return await trade_menu(update, context)
    
    if trade['offer']['coins'] > user1.get('coins', 0):
        await update.message.reply_text("❌ У отправителя недостаточно койнов!")
        return await trade_menu(update, context)
    
    if trade['request']['money'] > user2['balance']:
        await update.message.reply_text("❌ У получателя недостаточно денег!")
        return await trade_menu(update, context)
    
    if trade['request']['coins'] > user2.get('coins', 0):
        await update.message.reply_text("❌ У получателя недостаточно койнов!")
        return await trade_menu(update, context)
    
    user1_inventory = user1.get('inventory', {'items': []})
    for item in trade['offer']['items']:
        if item not in user1_inventory['items']:
            await update.message.reply_text(f"❌ У отправителя нет предмета {item}!")
            return await trade_menu(update, context)
    
    user2_inventory = user2.get('inventory', {'items': []})
    for item in trade['request']['items']:
        if item not in user2_inventory['items']:
            await update.message.reply_text(f"❌ У получателя нет предмета {item}!")
            return await trade_menu(update, context)
    
    user1['balance'] -= trade['offer']['money']
    user2['balance'] += trade['offer']['money']
    
    user2['balance'] -= trade['request']['money']
    user1['balance'] += trade['request']['money']
    
    user1['coins'] -= trade['offer']['coins']
    user2['coins'] += trade['offer']['coins']
    
    user2['coins'] -= trade['request']['coins']
    user1['coins'] += trade['request']['coins']
    
    for item in trade['offer']['items']:
        user1_inventory['items'].remove(item)
        user2_inventory.setdefault('items', []).append(item)
    
    for item in trade['request']['items']:
        user2_inventory['items'].remove(item)
        user1_inventory.setdefault('items', []).append(item)
    
    del active_trades[trade_id]
    
    trade_result = (
        f"✅ Трейд {trade_id} успешно завершен!\n\n"
        f"Вы получили:\n"
        f"💰 {trade['request']['money']:,} ₽\n"
        f"🪙 {trade['request']['coins']} койнов\n"
        f"🎁 {', '.join(trade['request']['items']) or 'нет'}\n\n"
        f"Вы отдали:\n"
        f"💰 {trade['offer']['money']:,} ₽\n"
        f"🪙 {trade['offer']['coins']} койнов\n"
        f"🎁 {', '.join(trade['offer']['items']) or 'нет'}"
    )
    
    await update.message.reply_text(trade_result)
    
    try:
        await context.bot.send_message(
            chat_id=trade['user1'] if update.message.from_user.id == trade['user2'] else trade['user2'],
            text=trade_result
        )
    except Exception as e:
        logging.error(f"Не удалось отправить уведомление о завершении трейда: {e}")
    
    save_data()
    return await trade_menu(update, context)

# ==================== ФУНКЦИИ БОКСОВ ====================
async def box_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in banned_users:
        if update.callback_query:
            await update.callback_query.answer("⛔ Вы заблокированы", show_alert=True)
            return
        else:
            await update.message.reply_text("⛔ Вы заблокированы и не можете использовать бота.")
            return
        
    user = get_user_data(user_id)
    user['last_active'] = time.time()
    
    # Инициализация инвентаря, если его нет
    if 'inventory' not in user:
        user['inventory'] = {'boxes': 0, 'items': []}
    
    keyboard = [
        [InlineKeyboardButton(f"🎁 Купить бокс ({BOX_PRICE} койнов)", callback_data="box_buy")],
        [InlineKeyboardButton(f"🎉 Открыть бокс ({user['inventory']['boxes']} шт.)", callback_data="box_open")],
        [InlineKeyboardButton("📦 Мой инвентарь", callback_data="box_inventory")],
        [InlineKeyboardButton("🔙 Назад", callback_data="box_back")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = "🎁 Меню боксов:\n\n" \
           f"🪙 Ваши койны: {user.get('coins', 0)}\n" \
           f"🎁 Доступно боксов: {user['inventory']['boxes']}"
    
    if update.callback_query:
        try:
            await update.callback_query.edit_message_text(
                text,
                reply_markup=reply_markup
            )
        except:
            await update.callback_query.message.reply_text(
                text,
                reply_markup=reply_markup
            )
    else:
        await update.message.reply_text(
            text,
            reply_markup=reply_markup
        )
    
    return BOX_MENU

async def box_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user = get_user_data(user_id)
    
    if query.data == "box_buy":
        if user.get('coins', 0) < BOX_PRICE:
            await query.answer(f"❌ Недостаточно койнов! Нужно {BOX_PRICE}", show_alert=True)
            return await box_menu(update, context)
        
        user['coins'] -= BOX_PRICE
        user['inventory']['boxes'] += 1
        save_data()
        
        await context.bot.send_message(
            chat_id=user_id,
            text=f"✅ Вы купили 1 бокс за {BOX_PRICE} койнов. Теперь у вас {user['inventory']['boxes']} боксов."
        )
        return await box_menu(update, context)
    
    elif query.data == "box_open":
        if user['inventory']['boxes'] < 1:
            await query.answer("❌ У вас нет боксов для открытия!", show_alert=True)
            return await box_menu(update, context)
        
        reward, emoji = calculate_box_reward()
        user['balance'] += reward
        user['inventory']['boxes'] -= 1
        
        # Добавляем награду в инвентарь
        reward_item = f"{emoji} {reward:,} ₽"
        user['inventory']['items'].append(reward_item)
        
        save_data()
        
        await context.bot.send_message(
            chat_id=user_id,
            text=f"🎉 Вы открыли бокс и получили: {reward_item}\n" \
                 f"💰 Ваш баланс: {user['balance']:,} ₽"
        )
        return await box_menu(update, context)
    
    elif query.data == "box_inventory":
        inventory = user.get('inventory', {})
        boxes = inventory.get('boxes', 0)
        items = inventory.get('items', [])
        
        inventory_text = "📦 Ваш инвентарь:\n\n"
        inventory_text += f"🎁 Боксов: {boxes}\n"
        inventory_text += "🎁 Предметы:\n"
        
        if not items:
            inventory_text += "Пока пусто"
        else:
            for i, item in enumerate(items, 1):
                inventory_text += f"{i}. {item}\n"
        
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="box_back")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            inventory_text,
            reply_markup=reply_markup
        )
        return BOX_MENU
    
    elif query.data == "box_back":
        return await box_menu(update, context)
    
    return BOX_MENU

async def handle_trade_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await trade_menu(update, context)

async def handle_box_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await box_menu(update, context)

async def error_handler(update: object, context: CallbackContext) -> None:
    logger.error("Exception while handling an update:", exc_info=context.error)

async def main():
    global ADMIN_GROUP_ID
    
    load_data()
    
    application = Application.builder().token("7507672774:AAH4QgBAvFpxp4x9cpclDlTGqnQuhi51Ics").build()
    
    if not await setup_admin_group(application.bot):
        logging.warning("Группа администраторов не настроена, некоторые функции будут недоступны")
    else:
        try:
            await application.bot.send_message(
                chat_id=ADMIN_GROUP_ID,
                text="🤖 Бот запущен и готов к работе!",
                parse_mode='HTML'
            )
        except Exception as e:
            logging.error(f"Не удалось отправить тестовое сообщение в группу: {str(e)}")

    admin_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("admin", admin_login)],
        states={
            AWAITING_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_admin_password)],
            ADMIN_PANEL: [
                CallbackQueryHandler(admin_actions, pattern=r"^adm:"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, show_admin_panel)
            ],
            AWAITING_USER_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_user_action)],
            AWAITING_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_amount)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=False,
        per_chat=True
    )
    
    casino_conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex(r"^(🎰 Казино|Казино)$"), handle_casino_button),
            CommandHandler("casino", casino)
        ],
        states={
            BET: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_bet)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=False
    )
    
    business_conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex(r"^(🏢 Бизнесы|Бизнесы)$"), handle_businesses_button),
            CommandHandler("businesses", businesses_menu)
        ],
        states={
            BUY_BUSINESS: [CallbackQueryHandler(business_button_handler, pattern=r"^business_")],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=False
    )
    
    trade_conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex(r"^(🔄 Трейды|Трейды)$"), handle_trade_button),
            CommandHandler("trade", trade_menu)
        ],
        states={
            TRADE_MENU: [CallbackQueryHandler(trade_button_handler, pattern=r"^trade_")],
            TRADE_CREATE: [CallbackQueryHandler(trade_create_handler, pattern=r"^trade_")],
            TRADE_OFFER: [
                CallbackQueryHandler(trade_offer_handler, pattern=r"^trade_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, trade_offer_handler)
            ],
            TRADE_ACCEPT: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_trade_action)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=False
    )

    box_conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex(r"^(🎁 Боксы|Боксы)$"), handle_box_button),
            CommandHandler("boxes", box_menu)
        ],
        states={
            BOX_MENU: [CallbackQueryHandler(box_button_handler, pattern=r"^box_")],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        
        per_message=False
    )
    
    application.add_handler(admin_conv_handler)
    application.add_handler(casino_conv_handler)
    application.add_handler(business_conv_handler)
    application.add_handler(trade_conv_handler)
    application.add_handler(box_conv_handler)
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("set_nick", set_nick))
    application.add_handler(CommandHandler("pay", pay))
    application.add_handler(CommandHandler("balance", balance))
    application.add_handler(CommandHandler("profile", profile))
    application.add_handler(CommandHandler("top_balance", top_balance))
    application.add_handler(CommandHandler("top_referrals", top_referrals))
    application.add_handler(CommandHandler("top_coins", top_coins))
    application.add_handler(CommandHandler("promo", promo))
    
    application.add_handler(CallbackQueryHandler(work_handler, pattern=r"^work_"))
    application.add_handler(CallbackQueryHandler(business_button_handler, pattern=r"^business_"))
    application.add_handler(CallbackQueryHandler(top_button_handler, pattern=r"^top_"))
    
    application.add_handler(MessageHandler(filters.Regex(r"^💼 Работа$"), handle_work_button))
    application.add_handler(MessageHandler(filters.Regex(r"^💰 Баланс$"), handle_balance_button))
    application.add_handler(MessageHandler(filters.Regex(r"^📊 Профиль$"), handle_profile_button))
    application.add_handler(MessageHandler(filters.Regex(r"^🏆 Топы$"), handle_tops_button))
    application.add_handler(MessageHandler(filters.Regex(r"^🔄 Трейды$"), handle_trade_button))
    application.add_handler(MessageHandler(filters.Regex(r"^🎁 Боксы$"), handle_box_button))
    
    application.add_handler(MessageHandler(filters.ChatType.GROUPS & filters.TEXT & ~filters.COMMAND, handle_group_message))
    
    application.add_error_handler(error_handler)
    
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    
    try:
        while True:
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        pass
    finally:
        await application.updater.stop()
        await application.stop()
        await application.shutdown()

def run_bot():
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot stopped by user")
    except Exception as e:
        print(f"Unexpected error: {e}")
    finally:
        print("Bot has been shut down")

if __name__ == "__main__":
    run_bot()