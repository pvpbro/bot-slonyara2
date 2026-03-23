import uuid
import datetime
import asyncio  # Добавьте эту строку вверху файла
import aiohttp  # Добавьте это в импортыport asyncio
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
    InlineKeyboardButton,
    WebAppInfo
)
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
    CallbackQueryHandler,
    ConversationHandler,
    CallbackContext,
    JobQueue
)

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Константы для фото
PHOTO_NORMAL_PATH = os.path.join(BASE_DIR, "окак.jpg")
PHOTO_EXTINGUISHER_PATH = os.path.join(BASE_DIR, "чертик.jpg")
PHOTO_TAXI_PATH = os.path.join(BASE_DIR, "такси.jpg")
PHOTO_ACCOUNTANT_PATH = os.path.join(BASE_DIR, "бухгалтер.jpg")
PHOTO_GANG_PATH = os.path.join(BASE_DIR, "банды.jpg")
PHOTO_CASINO_PATH = os.path.join(BASE_DIR, "казино.jpg")

# ==================== НОВЫЕ КОНСТАНТЫ ДЛЯ КОМБИНАЦИЙ ====================
PHOTO_FLOWER_WITH_EXTINGUISHER = os.path.join(BASE_DIR, "цветок_с_огнетушителем.jpg")
PHOTO_FLOWER_WITHOUT_EXTINGUISHER = os.path.join(BASE_DIR, "чертик.jpg")

# ==================== СИСТЕМА ЧЕКОВ ====================
# ID канала для чеков
CHECK_CHANNEL_ID = "-1003581581967"  # ID канала
# ==================== СИСТЕМА ДРУЗЕЙ ====================
friend_requests = {}  # {request_id: {'from': user_id, 'to': user_id, 'time': timestamp}}
friends = {}  # {user_id: [список друзей]}
# Хранилище чеков
# ==================== КЛИКЕР ДЛЯ РАБОТЫ ====================
# ==================== КРАШ-ИГРА ====================
CRASH_CONFIG = {
    'min_bet': 1_000,           # Минимальная ставка 1к
    'max_bet': 100_000_000_000_000,     # Максимальная ставка 100ккkk
    'min_multiplier': 1.01,      # Минимальный множитель
    'max_multiplier': 10.0,      # Максимальный множитель
    'crash_chance': 0.03,        # 3% шанс краша на каждом шаге
    'multiplier_step': 0.01,      # Шаг увеличения множителя
    'time_between_steps': 0.5,    # 0.5 секунды между шагами
}

# Активные игры
crash_games = {}  # {user_id: {'bet': ставка, 'multiplier': множитель, 'active': True, 'cashed_out': False}}

# Статистика игр
crash_stats = {}  # {user_id: {'games': всего, 'wins': выигрыши, 'profit': прибыль}}
# ==================== КЛИКЕР ====================
CLICKER_CONFIG = {
    'reward': 10_000_000,  # 10кк за успешный клик
    'buttons_count': 5,     # 5 кнопок
    'click_cooldown': 0.5,  # 0.5 сек между кликами
    'mistake_ban': 600,     # 10 минут бана при ошибке (в секундах)
}

clicker_games = {}  # {user_id: {'active': True, 'correct': index, 'start_time': time, 'mistake_time': time}}
clicker_banned = {}  # {user_id: unblock_time}

checks = {}  # Формат: {check_id: check_data}


# Конфигурация чеков
CHECK_CONFIG = {
    'expire_time': 86400,  # 24 часа в секундах
    'max_activations': 100,  # Максимальное количество активаций для одного чека
    'min_amount': 1000,  # Минимальная сумма чека
    'max_amount': 1_000_000_000,  # Максимальная сумма чека (1 млрд)
}

# Разрешенные пользователи для создания чеков
CHECK_ALLOWED_USERS = [7990799592]  # Только этот пользователь может создавать чеки
# ==================== VIP СИСТЕМА ====================
VIP_PRICE = 50  # токенов в месяц
VIP_DAILY_BONUS = 5_000_000  # 5кк в день
VIP_BUSINESS_INCOME = 30_000_000  # 30кк в час
VIP_BOOST = 1.15  # +15% к доходу

vip_users = {}  # {user_id: {'expires': timestamp, 'premium_business': bool}}

def check_vip(user_id):
    """Проверяет, активна ли VIP подписка"""
    user_id = str(user_id)
    if user_id in vip_users:
        expires = vip_users[user_id].get('expires', 0)
        if expires > time.time():
            return True
        else:
            # VIP истек - удаляем только из vip_users
            if user_id in vip_users:
                del vip_users[user_id]
                # НЕ ТРОГАЕМ vip_business ЗДЕСЬ!
                save_vip()
    return False
    
async def check_expired_vip(context: ContextTypes.DEFAULT_TYPE):
    """Проверяет истекшие VIP подписки"""
    current_time = time.time()
    for user_id, vip_data in list(vip_users.items()):
        if vip_data['expires'] <= current_time:
            # ТОЛЬКО удаляем из vip_users, НЕ ТРОГАЕМ бизнес
            del vip_users[user_id]
            # Уведомляем пользователя
            try:
                await context.bot.send_message(
                    chat_id=int(user_id),
                    text="❌ Ваш VIP статус истек. VIP бизнес больше не приносит доход."
                )
            except:
                pass
    
    save_vip()

def get_vip_bonus(user_id):
    """Возвращает множитель дохода для VIP"""
    return VIP_BOOST if check_vip(user_id) else 1.0
# Премиум предметы (золотой цветок и т.д.)
premium_items = {}  # {user_id: [список предметов]}
def save_vip():
    """Сохраняет данные о VIP"""
    try:
        with open('vip.json', 'w', encoding='utf-8') as f:
            json.dump(vip_users, f, ensure_ascii=False, indent=4)
    except Exception as e:
        logging.error(f"Ошибка сохранения VIP: {e}")

def load_vip():
    """Загружает данные о VIP"""
    global vip_users
    try:
        if os.path.exists('vip.json'):
            with open('vip.json', 'r', encoding='utf-8') as f:
                vip_users = json.load(f)
    except Exception as e:
        logging.error(f"Ошибка загрузки VIP: {e}")
        vip_users = {}
ADMINS = {
    'scriptik_kormit': {  # Владелец (полный доступ)
        'password_hash': hashlib.sha256('pvpcat1203930394944844838484'.encode()).hexdigest(),
        'telegram_id': 7990799592,
        '2fa_secret': secrets.token_hex(16),
        'last_login': None,
        'failed_attempts': 0,
        'last_attempt': None,
        'level': 3,  # Уровень доступа (3 - владелец)
        'daily_limit': {'money': float('inf'), 'coins': float('inf')}  # Без лимитов
    },
    'HigherLoyz': {  # Владелец с ограничениями
        'password_hash': hashlib.sha256('sashamix'.encode()).hexdigest(),
        'telegram_id': None,  # Можно указать реальный ID
        'last_login': None,
        'failed_attempts': 0,
        'last_attempt': None,
        'level': 1,  # Уровень владельца
        'daily_limit': {'money': 1_000_000, 'coins': 20}  # Лимиты в день
    },
    'New_moon3': {  # Владелец с ограничениями
        'password_hash': hashlib.sha256('vich1'.encode()).hexdigest(),
        'telegram_id': 5548750765,  # Можно указать реальный ID
        'last_login': None,
        'failed_attempts': 0,
        'last_attempt': None,
        'level': 2,  # Уровень владельца
        'daily_limit': {'money': 1_000_000, 'coins': 20}  # Лимиты в день
    }
}
# Группа администраторов (публичная)
ADMIN_GROUP_ID = "-1003505311472"  # ID группы
ADMIN_GROUP_LINK = "https://t.me/tigr228585r"  # Ссылка на публичную группу
# ==================== PVP КОСТИ ====================
pvp_games = {}  # {game_id: {'creator': user_id, 'opponent': None, 'amount': сумма, 'status': 'waiting'}}

PVP_GAME_TIME = 300  # 5 минут на принятие

# ==================== УЛУЧШЕННАЯ СИСТЕМА РАБОТ ====================
# ==================== СИСТЕМА ДОСТИЖЕНИЙ ====================
# ==================== МАГАЗИН РАСХОДНИКОВ ====================
CONSUMABLES_SHOP = {
    'coin': {
        'name': '🪙 Койн',
        'description': 'Можно обменять на 100,000,000 ₽',
        'buy_price': 200_000_000,  # 200кк
        'sell_price': 100_000_000,  # 100кк
        'emoji': '🪙',
        'type': 'currency'
    },
    'luck_ticket': {
        'name': '🍀 Билет удачи',
        'description': 'Удваивает шанс в казино на 1 ставку',
        'buy_price': 50_000_000,
        'emoji': '🍀',
        'type': 'boost',
        'effect': 'casino_luck'
    },
    'speed_potion': {
        'name': '⚡ Ускоритель',
        'description': 'Сокращает время работы на 50% (1 раз)',
        'buy_price': 30_000_000,
        'emoji': '⚡',
        'type': 'boost',
        'effect': 'work_speed'
    },
    'gift_box': {
        'name': '🎁 Подарочная коробка',
        'description': 'Можно подарить другу (содержит случайный бонус)',
        'buy_price': 100_000_000,
        'emoji': '🎁',
        'type': 'gift'
    },
    'flower': {
        'name': '🌸 Цветок',
        'description': 'Красивый цветок для друга',
        'buy_price': 10_000_000,
        'emoji': '🌸',
        'type': 'gift'
    },
    'cake': {
        'name': '🎂 Тортик',
        'description': 'Сладкий подарок ко дню рождения',
        'buy_price': 25_000_000,
        'emoji': '🎂',
        'type': 'gift'
    },
    'champagne': {
        'name': '🍾 Шампанское',
        'description': 'Для особого случая',
        'buy_price': 40_000_000,
        'emoji': '🍾',
        'type': 'gift'
    },
    'ring': {
        'name': '💍 Колечко',
        'description': 'Дорогой подарок для лучшего друга',
        'buy_price': 100_000_000,
        'emoji': '💍',
        'type': 'gift'
    }
}

# Инвентарь пользователя для расходников
user_consumables = {}  # {user_id: {item_id: количество}}

ACHIEVEMENTS = {
    # Достижения по балансу
    'millionaire': {
        'name': '💰 Миллионер',
        'description': 'Накопить 1,000,000 ₽',
        'emoji': '💰',
        'condition': lambda user: user['balance'] >= 1_000_000,
        'reward': 100_000,
        'hidden': False
    },
    'billionaire': {
        'name': '💎 Миллиардер',
        'description': 'Накопить 1,000,000,000 ₽',
        'emoji': '💎',
        'condition': lambda user: user['balance'] >= 1_000_000_000,
        'reward': 10_000_000,
        'hidden': False
    },
    'trillionaire': {
        'name': '👑 Триллионер',
        'description': 'Накопить 1,000,000,000,000 ₽',
        'emoji': '👑',
        'condition': lambda user: user['balance'] >= 1_000_000_000_000,
        'reward': 100_000_000,
        'hidden': True  # Секретное достижение
    },
    
    # Достижения по бизнесам
    'business_beginner': {
        'name': '🏪 Начинающий бизнесмен',
        'description': 'Купить 1 бизнес',
        'emoji': '🏪',
        'condition': lambda user: user.get('business_count', 0) >= 1,
        'reward': 50_000,
        'hidden': False
    },
    'business_master': {
        'name': '🏭 Магнат',
        'description': 'Купить 10 бизнесов',
        'emoji': '🏭',
        'condition': lambda user: user.get('business_count', 0) >= 10,
        'reward': 500_000,
        'hidden': False
    },
    'business_tycoon': {
        'name': '🏢 Олигарх',
        'description': 'Купить 25 бизнесов',
        'emoji': '🏢',
        'condition': lambda user: user.get('business_count', 0) >= 25,
        'reward': 5_000_000,
        'hidden': False
    },
    
    # Достижения по казино
    'casino_winner': {
        'name': '🎰 Счастливчик',
        'description': 'Выиграть в казино 1,000,000 ₽ за раз',
        'emoji': '🎰',
        'condition': lambda user: user.get('max_casino_win', 0) >= 1_000_000,
        'reward': 100_000,
        'hidden': False
    },
    'casino_addict': {
        'name': '🎲 Игроман',
        'description': 'Сделать 100 ставок в казино',
        'emoji': '🎲',
        'condition': lambda user: user.get('total_bets', 0) >= 100,
        'reward': 200_000,
        'hidden': False
    },
    'casino_lucky': {
        'name': '🍀 Везунчик',
        'description': 'Выиграть 3 раза подряд',
        'emoji': '🍀',
        'condition': lambda user: user.get('max_win_streak', 0) >= 3,
        'reward': 300_000,
        'hidden': False
    },
    
    # Достижения по работам
    'hard_worker': {
        'name': '👷 Трудяга',
        'description': 'Выполнить 100 работ',
        'emoji': '👷',
        'condition': lambda user: sum(job.get('completed', 0) for job in user.get('jobs', {}).values()) >= 100,
        'reward': 150_000,
        'hidden': False
    },
    'workaholic': {
        'name': '💼 Трудоголик',
        'description': 'Выполнить 1000 работ',
        'emoji': '💼',
        'condition': lambda user: sum(job.get('completed', 0) for job in user.get('jobs', {}).values()) >= 1000,
        'reward': 1_000_000,
        'hidden': True  # Секретное достижение
    },
    
    # Достижения по рефералам
    'friend_1': {
        'name': '👥 Компанейский',
        'description': 'Пригласить 1 друга',
        'emoji': '👥',
        'condition': lambda user: len(user.get('referrals', [])) >= 1,
        'reward': 10_000,
        'hidden': False
    },
    'friend_10': {
        'name': '👨‍👩‍👧‍👦 Популярный',
        'description': 'Пригласить 10 друзей',
        'emoji': '👨‍👩‍👧‍👦',
        'condition': lambda user: len(user.get('referrals', [])) >= 10,
        'reward': 100_000,
        'hidden': False
    },
    'friend_50': {
        'name': '🌟 Звезда',
        'description': 'Пригласить 50 друзей',
        'emoji': '🌟',
        'condition': lambda user: len(user.get('referrals', [])) >= 50,
        'reward': 1_000_000,
        'hidden': True  # Секретное достижение
    },
    
    # Достижения по боксам
    'box_opener': {
        'name': '🎁 Коллекционер',
        'description': 'Открыть 10 боксов',
        'emoji': '🎁',
        'condition': lambda user: user.get('boxes_opened', 0) >= 10,
        'reward': 50_000,
        'hidden': False
    },
    'box_master': {
        'name': '📦 Охотник за сокровищами',
        'description': 'Открыть 100 боксов',
        'emoji': '📦',
        'condition': lambda user: user.get('boxes_opened', 0) >= 100,
        'reward': 500_000,
        'hidden': False
    },
    
    # Достижения по инвестициям
    'investor': {
        'name': '📈 Инвестор',
        'description': 'Вложить 10,000,000 ₽ в инвестиции',
        'emoji': '📈',
        'condition': lambda user: user.get('total_invested', 0) >= 10_000_000,
        'reward': 200_000,
        'hidden': False
    },
    'gambler': {
        'name': '🎲 Рисковый',
        'description': 'Вложить 100,000,000 ₽ в высокорисковые активы',
        'emoji': '🎲',
        'condition': lambda user: user.get('high_risk_invested', 0) >= 100_000_000,
        'reward': 2_000_000,
        'hidden': True  # Секретное достижение
    },
}

# Секретные достижения (их описание скрыто до получения)
SECRET_ACHIEVEMENTS = ['trillionaire', 'workaholic', 'friend_50', 'gambler']
# ==================== ДОНАТ МАГАЗИН ====================
# ==================== ТОКЕНЫ ====================
TOKEN_BALANCES = {}  # {user_id: количество токенов}

TOKEN_SHOP_ITEMS = {
    1: {"name": "2,000,000,000 ₽", "price": 10, "amount": 2_000_000_000},
    2: {"name": "5,000,000,000 ₽", "price": 22, "amount": 5_000_000_000},
    3: {"name": "10,000,000,000 ₽", "price": 40, "amount": 10_000_000_000},
    4: {"name": "20,000,000,000 ₽", "price": 75, "amount": 20_000_000_000},
    5: {"name": "50,000,000,000 ₽", "price": 180, "amount": 50_000_000_000},
    6: {"name": "100,000,000,000 ₽", "price": 350, "amount": 100_000_000_000},
    # ... существующие товары ...
    'vip': {
        'name': '👑 VIP СТАТУС',
        'description': 'Премиум подписка на 30 дней',
        'price': 50,
        'emoji': '👑',
        'type': 'vip'
}
}
# ID владельца, который может выдавать токены
TOKEN_OWNER_ID = "7990799592"

def get_token_balance(user_id):
    """Получить баланс токенов пользователя"""
    user_id = str(user_id)
    return TOKEN_BALANCES.get(user_id, 0)

def add_tokens(user_id, amount):
    """Добавить токены пользователю"""
    user_id = str(user_id)
    TOKEN_BALANCES[user_id] = TOKEN_BALANCES.get(user_id, 0) + amount
    save_token_balances()

def remove_tokens(user_id, amount):
    """Списать токены у пользователя"""
    user_id = str(user_id)
    current = TOKEN_BALANCES.get(user_id, 0)
    if current >= amount:
        TOKEN_BALANCES[user_id] = current - amount
        save_token_balances()
        return True
    return False

def save_token_balances():
    """Сохранить балансы токенов"""
    try:
        with open('token_balances.json', 'w', encoding='utf-8') as f:
            json.dump(TOKEN_BALANCES, f, ensure_ascii=False, indent=4)
    except Exception as e:
        logging.error(f"Ошибка сохранения токенов: {e}")

def load_token_balances():
    """Загрузить балансы токенов"""
    global TOKEN_BALANCES
    try:
        if os.path.exists('token_balances.json'):
            with open('token_balances.json', 'r', encoding='utf-8') as f:
                TOKEN_BALANCES = json.load(f)
    except Exception as e:
        logging.error(f"Ошибка загрузки токенов: {e}")
        TOKEN_BALANCES = {}

# ==================== ИНВЕСТИЦИИ ====================
PREMIUM_BOX_CONFIG = {
    "name": "💎 Премиум бокс",
    "price": 1_000_000_000,  # 1ккк
    "rewards": [
        # ТОЛЬКО ОДИН ПРЕДМЕТ - ЦВЕТОК (2% шанс)
        {
            "type": "item", 
            "name": "🌸 Золотой цветок", 
            "emoji": "🌸", 
            "chance": 7, 
            "item_id": "golden_flower",
            "description": "Редкий золотой цветок удачи"
        },
        
        # ВАЛЮТА (остальные 98%)
        {
            "type": "money", 
            "amount": 10_000_000, 
            "emoji": "💰", 
            "chance": 35, 
            "description": "10кк"
        },  # 40%
        {
            "type": "money", 
            "amount": 250_000_000, 
            "emoji": "💰", 
            "chance": 30, 
            "description": "250кк"
        },  # 30%
        {
            "type": "money", 
            "amount": 300_300_000, 
            "emoji": "💰", 
            "chance": 20, 
            "description": "300кк"
        },  # 20%
        {
            "type": "money", 
            "amount": 1_500_000_000, 
            "emoji": "💎", 
            "chance": 3, 
            "description": "1.5ккк (редкий)",
            "is_rare": True
        },  # 3% - как указано
    ],
    "item_photos": {
        "golden_flower": "/storage/emulated/0/фотобот/цветок.jpg",  # Фото цветка
    }
}

INVESTMENT_COMPANIES = {
    'tech': {
        'name': '🚀 TechCorp',
        'emoji': '💻',
        'description': 'Технологический гигант',
        'base_return': 1.2,  # базовый возврат 120%
        'volatility': 0.4,    # волатильность 40%
        'min_invest': 100000,
        'color': '🔵'
    },
    'energy': {
        'name': '⚡ EnergyCo',
        'emoji': '⚡',
        'description': 'Энергетическая компания',
        'base_return': 1.15,
        'volatility': 0.3,
        'min_invest': 50000,
        'color': '🟡'
    },
    'finance': {
        'name': '💰 FinanceBank',
        'emoji': '🏦',
        'description': 'Финансовый сектор',
        'base_return': 1.1,
        'volatility': 0.2,
        'min_invest': 200000,
        'color': '🟢'
    },
    'space': {
        'name': '🚀 SpaceY',
        'emoji': '🛸',
        'description': 'Космический туризм',
        'base_return': 1.5,
        'volatility': 0.7,
        'min_invest': 1000000,
        'color': '🟣'
    },
    'crypto': {
        'name': '₿ CryptoMine',
        'emoji': '₿',
        'description': 'Крипто майнинг',
        'base_return': 2.0,
        'volatility': 1.0,
        'min_invest': 500000,
        'color': '🟠'
    }
}

user_investments = {}  # {user_id: {company: {'amount': сумма, 'start_time': время, 'days': дни}}}

# Конфигурация профессий
JOBS_CONFIG = {
    'taxi': {
        'name': '🚕 Таксист',
        'emoji': '🚕',
        'description': 'Развозите пассажиров по городу',
        'min_earn': [5000, 15000, 30000, 50000, 100000],
        'max_earn': [20000, 40000, 80000, 150000, 300000],
        'cooldown': [300, 240, 180, 120, 60],  # в секундах (5мин, 4мин, 3мин, 2мин, 1мин)
        'exp_per_work': [10, 15, 20, 25, 30],
        'levels': 5,
        'requirements': {2: 50, 3: 150, 4: 300, 5: 500},  # выполнено работ для уровня
        'bonus': {  # бонусы за уровень
            2: '🚗 Скорость +20%',
            3: '💰 Доход +30%',
            4: '🏎️ Спорткар (шанс двойной оплаты 10%)',
            5: '👑 Бизнес-класс (шанс чаевых 20%)'
        }
    },
    'accountant': {
        'name': '📊 Бухгалтер',
        'emoji': '📊',
        'description': 'Ведите учет и получайте бонусы',
        'min_earn': [100000, 250000, 500000, 1000000, 2000000],
        'max_earn': [500000, 1000000, 2000000, 4000000, 8000000],
        'cooldown': [3600, 3000, 2400, 1800, 1200],  # 60мин, 50мин, 40мин, 30мин, 20мин
        'exp_per_work': [20, 25, 30, 35, 40],
        'levels': 5,
        'requirements': {2: 30, 3: 80, 4: 150, 5: 250},
        'daily_limit': [5, 8, 12, 16, 20],  # сколько раз в день можно работать
        'bonus': {
            2: '📈 Аналитика (шанс найти ошибку +5% дохода)',
            3: '💼 VIP-клиенты (доход +40%)',
            4: '🔍 Аудит (шанс двойного дохода 15%)',
            5: '👔 Финдиректор (ежедневный бонус 500к)'
        }
    },
    'builder': {
        'name': '👷 Строитель',
        'emoji': '👷',
        'description': 'Стройте и улучшайте здания',
        'min_earn': [20000, 50000, 100000, 200000, 500000],
        'max_earn': [80000, 150000, 300000, 600000, 1200000],
        'cooldown': [1800, 1500, 1200, 900, 600],  # 30мин, 25мин, 20мин, 15мин, 10мин
        'exp_per_work': [15, 20, 25, 30, 35],
        'levels': 5,
        'requirements': {2: 40, 3: 100, 4: 200, 5: 350},
        'bonus': {
            2: '🔨 Прораб (шанс найти стройматериалы)',
            3: '🏗️ Краны (доход +35%)',
            4: '🏭 Завод (шанс двойного дохода 12%)',
            5: '🏰 Небоскреб (еженедельный бонус 2кк)'
        }
    },
    'businessman': {
        'name': '👨‍💼 Бизнесмен',
        'emoji': '👨‍💼',
        'description': 'Заключайте выгодные сделки',
        'min_earn': [100000, 250000, 500000, 1000000, 2500000],
        'max_earn': [500000, 1000000, 2500000, 5000000, 10000000],
        'cooldown': [3600, 3000, 2400, 1800, 1200],  # 60мин, 50мин, 40мин, 30мин, 20мин
        'exp_per_work': [25, 30, 35, 40, 45],
        'levels': 5,
        'requirements': {2: 25, 3: 70, 4: 150, 5: 300},
        'bonus': {
            2: '🤝 Связи (шанс на бонусную сделку)',
            3: '💎 Элитные клиенты (доход +50%)',
            4: '📊 Биржа (шанс x3 дохода 10%)',
            5: '👑 Магнат (пассивный доход 100к/час)'
        }
    }
}

# Достижения за работу
WORK_ACHIEVEMENTS = {
    'taxi': {
        100: {'name': '🚕 Новичок дорог', 'reward': 100000},
        500: {'name': '🚖 Мастер руля', 'reward': 500000},
        1000: {'name': '🏎️ Король дорог', 'reward': 2000000}
    },
    'accountant': {
        50: {'name': '📊 Счетовод', 'reward': 500000},
        200: {'name': '📈 Финансист', 'reward': 2000000},
        500: {'name': '💼 Гений учета', 'reward': 5000000}
    },
    'builder': {
        100: {'name': '👷 Строитель', 'reward': 300000},
        300: {'name': '🏗️ Прораб', 'reward': 1000000},
        600: {'name': '🏰 Архитектор', 'reward': 3000000}
    },
    'businessman': {
        50: {'name': '💼 Бизнесмен', 'reward': 1000000},
        150: {'name': '👔 Инвестор', 'reward': 5000000},
        300: {'name': '👑 Олигарх', 'reward': 10000000}
    }
}

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
SESSION_TIMEOUT = 24 * 3600

# Хранилища данных
request_log = {}
blacklist = {}
active_sessions = {}
user_warns = {}
banned_users = set()
user_data = {}
trade_offers = {}
active_trades = {}

# ==================== НАСТРОЙКИ ПОЛЬЗОВАТЕЛЯ ====================
user_settings = {}  # {user_id: {'confirm_transfer': bool, 'hide_in_top': bool}}

def get_user_settings(user_id):
    """Получает настройки пользователя"""
    user_id = str(user_id)
    if user_id not in user_settings:
        user_settings[user_id] = {
            'confirm_transfer': False,  # По умолчанию выключено
            'hide_in_top': False        # По умолчанию показан в топах
        }
    return user_settings[user_id]

def save_user_settings():
    """Сохраняет настройки пользователей"""
    try:
        with open('user_settings.json', 'w', encoding='utf-8') as f:
            json.dump(user_settings, f, ensure_ascii=False, indent=4)
    except Exception as e:
        logging.error(f"Ошибка сохранения настроек: {e}")

def load_user_settings():
    """Загружает настройки пользователей"""
    global user_settings
    try:
        if os.path.exists('user_settings.json'):
            with open('user_settings.json', 'r', encoding='utf-8') as f:
                user_settings = json.load(f)
    except Exception as e:
        logging.error(f"Ошибка загрузки настроек: {e}")
        user_settings = {}
        
async def settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню настроек"""
    user_id = str(update.effective_user.id)
    settings = get_user_settings(user_id)
    
    text = (
        "⚙️ <b>НАСТРОЙКИ</b>\n"
        "═══════════════════\n\n"
        "Здесь вы можете настроить бота под себя.\n\n"
    )
    
    # Статусы настроек
    confirm_status = "✅ ВКЛ" if settings['confirm_transfer'] else "❌ ВЫКЛ"
    hide_status = "✅ ВКЛ" if settings['hide_in_top'] else "❌ ВЫКЛ"
    
    text += (
        f"💸 <b>Подтверждение переводов:</b> {confirm_status}\n"
        f"├ При включении, переводы нужно будет подтверждать\n"
        f"└ кнопкой в течение 30 секунд\n\n"
        
        f"👤 <b>Скрыть из топов:</b> {hide_status}\n"
        f"└ Ваш профиль не будет отображаться в топах"
    )
    
    keyboard = [
        [InlineKeyboardButton(
            f"💸 Подтверждение переводов: {confirm_status}", 
            callback_data="settings_toggle_confirm"
        )],
        [InlineKeyboardButton(
            f"👤 Скрыть из топов: {hide_status}", 
            callback_data="settings_toggle_hide"
        )],
        [InlineKeyboardButton("🔙 НАЗАД", callback_data="settings_back")]
    ]
    
    await update.message.reply_text(
        text=text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )

async def settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопок настроек"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    data = query.data
    settings = get_user_settings(user_id)
    
    if data == "settings_toggle_confirm":
        settings['confirm_transfer'] = not settings['confirm_transfer']
        save_user_settings()
        await query.edit_message_text(
            text=f"✅ Подтверждение переводов {'включено' if settings['confirm_transfer'] else 'выключено'}"
        )
        await asyncio.sleep(1)
        return await settings_menu(update, context)
    
    elif data == "settings_toggle_hide":
        settings['hide_in_top'] = not settings['hide_in_top']
        save_user_settings()
        await query.edit_message_text(
            text=f"✅ Скрытие из топов {'включено' if settings['hide_in_top'] else 'выключено'}"
        )
        await asyncio.sleep(1)
        return await settings_menu(update, context)
    
    elif data == "settings_back":
        return await settings_menu(update, context)        

def load_investments():
    """Загружает данные об инвестициях"""
    global user_investments
    try:
        if os.path.exists('investments.json'):
            with open('investments.json', 'r', encoding='utf-8') as f:
                user_investments = json.load(f)
    except Exception as e:
        logging.error(f"Ошибка загрузки инвестиций: {e}")
        user_investments = {}

def save_investments():
    """Сохраняет данные об инвестициях"""
    try:
        with open('investments.json', 'w', encoding='utf-8') as f:
            json.dump(user_investments, f, ensure_ascii=False, indent=4)
    except Exception as e:
        logging.error(f"Ошибка сохранения инвестиций: {e}")
def load_premium_items():
    """Загружает данные о премиум предметах"""
    global premium_items
    try:
        if os.path.exists('premium_items.json'):
            with open('premium_items.json', 'r', encoding='utf-8') as f:
                premium_items = json.load(f)
    except Exception as e:
        logging.error(f"Ошибка загрузки премиум предметов: {e}")
        premium_items = {}

def save_premium_items():
    """Сохраняет данные о премиум предметах"""
    try:
        with open('premium_items.json', 'w', encoding='utf-8') as f:
            json.dump(premium_items, f, ensure_ascii=False, indent=4)
    except Exception as e:
        logging.error(f"Ошибка сохранения премиум предметов: {e}")

def save_checks():
    """Сохраняет данные о чеках"""
    try:
        with open('checks.json', 'w', encoding='utf-8') as f:
            json.dump(checks, f, ensure_ascii=False, indent=4)
    except Exception as e:
        logging.error(f"Ошибка сохранения чеков: {e}")

def load_checks():
    """Загружает данные о чеках"""
    global checks
    try:
        if os.path.exists('checks.json'):
            with open('checks.json', 'r', encoding='utf-8') as f:
                checks = json.load(f)
    except Exception as e:
        logging.error(f"Ошибка загрузки чеков: {e}")
        checks = {}

def update_admin_session(user_id):
    """Обновляет время активности сессии администратора"""
    if user_id in active_sessions:
        active_sessions[user_id]['last_activity'] = time.time()
        return True
    return False
    
# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================
def is_admin_session_valid(user_id):
    """Проверяет, валидна ли сессия администратора"""
    if user_id not in active_sessions:
        return False
    
    session = active_sessions[user_id]
    current_time = time.time()
    
    # Проверка таймаута сессии (24 часа)
    if current_time - session['last_activity'] > SESSION_TIMEOUT:
        # Автоматически удаляем просроченную сессию
        del active_sessions[user_id]
        return False
    
    return True
    
async def process_new_admin_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка пароля для нового администратора"""
    user = update.effective_user
    password = update.message.text.strip()
    
    # Проверяем, есть ли данные о создаваемом админе
    if 'pending_admin' not in context.user_data:
        await update.message.reply_text("❌ Ошибка данных! Начните заново.")
        return await show_admin_panel(update, context)
    
    pending_data = context.user_data['pending_admin']
    username = pending_data['username']
    level = pending_data['level']
    
    if len(password) < 6:
        await update.message.reply_text("❌ Пароль слишком короткий! Минимум 6 символов.\nВведите пароль:")
        return AWAITING_ADMIN_PASSWORD
    
    # Проверяем, не существует ли уже такой администратор
    if username in ADMINS:
        await update.message.reply_text("❌ Этот пользователь уже является администратором!")
        context.user_data.pop('pending_admin', None)
        return await show_admin_panel(update, context)
    
    # Создаем администратора
    ADMINS[username] = {
        'password_hash': hashlib.sha256(password.encode()).hexdigest(),
        'telegram_id': None,  # Будет установлен при первом входе
        'last_login': None,
        'failed_attempts': 0,
        'last_attempt': None,
        'level': level,
        'daily_limit': {
            'money': 50_000_000 if level >= 2 else 10_000_000,
            'coins': 100 if level >= 2 else 20
        },
        'created_by': user.username,
        'created_at': datetime.now().isoformat()
    }
    
    save_data()
    
    # Очищаем временные данные
    context.user_data.pop('pending_admin', None)
    context.user_data.pop('target_admin', None)
    context.user_data.pop('admin_action', None)
    
    level_names = {3: "👑 Владелец", 2: "🛡 Администратор", 1: "👮 Модератор"}
    
    await update.message.reply_text(
        f"✅ Новый администратор добавлен!\n\n"
        f"👤 Пользователь: @{username}\n"
        f"🛡 Уровень: {level_names.get(level, 'Неизвестно')}\n"
        f"🔐 Пароль: {password}\n\n"
        f"⚠️ <b>Сохраните этот пароль!</b>\n"
        f"Администратор должен использовать его для входа командой /admin",
        parse_mode='HTML'
    )
    
    return await show_admin_panel(update, context)

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

def load_users():
    """Загружает данные пользователей из users.json"""
    global user_data, banned_users, trade_offers, active_trades
    try:
        if os.path.exists('users.json'):
            with open('users.json', 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if content:
                    data = json.loads(content)
                    user_data = data.get('user_data', {})
                    banned_users = set(data.get('banned_users', []))
                    trade_offers = data.get('trade_offers', {})
                    active_trades = data.get('active_trades', {})
                else:
                    user_data = {}
                    banned_users = set()
                    trade_offers = {}
                    active_trades = {}
    except Exception as e:
        logging.error(f"Ошибка загрузки пользователей: {e}")
        user_data = {}
        banned_users = set()
        trade_offers = {}
        active_trades = {}

def save_users():
    """Сохраняет данные пользователей в users.json"""
    try:
        data = {
            'user_data': user_data,
            'banned_users': list(banned_users),
            'trade_offers': trade_offers,
            'active_trades': active_trades
        }
        with open('users.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        logging.error(f"Ошибка сохранения пользователей: {e}")

def get_user_photo_info(user_id: str) -> dict:
    """Определяет какое фото показывать пользователю с учетом всех предметов"""
    user_id_str = str(user_id)
    print(f"DEBUG photo для {user_id_str}")
    
    user = get_user_data(user_id_str, create_if_not_exists=False)
    if not user:
        print("DEBUG: пользователь не найден")
        return {"path": PHOTO_NORMAL_PATH, "caption": "", "priority": 0}
    
    # Отладочная информация
    user_item_data = user_items.get(user_id_str, {})
    print(f"DEBUG: user_items = {user_item_data}")
    print(f"DEBUG: active_item = {user_item_data.get('active_item')}")
    print(f"DEBUG: items_owned = {user_item_data.get('items_owned', [])}")
    
    # Проверяем активные предметы
    active_flower = user.get('active_premium_item', {}).get('id') == 'golden_flower'
    active_extinguisher = user_item_data.get('active_item') == 'fire_extinguisher'
    
    print(f"DEBUG: active_flower = {active_flower}")
    print(f"DEBUG: active_extinguisher = {active_extinguisher}")
    
    # 1. КОМБИНАЦИЯ: Активный цветок + активный огнетушитель (наивысший приоритет)
    if active_flower and active_extinguisher:
        if os.path.exists(PHOTO_FLOWER_WITH_EXTINGUISHER):
            return {
                "path": PHOTO_FLOWER_WITH_EXTINGUISHER,
                "caption": "🌸 + 🚒 Цветок с огнетушителем",
                "priority": 4
            }
        elif os.path.exists(PHOTO_FLOWER_WITHOUT_EXTINGUISHER):
            return {
                "path": PHOTO_FLOWER_WITHOUT_EXTINGUISHER,
                "caption": "🌸 Золотой цветок",
                "priority": 3
            }
    
    # 2. АКТИВНЫЙ ЦВЕТОК (без огнетушителя)
    if active_flower:
        photo_path = PREMIUM_BOX_CONFIG['item_photos'].get('golden_flower')
        if photo_path and os.path.exists(photo_path):
            return {
                "path": photo_path,
                "caption": "🌸 Золотой цветок удачи",
                "priority": 3
            }
    
    # 3. АКТИВНЫЙ ОГНЕТУШИТЕЛЬ
    if active_extinguisher:
        photo_path = PHOTO_EXTINGUISHER_PATH
        if os.path.exists(photo_path):
            return {
                "path": photo_path,
                "caption": "🎯 Активный предмет: 🚒 Огнетушитель",
                "priority": 2
            }
    
    # 4. Бизнес-такси (уровень 3 таксиста)
    if user.get('jobs', {}).get('taxi', {}).get('level') == 3:
        photo_path = TAXI_LEVELS[3].get('photo')
        if photo_path and os.path.exists(photo_path):
            return {
                "path": photo_path,                "caption": "🏎️ Таксист бизнес-класса",
                "priority": 1
            }
    
    # 5. Стандартное фото
    if os.path.exists(PHOTO_NORMAL_PATH):
        return {
            "path": PHOTO_NORMAL_PATH,
            "caption": "",
            "priority": 0
        }
    
    # Если файл не найден
    return {
        "path": "",
        "caption": "⚠️ Фото недоступно",
        "priority": -1
    }



def save_data(data=None):
    """Сохраняет данные в data.json"""
    if data is None:
        data = {
            'user_data': user_data,
            'banned_users': list(banned_users),
            'trade_offers': trade_offers,
            'active_trades': active_trades
        }
    with open('data.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    
    # Сохраняем остальные данные
    save_user_items()
    save_casino_stats()
    save_checks()
    save_user_settings()
    save_friends()
    save_investments()
    save_premium_items()
    save_consumables()
    save_vip()

def load_data():
    """Загружает данные из data.json"""
    global user_data, banned_users, trade_offers, active_trades
    try:
        if os.path.exists('data.json'):
            with open('data.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
                user_data = data.get('user_data', {})
                banned_users = set(data.get('banned_users', []))
                trade_offers = data.get('trade_offers', {})
                active_trades = data.get('active_trades', {})
        else:
            user_data = {}
            banned_users = set()
            trade_offers = {}
            active_trades = {}
    except Exception as e:
        logging.error(f"Ошибка загрузки: {e}")
        user_data = {}
        banned_users = set()
        trade_offers = {}
        active_trades = {}
        
def get_user_data(user_id, create_if_not_exists=True):
    """Получение данных пользователя с созданием если нужно"""
    user_id = str(user_id)
    
    if user_id not in user_data and create_if_not_exists:
        # СОЗДАЕМ НОВОГО ПОЛЬЗОВАТЕЛЯ СО ВСЕМИ ПОЛЯМИ
        user_data[user_id] = {
            'balance': 100000,
            'coins': 0,
            'accountant_uses': 0,
            'last_accountant_date': None,
            'businesses': [],
            'last_taxi_time': None,
            'last_business_income': datetime.now().isoformat(),
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
            'promocode_used': 0,
            'jobs': {
                'taxi': {'level': 1, 'completed': 0, 'last_work': None},
                'accountant': {'level': 1, 'completed': 0, 'last_work': None},
                'builder': {'level': 1, 'completed': 0, 'last_work': None},
                'businessman': {'level': 1, 'completed': 0, 'last_work': None}
            },
            'vip_business': False,
            'achievements': {},
            'premium_items': [],
            'last_daily_box': None
        }
    
    # ЕСЛИ ПОЛЬЗОВАТЕЛЬ ЕСТЬ, НО НЕТ КАКИХ-ТО ПОЛЕЙ - ДОБАВЛЯЕМ
    if user_id in user_data:
        user = user_data[user_id]
        
        # Проверяем наличие всех обязательных полей
        if 'balance' not in user:
            user['balance'] = 100000
        if 'coins' not in user:
            user['coins'] = 0
        if 'business_count' not in user:
            user['business_count'] = 0
        if 'last_business_income' not in user:
            user['last_business_income'] = datetime.now().isoformat()
        if 'vip_business' not in user:
            user['vip_business'] = False
        if 'inventory' not in user:
            user['inventory'] = {'boxes': 0, 'items': []}
        if 'jobs' not in user:
            user['jobs'] = {
                'taxi': {'level': 1, 'completed': 0, 'last_work': None},
                'accountant': {'level': 1, 'completed': 0, 'last_work': None},
                'builder': {'level': 1, 'completed': 0, 'last_work': None},
                'businessman': {'level': 1, 'completed': 0, 'last_work': None}
            }
    
    return user_data.get(user_id, {})

# Статистика казино для топа по сливу
casino_stats = {}  # Формат: {user_id: {'lost': сумма_проигрыша, 'won': сумма_выигрыша, 'net': чистая_прибыль/убыток}}

# Конфигурация для игры БСК
BSK_CONFIG = {
    'win_multiplier': 6,  # x6 при выигрыше
    'win_chance': 0.4,     # 40% шанс на победу
    'min_bet': 1,       # Минимальная ставка 1000
    'max_bet': 999_000_000_000_000_000  # Максимальная ставка 100 млн
}

# Стикеры для БСК (ID стикеров в Telegram)
BSK_STICKERS = {
    'shoot': '🏀',  # Можно заменить на реальный ID стикера
    'success': '🏀🔥',  # Попадание
    'fail': '🏀❌',  # Промах
    'win': '🎉🏆',  # Победа
    'lose': '😢💔'  # Проигрыш
}    

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
        
# ==================== МАГАЗИН ====================
SHOP_MENU = "shop_menu"  # Добавьте эту константу с другими состояниями

SHOP_ITEMS = {
    'fire_extinguisher': {
        'name': '🚒 Огнетушитель',
        'price': 500_000,
        'description': 'Потушит любой пожар в вашем профиле!',
        'image_url': 'https://imgfoto.host/i/pn3rUk',
        'type': 'avatar'
    }
}

user_items = {}

def save_user_items():
    """Сохраняет данные о предметах пользователей"""
    try:
        data = {'user_items': user_items}
        with open('user_items.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        logging.error(f"Ошибка сохранения предметов: {e}")

def load_user_items():
    """Загружает данные о предметах пользователей"""
    global user_items
    try:
        if os.path.exists('user_items.json'):
            with open('user_items.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
                user_items = data.get('user_items', {})
    except Exception as e:
        logging.error(f"Ошибка загрузки предметов: {e}")
        user_items = {}

def get_main_keyboard():
    """Создает клавиатуру главного меню"""
    keyboard = [     
        ["🎰 Казино", "🏦 Банк", "💼 Работа"],
        ["🏢 Бизнесы", "🏴 Банды", "📊 Профиль"],
        ["💰 Баланс", "🏆 Топы", "⚙️ Настройки"],
        ["🔄 Трейды", "🎁 Боксы", "🛒 Магазин"] # Новая кнопка
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Рассылка сообщения всем игрокам (только для админа)"""
    user_id = update.effective_user.id
    
    # Проверяем, что команду дал админ (ID 7990799592)
    if user_id != 7990799592:
        await update.message.reply_text("❌ У вас нет прав для этой команды!")
        return
    
    # Проверяем, есть ли текст сообщения
    if not context.args:
        await update.message.reply_text(
            "❌ Использование: /rasil [текст сообщения]\n"
            "Пример: /rasil Привет всем! Сегодня удвоенный доход!"
        )
        return
    
    # Получаем текст сообщения
    message_text = ' '.join(context.args)
    
    # Отправляем подтверждение
    status_msg = await update.message.reply_text(
        f"📤 Начинаю рассылку...\n"
        f"👥 Всего пользователей: {len(user_data)}\n"
        f"⏳ Это может занять некоторое время."
    )
    
    # Счетчики
    sent = 0
    failed = 0
    blocked = 0
    
    # Отправляем сообщение каждому пользователю
    for uid, user in user_data.items():
        try:
            await context.bot.send_message(
                chat_id=int(uid),
                text=(
                    f"📢 <b>РАССЫЛКА</b>\n"
                    f"═══════════════════\n\n"
                    f"{message_text}\n\n"
                    f"💬 Сообщение от администрации"
                ),
                parse_mode='HTML'
            )
            sent += 1
            
            # Небольшая задержка, чтобы не спамить
            await asyncio.sleep(0.05)
            
        except Exception as e:
            if "blocked" in str(e).lower():
                blocked += 1
            else:
                failed += 1
            logging.error(f"Ошибка отправки пользователю {uid}: {e}")
    
    # Отправляем отчет
    await status_msg.edit_text(
        f"✅ <b>РАССЫЛКА ЗАВЕРШЕНА!</b>\n"
        f"══════════════════════\n\n"
        f"📊 <b>Статистика:</b>\n"
        f"├ 👥 Всего: {len(user_data)}\n"
        f"├ ✅ Доставлено: {sent}\n"
        f"├ ❌ Заблокировали бота: {blocked}\n"
        f"└ ⚠️ Ошибок: {failed}\n\n"
        f"📝 Текст: {message_text}",
        parse_mode='HTML'
    )

# ==================== ХРАНИЛИЩА ДАННЫХ БАНД ====================
gangs = {}  # Формат: {gang_id: gang_data}
gang_invites = {}  # Приглашения в банды
gang_wars = {}  # Активные войны между бандами

# Конфигурация банд
GANG_CONFIG = {
    'creation_cost': 1_000_000_000,  # 100ккк = 100,000,000,000
    'max_members': {
        1: 40,   # Уровень 1: 10 человек
        2: 55,   # Уровень 2: 25 человек
        3: 70,   # Уровень 3: 50 человек
        4: 300,  # Уровень 4: 100 человек
    },
    'upgrade_cost': {
        2: 500_000_000,    # 500кк
        3: 2_000_000_000,  # 2ккк
        4: 5_000_000_000,  # 5ккк
    },
    'war_cooldown': 86400,  # 24 часа между войнами
    'attack_duration': 3600,  # 1 час на атаку
}
# ==================== КОНФИГУРАЦИЯ БИЗНЕСОВ ====================
# ==================== КОНФИГУРАЦИЯ БИЗНЕСОВ (РАСШИРЕННАЯ) ====================
BUSINESS_TYPES = {
    # УРОВЕНЬ 1 - Малый бизнес (до 100 млн)
    1: {
        "name": "Киоск с шаурмой",
        "price": 1_000_000,
        "income": 10_000,
        "description": "Небольшой киоск в спальном районе",
        "emoji": "🥙",
        "category": "Еда",
        "level": 1,
        "required_level": 0,
        "max_level": 5,
        "profit_multiplier": 1.0
    },
    2: {
        "name": "Кофейня на колесах",
        "price": 2_500_000,
        "income": 25_000,
        "description": "Мобильная кофейня в центре города",
        "emoji": "☕",
        "category": "Еда",
        "level": 1,
        "required_level": 0,
        "max_level": 5,
        "profit_multiplier": 1.1
    },
    3: {
        "name": "Пекарня",
        "price": 5_000_000,
        "income": 50_000,
        "description": "Свежая выпечка каждый день",
        "emoji": "🥐",
        "category": "Еда",
        "level": 1,
        "required_level": 1,
        "max_level": 5,
        "profit_multiplier": 1.2
    },
    4: {
        "name": "Небольшой магазин",
        "price": 8_000_000,
        "income": 80_000,
        "description": "Продуктовый магазин у дома",
        "emoji": "🏪",
        "category": "Торговля",
        "level": 1,
        "required_level": 2,
        "max_level": 5,
        "profit_multiplier": 1.3
    },
    5: {
        "name": "Пивной бар",
        "price": 12_000_000,
        "income": 120_000,
        "description": "Уютный бар с разливным пивом",
        "emoji": "🍺",
        "category": "Развлечения",
        "level": 1,
        "required_level": 3,
        "max_level": 5,
        "profit_multiplier": 1.4
    },
    
    # УРОВЕНЬ 2 - Средний бизнес (до 500 млн)
    6: {
        "name": "Ресторан быстрого питания",
        "price": 20_000_000,
        "income": 200_000,
        "description": "Популярная сеть фастфуда",
        "emoji": "🍔",
        "category": "Еда",
        "level": 2,
        "required_level": 4,
        "max_level": 10,
        "profit_multiplier": 1.5
    },
    7: {
        "name": "Фитнес-клуб",
        "price": 35_000_000,
        "income": 350_000,
        "description": "Современный тренажерный зал",
        "emoji": "🏋️",
        "category": "Спорт",
        "level": 2,
        "required_level": 5,
        "max_level": 10,
        "profit_multiplier": 1.6
    },
    8: {
        "name": "Автомойка",
        "price": 50_000_000,
        "income": 500_000,
        "description": "Автоматическая мойка самообслуживания",
        "emoji": "🚗",
        "category": "Услуги",
        "level": 2,
        "required_level": 6,
        "max_level": 10,
        "profit_multiplier": 1.7
    },
    9: {
        "name": "Стоматологическая клиника",
        "price": 75_000_000,
        "income": 750_000,
        "description": "Частная стоматология",
        "emoji": "🦷",
        "category": "Медицина",
        "level": 2,
        "required_level": 7,
        "max_level": 10,
        "profit_multiplier": 1.8
    },
    10: {
        "name": "Автосалон",
        "price": 100_000_000,
        "income": 1_000_000,
        "description": "Продажа новых автомобилей",
        "emoji": "🚘",
        "category": "Авто",
        "level": 2,
        "required_level": 8,
        "max_level": 10,
        "profit_multiplier": 1.9
    },
    
    # УРОВЕНЬ 3 - Крупный бизнес (до 2 млрд)
    11: {
        "name": "ТРЦ",
        "price": 200_000_000,
        "income": 2_000_000,
        "description": "Торгово-развлекательный центр",
        "emoji": "🏬",
        "category": "Недвижимость",
        "level": 3,
        "required_level": 9,
        "max_level": 15,
        "profit_multiplier": 2.0
    },
    12: {
        "name": "Кинотеатр",
        "price": 300_000_000,
        "income": 3_000_000,
        "description": "Мультиплекс с 8 залами",
        "emoji": "🎬",
        "category": "Развлечения",
        "level": 3,
        "required_level": 10,
        "max_level": 15,
        "profit_multiplier": 2.1
    },
    13: {
        "name": "Отель 4 звезды",
        "price": 500_000_000,
        "income": 5_000_000,
        "description": "Комфортабельный отель в центре",
        "emoji": "🏨",
        "category": "Гостиничный",
        "level": 3,
        "required_level": 11,
        "max_level": 15,
        "profit_multiplier": 2.2
    },
    14: {
        "name": "Частная клиника",
        "price": 750_000_000,
        "income": 7_500_000,
        "description": "Многопрофильный медицинский центр",
        "emoji": "🏥",
        "category": "Медицина",
        "level": 3,
        "required_level": 12,
        "max_level": 15,
        "profit_multiplier": 2.3
    },
    15: {
        "name": "Бизнес-центр",
        "price": 1_000_000_000,
        "income": 10_000_000,
        "description": "Офисное здание класса А",
        "emoji": "🏢",
        "category": "Недвижимость",
        "level": 3,
        "required_level": 13,
        "max_level": 15,
        "profit_multiplier": 2.4
    },
    
    # УРОВЕНЬ 4 - Премиум бизнес (до 10 млрд)
    16: {
        "name": "Завод",
        "price": 2_000_000_000,
        "income": 20_000_000,
        "description": "Промышленное производство",
        "emoji": "🏭",
        "category": "Промышленность",
        "level": 4,
        "required_level": 14,
        "max_level": 20,
        "profit_multiplier": 2.5
    },
    17: {
        "name": "Нефтяная вышка",
        "price": 3_000_000_000,
        "income": 30_000_000,
        "description": "Добыча черного золота",
        "emoji": "🛢️",
        "category": "Добыча",
        "level": 4,
        "required_level": 15,
        "max_level": 20,
        "profit_multiplier": 2.6
    },
    18: {
        "name": "Аэропорт",
        "price": 5_000_000_000,
        "income": 50_000_000,
        "description": "Международный аэропорт",
        "emoji": "✈️",
        "category": "Транспорт",
        "level": 4,
        "required_level": 16,
        "max_level": 20,
        "profit_multiplier": 2.7
    },
    19: {
        "name": "IT-компания",
        "price": 7_500_000_000,
        "income": 75_000_000,
        "description": "Разработка программного обеспечения",
        "emoji": "💻",
        "category": "Технологии",
        "level": 4,
        "required_level": 17,
        "max_level": 20,
        "profit_multiplier": 2.8
    },
    20: {
        "name": "Космический туризм",
        "price": 10_000_000_000,
        "income": 100_000_000,
        "description": "Полеты в космос для туристов",
        "emoji": "🚀",
        "category": "Технологии",
        "level": 4,
        "required_level": 18,
        "max_level": 20,
        "profit_multiplier": 2.9
    },
    
    # УРОВЕНЬ 5 - Элитный бизнес (до 100 млрд)
    21: {
        "name": "Казино",
        "price": 20_000_000_000,
        "income": 200_000_000,
        "description": "Элитное казино в Лас-Вегасе",
        "emoji": "🎰",
        "category": "Развлечения",
        "level": 5,
        "required_level": 19,
        "max_level": 25,
        "profit_multiplier": 3.0
    },
    22: {
        "name": "Остров",
        "price": 30_000_000_000,
        "income": 300_000_000,
        "description": "Частный тропический остров",
        "emoji": "🏝️",
        "category": "Недвижимость",
        "level": 5,
        "required_level": 20,
        "max_level": 25,
        "profit_multiplier": 3.1
    },
    23: {
        "name": "Футбольный клуб",
        "price": 50_000_000_000,
        "income": 500_000_000,
        "description": "Профессиональный футбольный клуб",
        "emoji": "⚽",
        "category": "Спорт",
        "level": 5,
        "required_level": 21,
        "max_level": 25,
        "profit_multiplier": 3.2
    },
    24: {
        "name": "Круизный лайнер",
        "price": 75_000_000_000,
        "income": 750_000_000,
        "description": "Роскошный круизный корабль",
        "emoji": "🚢",
        "category": "Транспорт",
        "level": 5,
        "required_level": 22,
        "max_level": 25,
        "profit_multiplier": 3.3
    },
    25: {
        "name": "Спутник",
        "price": 100_000_000_000,
        "income": 1_000_000_000,
        "description": "Собственный спутник на орбите",
        "emoji": "🛰️",
        "category": "Космос",
        "level": 5,
        "required_level": 23,
        "max_level": 25,
        "profit_multiplier": 3.5
    },

    # ... существующие бизнесы ...
    26: {
        "name": "👑 Премиум бизнес (VIP)",
        "price": 0,  # Бесплатно для VIP
        "income": 30_000_000,
        "description": "Эксклюзивный бизнес для VIP игроков",
        "emoji": "👑",
        "category": "VIP",
        "level": 6,
        "vip_only": True
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
DEPOSIT_TYPES = {
    1: {
        "name": "1 день", 
        "multiplier": 1.05,
        "min_amount": 50_000
    },
    3: {
        "name": "3 дня",
        "multiplier": 1.15,
        "min_amount": 100_000
    },
    7: {
        "name": "1 неделя",
        "multiplier": 1.3,
        "min_amount": 500_000
    },
    14: {
        "name": "2 недели",
        "multiplier": 1.6,
        "min_amount": 1_000_000
    },
    30: {
        "name": "1 месяц",
        "multiplier": 2.0,
        "min_amount": 5_000_000
    }
}

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

# Убедитесь, что эти строки есть в начале файла (после импортов)
(
    AWAITING_PASSWORD,
    ADMIN_PANEL,
    AWAITING_USER_ID,
    AWAITING_AMOUNT,
    BET_TYPE,
    BET_AMOUNT,
    BUY_BUSINESS,
    BUSINESS_NAME,
    TRADE_MENU,
    TRADE_CREATE,
    TRADE_OFFER,
    TRADE_ACCEPT,
    BOX_MENU,          # <-- ЭТО ДОЛЖНО БЫТЬ
    BOX_OPEN,          # <-- И ЭТО
    BANK_MENU,
    BANK_DEPOSIT,
    BANK_WITHDRAW,
    AWAITING_PROMO_NAME,
    AWAITING_PROMO_TYPE,
    AWAITING_PROMO_VALUE,
    AWAITING_PROMO_USES,
    AWAITING_PROMO_EXPIRE,
    AWAITING_ADMIN_USERNAME,
    AWAITING_ADMIN_LEVEL,
    CREATE_CHECK,
    CHECK_AMOUNT,
    ACTIVATE_CHECK,
    GANG_MENU,
    GANG_CREATE,
    GANG_INVITE,
    GANG_KICK,
    GANG_TRANSFER,
    GANG_DISBAND,
    GANG_WAR_TARGET,
    GANG_WAR_CONFIRM,
    GANG_SETTINGS,
    GANG_JOIN_TYPE,
    GANG_DONATE,
    GANG_WAR_ATTACK,
    PREMIUM_BOX_MENU,
    AWAITING_ADMIN_PASSWORD,
    WORK_MENU,
    INVEST_MENU,      # Добавьте это
    INVEST_AMOUNT,    # Добавьте это
) = range(44)  # Увеличьте число  # 
# ==================== КОМАНДЫ АДМИНИСТРАТОРА ====================
# В начале файла убираем SESSION_TIMEOUT и active_sessions
active_sessions = {}  # Просто оставляем пустым

async def admin_login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    await update.message.reply_text("🔑 Введите пароль администратора:")
    return AWAITING_PASSWORD

async def process_admin_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    password = update.message.text.strip()
    
    # Проверяем, создаем ли мы нового админа (ожидается пароль для нового админа)
    if 'pending_admin' in context.user_data:
        # Это создание нового админа - сохраняем пароль
        pending_data = context.user_data['pending_admin']
        username = pending_data['username']
        level = pending_data['level']
        
        # Проверяем, не существует ли уже такой администратор
        if username in ADMINS:
            await update.message.reply_text("❌ Этот пользователь уже является администратором!")
            context.user_data.pop('pending_admin', None)
            return await show_admin_panel(update, context)
        
        # Создаем администратора
        ADMINS[username] = {
            'password_hash': hashlib.sha256(password.encode()).hexdigest(),
            'telegram_id': None,  # Будет установлен при первом входе
            'last_login': None,
            'failed_attempts': 0,
            'last_attempt': None,
            'level': level,
            'daily_limit': {
                'money': 50_000_000 if level >= 2 else 10_000_000,
                'coins': 100 if level >= 2 else 20
            },
            'created_by': user.username,
            'created_at': datetime.now().isoformat()
        }
        
        save_data()
        
        # Очищаем временные данные
        context.user_data.pop('pending_admin', None)
        context.user_data.pop('target_admin', None)
        context.user_data.pop('admin_action', None)
        
        level_names = {3: "👑 Владелец", 2: "🛡 Администратор", 1: "👮 Модератор"}
        
        await update.message.reply_text(
            f"✅ Новый администратор добавлен!\n\n"
            f"👤 Пользователь: @{username}\n"
            f"🛡 Уровень: {level_names.get(level, 'Неизвестно')}\n"
            f"🔐 Пароль: {password}\n\n"
            f"⚠️ <b>Сохраните этот пароль!</b>\n"
            f"Администратор должен использовать его для входа командой /admin",
            parse_mode='HTML'
        )
        
        return await show_admin_panel(update, context)
    
    else:
        # Это вход существующего админа
        # Ищем администратора
        admin_data = None
        admin_username = None
        
        # Проверяем все возможные варианты
        for username, data in ADMINS.items():
            # Проверяем пароль
            input_hash = hashlib.sha256(password.encode()).hexdigest()
            
            if hmac.compare_digest(input_hash, data['password_hash']):
                # Проверяем совпадение по telegram_id или username
                if data.get('telegram_id') == user.id or username.lower() == user.username.lower():
                    admin_data = data
                    admin_username = username
                    break
        
        if not admin_data:
            # Пробуем просто найти по паролю (для владельца)
            for username, data in ADMINS.items():
                input_hash = hashlib.sha256(password.encode()).hexdigest()
                if hmac.compare_digest(input_hash, data['password_hash']):
                    admin_data = data
                    admin_username = username
                    break
        
        if not admin_data:
            await update.message.reply_text("❌ Неверный пароль или нет доступа!")
            return AWAITING_PASSWORD
        
        # Сохраняем данные администратора в context
        context.user_data['admin_username'] = admin_username
        context.user_data['admin_level'] = admin_data.get('level', 0)
        
        # СОЗДАЕМ СЕССИЮ (самое важное!)
        session_token = secrets.token_hex(32)
        active_sessions[user.id] = {
            'session_token': session_token,
            'start_time': time.time(),
            'last_activity': time.time(),
            'username': admin_username
        }
        
        # Обновляем время последнего входа
        admin_data['last_login'] = time.time()
        
        await update.message.reply_text("✅ Успешный вход в админ-панель!")
        return await show_admin_panel(update, context)

async def reset_admin_session(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # Удаляем старую сессию
    if user_id in active_sessions:
        del active_sessions[user_id]
    
    await update.message.reply_text(
        "🔄 Сессия сброшена. Попробуйте войти заново командой /admin"
    )
    return ConversationHandler.END

async def process_admin_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    password = update.message.text.strip()
    
    # Ищем администратора
    admin_data = None
    admin_username = None
    
    # Проверяем все возможные варианты
    for username, data in ADMINS.items():
        # Проверяем пароль
        input_hash = hashlib.sha256(password.encode()).hexdigest()
        
        if hmac.compare_digest(input_hash, data['password_hash']):
            # Проверяем совпадение по telegram_id или username
            if data.get('telegram_id') == user.id or username.lower() == user.username.lower():
                admin_data = data
                admin_username = username
                break
    
    if not admin_data:
        # Пробуем просто найти по паролю (для владельца)
        for username, data in ADMINS.items():
            input_hash = hashlib.sha256(password.encode()).hexdigest()
            if hmac.compare_digest(input_hash, data['password_hash']):
                admin_data = data
                admin_username = username
                break
    
    if not admin_data:
        await update.message.reply_text("❌ Неверный пароль или нет доступа!")
        return AWAITING_PASSWORD
    
    # Сохраняем данные администратора в context
    context.user_data['admin_username'] = admin_username
    context.user_data['admin_level'] = admin_data.get('level', 0)
    
    # СОЗДАЕМ СЕССИЮ (самое важное!)
    session_token = secrets.token_hex(32)
    active_sessions[user.id] = {
        'session_token': session_token,
        'start_time': time.time(),
        'last_activity': time.time(),
        'username': admin_username
    }
    
    # Обновляем время последнего входа
    admin_data['last_login'] = time.time()
    
    await update.message.reply_text("✅ Успешный вход в админ-панель!")
    return await show_admin_panel(update, context)

def calculate_total_income(user):
    """Рассчитывает общий доход со всех бизнесов"""
    total_income = 0
    business_count = user.get('business_count', 0)
    
    for i in range(1, business_count + 1):
        biz = BUSINESS_TYPES.get(i)
        if biz:
            total_income += biz['income']
    
    return total_income    
            
async def show_admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user = update.effective_user
        
        # Проверка сессии - ОБЯЗАТЕЛЬНО в начале
        if not is_admin_session_valid(user.id):
            if update.callback_query:
                await update.callback_query.answer("❌ Сессия истекла!", show_alert=True)
                await update.callback_query.edit_message_text("❌ Сессия истекла! Войдите заново командой /admin")
            else:
                await update.message.reply_text("❌ Сессия истекла! Войдите заново командой /admin")
            return ConversationHandler.END
        
        # Обновляем активность сессии
        active_sessions[user.id]['last_activity'] = time.time()
        
        # Получаем данные из context или активной сессии
        admin_username = context.user_data.get('admin_username')
        admin_level = context.user_data.get('admin_level', 0)
        
        # Если нет в контексте, ищем в активных сессиях
        if not admin_username and user.id in active_sessions:
            admin_username = active_sessions[user.id]['username']
            # Ищем уровень в ADMINS
            if admin_username in ADMINS:
                admin_level = ADMINS[admin_username].get('level', 0)
        
        if not admin_username:
            # Если все еще нет - проверяем по telegram_id или username
            for username, data in ADMINS.items():
                if data.get('telegram_id') == user.id or username.lower() == user.username.lower():
                    admin_username = username
                    admin_level = data.get('level', 0)
                    break
            
            if not admin_username:
                if update.callback_query:
                    await update.callback_query.answer("❌ Нет доступа!", show_alert=True)
                    await update.callback_query.message.reply_text("❌ Нет доступа к админ-панели!")
                else:
                    await update.message.reply_text("❌ Нет доступа к админ-панели!")
                return ConversationHandler.END
        
        # Сохраняем в context
        context.user_data['admin_username'] = admin_username
        context.user_data['admin_level'] = admin_level
        
        # Получаем полные данные администратора
        admin_data = ADMINS.get(admin_username, {})
        if not admin_data:
            if update.callback_query:
                await update.callback_query.answer("❌ Данные не найдены!", show_alert=True)
                await update.callback_query.message.reply_text("❌ Данные администратора не найдены!")
            else:
                await update.message.reply_text("❌ Данные администратора не найдены!")
            return ConversationHandler.END
        
        # Генерируем простой токен (не CSRF, просто для уникальности)
        simple_token = secrets.token_hex(8)
        
        # Добавляем информацию о лимитах
        limits_text = ""
        if 'daily_limit' in admin_data:
            today = datetime.now().strftime('%Y-%m-%d')
            if 'daily_usage' not in admin_data or admin_data['daily_usage']['date'] != today:
                admin_data['daily_usage'] = {'date': today, 'money': 0, 'coins': 0}
            
            money_used = admin_data['daily_usage']['money']
            coins_used = admin_data['daily_usage']['coins']
            money_limit = admin_data['daily_limit'].get('money', '∞')
            coins_limit = admin_data['daily_limit'].get('coins', '∞')
            
            limits_text = (
                f"\n📊 Лимиты сегодня:\n"
                f"💰 Деньги: {money_used:,}/{'∞' if money_limit == float('inf') else f'{money_limit:,}'}\n"
                f"🪙 Койны: {coins_used}/{'∞' if coins_limit == float('inf') else coins_limit}"
            )
        
        # Создаем клавиатуру
        keyboard = [
            [
                InlineKeyboardButton("📊 Статистика", callback_data=f"adm:stats:{simple_token}"),
                InlineKeyboardButton("👥 Пользователи", callback_data=f"adm:users:{simple_token}")
            ]
        ]
        
        if admin_level >= 1:
            keyboard.append([
                InlineKeyboardButton("⚠️ Варн", callback_data=f"adm:warn:{simple_token}"),
                InlineKeyboardButton("🔨 Бан", callback_data=f"adm:ban:{simple_token}")
            ])
        
        if admin_level >= 2:
            keyboard.append([
                InlineKeyboardButton("🔓 Разбан", callback_data=f"adm:unban:{simple_token}"),
                InlineKeyboardButton("📝 Логи", callback_data=f"adm:logs:{simple_token}")
            ])
        
        if admin_level >= 3:
            keyboard.extend([
                [
                    InlineKeyboardButton("💰 Начислить", callback_data=f"adm:add:{simple_token}"),
                    InlineKeyboardButton("➖ Снять", callback_data=f"adm:rem:{simple_token}")
                ],
                [
                    InlineKeyboardButton("🎫 Промокоды", callback_data=f"adm:promo:{simple_token}"),
                    InlineKeyboardButton("👥 Управление админами", callback_data=f"adm:manage_admins:{simple_token}")
                ],
                [
                    InlineKeyboardButton("👑 Админы", callback_data=f"adm:admins:{simple_token}")
                ]
            ])
        
        keyboard.append([
            InlineKeyboardButton("🔄 Обновить", callback_data=f"adm:ref:{simple_token}"),
            InlineKeyboardButton("🔒 Выход", callback_data=f"adm:out:{simple_token}")
        ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        level_names = {
            1: "👮 Модератор",
            2: "🛡 Администратор", 
            3: "👑 Владелец"
        }
        
        message_text = (
            "👑 <b>Админ-панель</b>\n\n"
            f"👤 Пользователь: @{user.username or 'N/A'}\n"
            f"🛡 Уровень: {level_names.get(admin_level, 'Неизвестно')}"
            f"{limits_text}"
        )
        
        if update.callback_query:
            try:
                await update.callback_query.edit_message_text(
                    message_text,
                    reply_markup=reply_markup,
                    parse_mode='HTML'
                )
            except Exception as e:
                logging.error(f"Ошибка редактирования: {e}")
                await update.callback_query.message.reply_text(
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
        
        return ADMIN_PANEL
        
    except Exception as e:
        logging.error(f"Error in show_admin_panel: {e}", exc_info=True)
        
        error_text = "⚠️ Произошла ошибка"
        
        if update.callback_query:
            try:
                await update.callback_query.edit_message_text(error_text)
            except:
                await update.callback_query.message.reply_text(error_text)
        else:
            await update.message.reply_text(error_text)
        
        return ConversationHandler.END

async def check_investments(context: ContextTypes.DEFAULT_TYPE):
    """Проверяет завершенные инвестиции"""
    current_time = time.time()
    completed_count = 0
    
    for user_id, investments in list(user_investments.items()):
        for comp_id, inv in list(investments.items()):
            end_time = inv['start_time'] + (inv['days'] * 86400)
            if current_time >= end_time and 'completed' not in inv:
                # Инвестиция завершена
                company = INVESTMENT_COMPANIES.get(comp_id, {})
                if company:
                    # Рассчитываем прибыль
                    min_return = company['base_return'] - company['volatility']
                    max_return = company['base_return'] + company['volatility']
                    profit_mult = random.uniform(min_return, max_return)
                    profit = int(inv['amount'] * profit_mult)
                    
                    # Отмечаем как завершенную
                    inv['completed'] = True
                    inv['profit'] = profit
                    inv['profit_mult'] = profit_mult
                    
                    # Уведомляем пользователя
                    try:
                        await context.bot.send_message(
                            chat_id=int(user_id),
                            text=(
                                f"🎉 <b>ИНВЕСТИЦИЯ ЗАВЕРШЕНА!</b>\n\n"
                                f"{company['color']} {company['name']} {company['emoji']}\n"
                                f"💰 Вложено: {inv['amount']:,} ₽\n"
                                f"📈 Получено: {profit:,} ₽\n"
                                f"💵 Прибыль: {profit - inv['amount']:,} ₽\n\n"
                                f"Используйте /claim чтобы получить деньги!"
                            ),
                            parse_mode='HTML'
                        )
                    except:
                        pass
                    
                    completed_count += 1
    
    if completed_count > 0:
        save_investments()
        logging.info(f"✅ Завершено {completed_count} инвестиций")

async def admin_actions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    # Проверка сессии
    if not is_admin_session_valid(query.from_user.id):
        await query.answer("❌ Сессия истекла!", show_alert=True)
        await query.edit_message_text("❌ Сессия истекла! Войдите заново командой /admin")
        return ConversationHandler.END
    
    # Обновляем активность
    active_sessions[query.from_user.id]['last_activity'] = time.time()
    
    try:
        data = query.data.split(':')
        if len(data) != 3:
            await query.edit_message_text("⚠️ Ошибка формата!")
            return
        
        prefix, action, _ = data  # Игнорируем токен
        
        if prefix != 'adm':
            await query.edit_message_text("⚠️ Неизвестное действие!")
            return
        
        # Получаем уровень из context
        admin_level = context.user_data.get('admin_level', 0)
        
        # Проверяем права
        if action in ('ban', 'unban', 'warn') and admin_level < 1:
            await query.answer("⛔ Недостаточно прав!", show_alert=True)
            return
            
        if action in ('add', 'rem', 'admins', 'promo', 'create_promo', 'list_promo', 'delete_promo', 
                      'manage_admins', 'add_admin', 'edit_admin', 'remove_admin', 'list_admins') and admin_level < 3:
            await query.answer("⛔ Только для владельца!", show_alert=True)
            return
        
        # Обработка действий
        if action == 'stats':
            total_users = len(user_data)
            active_users = sum(1 for u in user_data.values() if 'last_active' in u and time.time() - u['last_active'] < 86400)
            total_balance = sum(u.get('balance', 0) for u in user_data.values())
            total_coins = sum(u.get('coins', 0) for u in user_data.values())
            total_businesses = sum(u.get('business_count', 0) for u in user_data.values())
            total_referrals = sum(len(u.get('referrals', [])) for u in user_data.values())
            
            stats_text = (
                f"📊 <b>Статистика бота</b>\n\n"
                f"👥 Всего пользователей: {total_users}\n"
                f"🟢 Активных за сутки: {active_users}\n"
                f"💰 Общий баланс: {total_balance:,} ₽\n"
                f"🪙 Всего койнов: {total_coins:,}\n"
                f"🏢 Всего бизнесов: {total_businesses}\n"
                f"📨 Всего рефералов: {total_referrals}\n"
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
                    logs = f.read()[-4000:]
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
            
        elif action == 'promo':
            keyboard = [
                [InlineKeyboardButton("➕ Создать промокод", callback_data=f"adm:create_promo:token")],
                [InlineKeyboardButton("📊 Список промокодов", callback_data=f"adm:list_promo:token")],
                [InlineKeyboardButton("❌ Удалить промокод", callback_data=f"adm:delete_promo:token")],
                [InlineKeyboardButton("🔙 Назад", callback_data=f"adm:ref:token")]
            ]
            
            promo_text = "🎫 Управление промокодами:\n\n"
            promo_text += f"📊 Активных промокодов: {len(PROMOCODES)}\n"
            promo_text += "🔄 Использовано всего: " + str(sum(p.get('used', 0) for p in PROMOCODES.values())) + "\n\n"
            
            await query.edit_message_text(
                promo_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='HTML'
            )
            return ADMIN_PANEL
            
        elif action == 'manage_admins':
            keyboard = [
                [InlineKeyboardButton("➕ Добавить админа", callback_data=f"adm:add_admin:token")],
                [InlineKeyboardButton("⚙️ Изменить уровень", callback_data=f"adm:edit_admin:token")],
                [InlineKeyboardButton("🔐 Сменить пароль", callback_data=f"adm:change_password:token")],
                [InlineKeyboardButton("❌ Удалить админа", callback_data=f"adm:remove_admin:token")],
                [InlineKeyboardButton("📊 Список админов", callback_data=f"adm:list_admins:token")],
                [InlineKeyboardButton("🔙 Назад", callback_data=f"adm:ref:token")]
            ]
            
            admin_count = len(ADMINS)
            level_counts = {1: 0, 2: 0, 3: 0}
            for data in ADMINS.values():
                level = data.get('level', 0)
                if level in level_counts:
                    level_counts[level] += 1
            
            admin_text = (
                "👥 Управление администраторами:\n\n"
                f"📊 Всего админов: {admin_count}\n"
                f"👑 Владельцев (уровень 3): {level_counts[3]}\n"
                f"🛡 Администраторов (уровень 2): {level_counts[2]}\n"
                f"👮 Модераторов (уровень 1): {level_counts[1]}\n\n"
                "Уровни доступа:\n"
                "3️⃣ Владелец - полный доступ ко всем функциям\n"
                "2️⃣ Администратор - бан, разбан, начисление, снятие\n"
                "1️⃣ Модератор - бан, разбан, предупреждения"
            )
            
            await query.edit_message_text(
                admin_text,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return ADMIN_PANEL
            
        elif action == 'create_promo':
            context.user_data['admin_action'] = 'create_promo'
            await query.edit_message_text("Введите название промокода (латинские буквы, без пробелов):")
            return AWAITING_PROMO_NAME
            
        elif action == 'list_promo':
            if not PROMOCODES:
                await query.edit_message_text("❌ Нет активных промокодов.")
                return ADMIN_PANEL
            
            promo_text = "📊 Список промокодов:\n\n"
            for code, data in PROMOCODES.items():
                used = data.get('used', 0)
                max_uses = data.get('max_uses', 0)
                money = data.get('reward', {}).get('money', 0)
                coins = data.get('reward', {}).get('coins', 0)
                item = data.get('reward', {}).get('item', 'Нет')
                
                expires = data.get('expires') if data.get('expires') else "Без срока"
                min_level = data.get('min_level', 0)
                created_by = data.get('created_by', 'N/A')
                
                promo_text += (
                    f"🎫 <b>{code}</b>\n"
                    f"💰 Деньги: {money:,} ₽ | 🪙 Койны: {coins}\n"
                    f"🎁 Предмет: {item}\n"
                    f"📊 Использовано: {used}/{max_uses}\n"
                    f"📅 Срок: {expires}\n"
                    f"📈 Мин. уровень: {min_level}\n"
                    f"👤 Создал: @{created_by}\n\n"
                )
            
            await query.edit_message_text(promo_text, parse_mode='HTML')
            return ADMIN_PANEL
            
        elif action == 'delete_promo':
            context.user_data['admin_action'] = 'delete_promo'
            await query.edit_message_text("Введите название промокода для удаления:")
            return AWAITING_PROMO_NAME
            
        elif action == 'add_admin':
            context.user_data['admin_action'] = 'add_admin'
            await query.edit_message_text("Введите @username пользователя для добавления в администраторы:")
            return AWAITING_ADMIN_USERNAME
            
        elif action == 'edit_admin':
            context.user_data['admin_action'] = 'edit_admin'
            await query.edit_message_text("Введите @username администратора для изменения уровня:")
            return AWAITING_ADMIN_USERNAME
            
        elif action == 'change_password':
            context.user_data['admin_action'] = 'change_password'
            await query.edit_message_text("Введите @username администратора для смены пароля:")
            return AWAITING_ADMIN_USERNAME
            
        elif action == 'remove_admin':
            context.user_data['admin_action'] = 'remove_admin'
            await query.edit_message_text("Введите @username администратора для удаления:")
            return AWAITING_ADMIN_USERNAME
            
        elif action == 'list_admins':
            admins_text = "👑 Список администраторов:\n\n"
            
            sorted_admins = sorted(ADMINS.items(), key=lambda x: x[1].get('level', 0), reverse=True)
            
            for username, data in sorted_admins:
                level = data.get('level', 0)
                level_name = {
                    3: "👑 Владелец",
                    2: "🛡 Администратор", 
                    1: "👮 Модератор"
                }.get(level, "❓ Неизвестно")
                
                last_login = datetime.fromtimestamp(data['last_login']).strftime('%d.%m.%Y %H:%M') if data.get('last_login') else "Никогда"
                created_at = datetime.fromisoformat(data.get('created_at', datetime.now().isoformat())).strftime('%d.%m.%Y') if data.get('created_at') else "Неизвестно"
                created_by = f"@{data.get('created_by', 'N/A')}"
                
                admins_text += (
                    f"{level_name} (@{username})\n"
                    f"🆔 ID: {data.get('telegram_id', 'N/A')}\n"
                    f"📅 Создан: {created_at}\n"
                    f"👤 Создал: {created_by}\n"
                    f"🕒 Последний вход: {last_login}\n"
                    f"💰 Лимит в день: {data.get('daily_limit', {}).get('money', 0):,} ₽\n"
                    f"🪙 Койнов в день: {data.get('daily_limit', {}).get('coins', 0)}\n\n"
                )
            
            await query.edit_message_text(admins_text)
            return ADMIN_PANEL
            
        elif action == 'ref':
            return await show_admin_panel(update, context)
            
        elif action == 'out':
            # Очищаем context и удаляем сессию
            user_id = query.from_user.id
            if user_id in active_sessions:
                del active_sessions[user_id]
            context.user_data.clear()
            await query.edit_message_text("✅ Вы вышли из админ-панели.")
            return ConversationHandler.END

    except Exception as e:
        logging.error(f"Error in admin_actions: {e}", exc_info=True)
        await query.edit_message_text("⚠️ Произошла ошибка при обработке запроса.")
        return ConversationHandler.END
 
async def sell_coin_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Продажа койна"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    user = get_user_data(user_id)
    
    # Проверяем наличие койнов
    if user.get('coins', 0) > 0:
        # Списываем 1 койн
        user['coins'] = user.get('coins', 0) - 1
        # Начисляем 100кк
        user['balance'] += 100_000_000
        
        save_data()
        
        await query.answer("✅ +100,000,000 ₽! Койн продан!", show_alert=True)
        
        # Возвращаемся в магазин
        return await shop_consumables_menu(update, context)
    else:
        await query.answer("❌ У вас нет койнов!", show_alert=True)
        return SHOP_MENU  
    
async def reset_progress(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Полный сброс прогресса пользователя"""
    user_id = str(update.effective_user.id)
    
    # Подтверждение
    keyboard = [
        [InlineKeyboardButton("✅ ДА, СБРОСИТЬ", callback_data="reset_confirm")],
        [InlineKeyboardButton("❌ ОТМЕНА", callback_data="reset_cancel")]
    ]
    
    await update.message.reply_text(
        "⚠️ <b>ВНИМАНИЕ!</b>\n\n"
        "Вы собираетесь полностью сбросить свой прогресс:\n"
        "• Все бизнесы будут удалены\n"
        "• Баланс станет 100,000 ₽\n"
        "• Койны обнулятся\n"
        "• Статистика казино обнулится\n"
        "• Достижения будут удалены\n"
        "• Инвестиции пропадут\n\n"
        "<b>Это действие необратимо!</b>\n\n"
        "Вы уверены?",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )

async def reset_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик подтверждения сброса"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    data = query.data
    
    if data == "reset_cancel":
        await query.edit_message_text("❌ Сброс отменён.")
        return
    
    if data == "reset_confirm":
        # Сохраняем важные данные перед сбросом
        old_username = user_data[user_id].get('username')
        old_referral_code = user_data[user_id].get('referral_code')
        old_referred_by = user_data[user_id].get('referred_by')
        old_referrals = user_data[user_id].get('referrals', [])
        
        # ПОЛНЫЙ СБРОС - создаем нового пользователя с нуля
        user_data[user_id] = {
            'balance': 100000,
            'coins': 0,
            'accountant_uses': 0,
            'last_accountant_date': None,
            'businesses': [],
            'last_taxi_time': None,
            'last_business_income': datetime.now().isoformat(),  # Важно! Ставим текущее время
            'username': old_username,
            'last_active': time.time(),
            'referral_code': old_referral_code,
            'referred_by': old_referred_by,
            'referrals': old_referrals,
            'business_count': 0,  # Сбрасываем бизнесы в 0
            'inventory': {
                'boxes': 0,
                'items': []
            },
            'used_promocodes': [],
            'promocode_used': 0,
            'jobs': {
                'taxi': {'level': 1, 'completed': 0, 'last_work': None},
                'accountant': {'level': 1, 'completed': 0, 'last_work': None},
                'builder': {'level': 1, 'completed': 0, 'last_work': None},
                'businessman': {'level': 1, 'completed': 0, 'last_work': None}
            }
        }
        
        # Очищаем дополнительные данные
        if user_id in user_items:
            del user_items[user_id]
        
        if user_id in user_investments:
            del user_investments[user_id]
        
        if user_id in casino_stats:
            del casino_stats[user_id]
        
        if 'premium_items' in globals() and user_id in premium_items:
            del premium_items[user_id]
        
        if user_id in user_consumables:
            del user_consumables[user_id]
        
        if user_id in vip_users:
            del vip_users[user_id]
        
        # Сохраняем изменения
        save_data()
        save_user_items()
        save_investments()
        save_casino_stats()
        if 'premium_items' in globals():
            save_premium_items()
        save_consumables()
        save_vip()
        
        await query.edit_message_text(
            "✅ <b>ПРОГРЕСС СБРОШЕН!</b>\n\n"
            "Ваш аккаунт полностью очищен:\n"
            "💰 Баланс: 100,000 ₽\n"
            "🏢 Бизнесов: 0\n"
            "🪙 Койны: 0\n\n"
            "Можете начинать заново!",
            parse_mode='HTML'
        )
        
special_user_id =  8413010389       
async def reset_my_businesses(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обнулить свои бизнесы"""
        user_id = update.effective_user.id
        
        if user_id != special_user_id:
            await update.message.reply_text("❌ Эта команда только для тебя!")
            return
        
        user = get_user_data(user_id)
        
        user['businesses'] = {}
        user['business_income'] = 0
        user['next_business_income_time'] = time.time() + 1800
        
        save_data()
        
        await update.message.reply_text(
            "✅ Твои бизнесы обнулены!\n"
            "Теперь можешь покупать новые."
        ) 
               
async def get_groups_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает все группы, где есть бот (только для админа)"""
    user_id = update.effective_user.id
    
    if user_id != 7990799592:
        await update.message.reply_text("❌ У вас нет прав!")
        return
    
    groups = []
    
    # Проходим по всем обновлениям в памяти
    for key in context.bot_data:
        if key.startswith('group_'):
            groups.append(context.bot_data[key])
    
    if not groups:
        await update.message.reply_text("📊 Бот не найден ни в одной группе.")
        return
    
    text = "📊 <b>ГРУППЫ С БОТОМ</b>\n═══════════════\n\n"
    for group in groups:
        text += f"👥 {group['title']}\n"
        text += f"├ ID: {group['id']}\n"
        text += f"└ Ссылка: {group['link']}\n\n"
    
    await update.message.reply_text(text, parse_mode='HTML')
# ==================== MINES ИГРА ====================

# Команда для открытия игры
# ==================== MINES ИГРА ====================
# Добавь это в любое место файла (лучше в конец)

async def mines_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Открывает игру Mines"""
    
    GAME_URL = "https://pvpbro.github.io/Mines/"
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("💣 ИГРАТЬ В MINES", web_app=WebAppInfo(url=GAME_URL))]
    ])
    
    await update.message.reply_text(
        "🎮 Нажми кнопку, чтобы открыть игру Mines!",
        reply_markup=keyboard
    )

async def test_webapp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Тестовый обработчик"""
    print("🔥🔥🔥 WEBAPP DATA ПОЛУЧЕНА!")
    print(update)
    print(update.effective_message)
    

async def mines_webapp_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает данные из игры Mines"""
    web_app_data = update.effective_message.web_app_data
    
    print(f"🔍 ПРОВЕРКА: {web_app_data}")
    
    if not web_app_data:
        print("❌ Нет данных")
        return
    
    print(f"✅ ЕСТЬ ДАННЫЕ: {web_app_data.data}")
    
    try:
        data = json.loads(web_app_data.data)
        print(f"📦 РАСПАРСЕНО: {data}")
        
        user_id = str(data.get('user_id'))
        action = data.get('action')
        
        print(f"👤 User ID: {user_id}, Action: {action}")
        
        user = get_user_data(user_id)
        
        if action == 'get_balance':
            response = {
                'action': 'balance_updated',
                'balance': user['balance']
            }
            await update.effective_message.reply_web_app_data(json.dumps(response))
            print(f"💰 Баланс {user['balance']} отправлен")
            
    except Exception as e:
        print(f"❌ Ошибка: {e}")



async def open_mines(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Открывает игру Mines"""
    
    # URL твоего сайта на GitHub Pages
    GAME_URL = "https://pvpbro.github.io/Mines/"
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("💣 ИГРАТЬ В MINES", web_app=WebAppInfo(url=GAME_URL))]
    ])
    
    await update.message.reply_text(
        "🎮 Нажми кнопку, чтобы открыть игру Mines!\n\n"
        "Правила:\n"
        "• Открывай клетки с самоцветами 💎\n"
        "• Не попади на мину 💣\n"
        "• Множитель растет с каждым ходом\n"
        "• Забери выигрыш в любой момент",
        reply_markup=keyboard
    )
    
async def handle_mines_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает данные из игры Mines"""
    web_app_data = update.effective_message.web_app_data
    
    if not web_app_data:
        return
    
    try:
        data = json.loads(web_app_data.data)
        user_id = str(data.get('user_id'))
        action = data.get('action')
        
        user = get_user_data(user_id)
        
        if action == 'get_balance':
            # Отправляем баланс в приложение
            response = {
                'action': 'balance_updated',
                'balance': user['balance']
            }
            await update.effective_message.reply_web_app_data(json.dumps(response))
            
        elif action == 'start_game':
            bet = data.get('bet')
            
            if bet > user['balance']:
                response = {
                    'action': 'error',
                    'message': 'Недостаточно средств'
                }
                await update.effective_message.reply_web_app_data(json.dumps(response))
                return
            
            # Создаем новую игру
            game_id = str(uuid.uuid4())
            
            # Генерируем мины
            import random
            all_cells = list(range(25))
            mines = random.sample(all_cells, 3)
            
            # Сохраняем игру
            if 'mines_games' not in context.bot_data:
                context.bot_data['mines_games'] = {}
            
            context.bot_data['mines_games'][game_id] = {
                'user_id': user_id,
                'bet': bet,
                'mines': mines,
                'opened': [],
                'active': True,
                'multiplier': 1.0
            }
            
            # Списываем ставку
            user['balance'] -= bet
            save_data()
            
            response = {
                'action': 'game_started',
                'game_id': game_id,
                'game_active': True,
                'game_over': False,
                'mines': [],
                'opened': [],
                'multiplier': 1.0,
                'new_balance': user['balance']
            }
            await update.effective_message.reply_web_app_data(json.dumps(response))
            
        elif action == 'open_cell':
            game_id = data.get('game_id')
            cell = data.get('cell')
            
            game = context.bot_data['mines_games'].get(game_id)
            if not game or not game['active']:
                return
            
            if cell in game['opened']:
                return
            
            game['opened'].append(cell)
            
            # Множители
            multipliers = [1.0, 1.2, 1.5, 1.9, 2.4, 3.0, 3.8, 4.8, 6.0, 7.5, 9.4, 11.8, 14.8, 18.5, 23.1, 28.9, 36.1, 45.1, 56.4, 70.5, 88.1, 110.1, 137.6, 172.0, 215.0]
            
            # Проверяем, мина ли это
            is_mine = cell in game['mines']
            
            if is_mine:
                game['active'] = False
                response = {
                    'action': 'cell_opened',
                    'mine': True,
                    'game_active': False,
                    'game_over': True,
                    'mines': game['mines'],
                    'opened': game['opened'],
                    'multiplier': game['multiplier'],
                    'new_balance': user['balance']
                }
            else:
                game['multiplier'] = multipliers[len(game['opened'])]
                response = {
                    'action': 'cell_opened',
                    'mine': False,
                    'game_active': True,
                    'game_over': False,
                    'mines': [],
                    'opened': game['opened'],
                    'multiplier': game['multiplier'],
                    'new_balance': user['balance']
                }
            
            await update.effective_message.reply_web_app_data(json.dumps(response))
            
        elif action == 'cash_out':
            game_id = data.get('game_id')
            game = context.bot_data['mines_games'].get(game_id)
            
            if not game or not game['active']:
                return
            
            win_amount = int(game['bet'] * game['multiplier'])
            user['balance'] += win_amount
            
            game['active'] = False
            
            response = {
                'action': 'cashed_out',
                'win_amount': win_amount,
                'game_active': False,
                'game_over': True,
                'mines': game['mines'],
                'opened': game['opened'],
                'multiplier': game['multiplier'],
                'new_balance': user['balance']
            }
            
            save_data()
            await update.effective_message.reply_web_app_data(json.dumps(response))
            
    except Exception as e:
        logging.error(f"Ошибка в mines handler: {e}")
        response = {
            'action': 'error',
            'message': 'Ошибка сервера'
        }
        await update.effective_message.reply_web_app_data(json.dumps(response))    

def get_consumables(user_id):
    """Получить расходники пользователя"""
    user_id = str(user_id)
    if user_id not in user_consumables:
        user_consumables[user_id] = {}
    return user_consumables[user_id]

def add_consumable(user_id, item_id, count=1):
    """Добавить расходник пользователю"""
    user_id = str(user_id)
    if user_id not in user_consumables:
        user_consumables[user_id] = {}
    user_consumables[user_id][item_id] = user_consumables[user_id].get(item_id, 0) + count
    save_consumables()

def remove_consumable(user_id, item_id, count=1):
    """Удалить расходник у пользователя"""
    user_id = str(user_id)
    if user_id in user_consumables and item_id in user_consumables[user_id]:
        if user_consumables[user_id][item_id] >= count:
            user_consumables[user_id][item_id] -= count
            if user_consumables[user_id][item_id] <= 0:
                del user_consumables[user_id][item_id]
            save_consumables()
            return True
    return False

def save_consumables():
    """Сохранить расходники"""
    try:
        with open('consumables.json', 'w', encoding='utf-8') as f:
            json.dump(user_consumables, f, ensure_ascii=False, indent=4)
    except Exception as e:
        logging.error(f"Ошибка сохранения расходников: {e}")

def load_consumables():
    """Загрузить расходники"""
    global user_consumables
    try:
        if os.path.exists('consumables.json'):
            with open('consumables.json', 'r', encoding='utf-8') as f:
                user_consumables = json.load(f)
    except Exception as e:
        logging.error(f"Ошибка загрузки расходников: {e}")
        user_consumables = {}

async def check_all_achievements(update, user_id, user_data):
    """Проверяет все достижения и начисляет награды"""
    if 'achievements' not in user_data:
        user_data['achievements'] = {}
    
    new_achs = []
    total_reward = 0
    
    for ach_id, ach in ACHIEVEMENTS.items():
        if ach_id in user_data['achievements']:
            continue
        
        try:
            if ach['condition'](user_data):
                user_data['achievements'][ach_id] = {
                    'unlocked_at': time.time(),
                    'reward_claimed': True
                }
                user_data['balance'] += ach['reward']
                total_reward += ach['reward']
                new_achs.append(ach['name'])
        except:
            pass
    
    if new_achs:
        text = "🎉 <b>НОВЫЕ ДОСТИЖЕНИЯ!</b>\n\n"
        for ach in new_achs:
            text += f"• {ach}\n"
        text += f"\n💰 Получено: {total_reward:,} ₽"
        
        if update and update.message:
            await update.message.reply_text(text, parse_mode='HTML')
        elif update and update.callback_query:
            await update.callback_query.message.reply_text(text, parse_mode='HTML')
    
    save_data()

async def pvp_dice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Создание PvP игры в кости"""
    # Проверяем, что это группа
    if update.message.chat.type not in ('group', 'supergroup'):
        await update.message.reply_text("❌ Эта игра доступна только в группах!")
        return
    
    user_id = update.message.from_user.id
    if user_id in banned_users:
        return
    
    # Получаем текст сообщения
    text = update.message.text.lower()
    parts = text.split()
    
    if len(parts) != 3:
        await update.message.reply_text(
            "🎲 <b>PVP КОСТИ</b>\n\n"
            "Использование:\n"
            "• /pvp @username [сумма]\n"
            "• лот @username [сумма]\n\n"
            "Пример: /pvp @friend 100000\n\n"
            "Правила:\n"
            "• Создатель ставит сумму\n"
            "• Соперник должен принять (тратит столько же)\n"
            "• Оба кидают кубик (1-6)\n"
            "• У кого больше - забирает всё",
            parse_mode='HTML'
        )
        return
    
    target_username = parts[1].lstrip('@')
    amount = parse_bet_amount(parts[2])
    
    if not amount or amount <= 0:
        await update.message.reply_text("❌ Неверная сумма!")
        return
    
    if amount < 1000:
        await update.message.reply_text("❌ Минимальная ставка: 1,000 ₽")
        return
    
    # Получаем данные создателя
    creator = get_user_data(user_id)
    
    if amount > creator['balance']:
        await update.message.reply_text(f"❌ У вас недостаточно средств! Баланс: {creator['balance']:,} ₽")
        return
    
    # Ищем соперника
    opponent_id = None
    for uid, u_data in user_data.items():
        saved_username = u_data.get('username')
        if saved_username and saved_username.lower() == target_username.lower():
            opponent_id = uid
            opponent_name = saved_username
            break
    
    if not opponent_id:
        await update.message.reply_text("❌ Пользователь не найден!")
        return
    
    if opponent_id == user_id:
        await update.message.reply_text("❌ Нельзя играть с самим собой!")
        return
    
    # Создаем игру
    game_id = secrets.token_hex(4)
    pvp_games[game_id] = {
        'creator': str(user_id),
        'creator_name': creator.get('username', str(user_id)),
        'opponent': str(opponent_id),
        'opponent_name': target_username,
        'amount': amount,
        'status': 'waiting',
        'created_at': time.time(),
        'message_id': None
    }
    
    # Списываем деньги у создателя
    creator['balance'] -= amount
    save_data()
    
    # Создаем клавиатуру для соперника
    keyboard = [
        [
            InlineKeyboardButton("✅ ПРИНЯТЬ", callback_data=f"pvp_accept_{game_id}"),
            InlineKeyboardButton("❌ ОТКАЗАТЬСЯ", callback_data=f"pvp_decline_{game_id}")
        ]
    ]
    
    message = await update.message.reply_text(
        f"🎲 <b>PVP КОСТИ</b>\n\n"
        f"👤 @{creator.get('username', 'Игрок')} вызывает @{target_username}!\n"
        f"💰 Ставка: {amount:,} ₽\n\n"
        f"⏳ У @{target_username} есть 5 минут, чтобы принять",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )
    
    pvp_games[game_id]['message_id'] = message.message_id
    
    # Запускаем таймер на удаление
    context.job_queue.run_once(
        pvp_game_timeout,
        PVP_GAME_TIME,
        data={'game_id': game_id, 'chat_id': update.message.chat_id},
        name=f"pvp_{game_id}"
    )

async def pvp_accept(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Принять PvP игру"""
    query = update.callback_query
    await query.answer()
    
    game_id = query.data.replace("pvp_accept_", "")
    
    if game_id not in pvp_games:
        await query.edit_message_text("❌ Игра не найдена или уже завершена!")
        return
    
    game = pvp_games[game_id]
    user_id = str(query.from_user.id)
    
    # Проверяем, что это нужный игрок
    if user_id != game['opponent']:
        await query.answer("❌ Это не ваша игра!", show_alert=True)
        return
    
    if game['status'] != 'waiting':
        await query.answer("❌ Игра уже начата или завершена!", show_alert=True)
        return
    
    # Получаем данные соперника
    opponent = get_user_data(user_id)
    
    # Проверяем деньги
    if game['amount'] > opponent['balance']:
        await query.edit_message_text(
            f"❌ У вас недостаточно средств! Нужно: {game['amount']:,} ₽"
        )
        # Удаляем игру
        del pvp_games[game_id]
        return
    
    # Списываем деньги у соперника
    opponent['balance'] -= game['amount']
    save_data()
    
    # Меняем статус
    game['status'] = 'active'
    
    # Получаем данные создателя
    creator = get_user_data(game['creator'])
    
    # Бросаем кости
    creator_roll = random.randint(1, 6)
    opponent_roll = random.randint(1, 6)
    
    result_text = (
        f"🎲 <b>PVP КОСТИ - РЕЗУЛЬТАТ</b>\n\n"
        f"👤 @{game['creator_name']}: {creator_roll}\n"
        f"👤 @{game['opponent_name']}: {opponent_roll}\n\n"
    )
    
    if creator_roll > opponent_roll:
        winner_id = game['creator']
        winner_name = game['creator_name']
        winner = creator
        winner['balance'] += game['amount'] * 2
        result_text += f"🎉 <b>ПОБЕДИТЕЛЬ: @{winner_name}</b>\n"
        result_text += f"💰 Выигрыш: {game['amount'] * 2:,} ₽"
    elif opponent_roll > creator_roll:
        winner_id = game['opponent']
        winner_name = game['opponent_name']
        winner = opponent
        winner['balance'] += game['amount'] * 2
        result_text += f"🎉 <b>ПОБЕДИТЕЛЬ: @{winner_name}</b>\n"
        result_text += f"💰 Выигрыш: {game['amount'] * 2:,} ₽"
    else:
        # Ничья - возвращаем деньги
        creator['balance'] += game['amount']
        opponent['balance'] += game['amount']
        result_text += f"🤝 <b>НИЧЬЯ!</b>\n"
        result_text += f"💰 Деньги возвращены"
    
    save_data()
    
    await query.edit_message_text(result_text, parse_mode='HTML')
    
    # Удаляем игру
    del pvp_games[game_id]

async def pvp_decline(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отказаться от PvP игры"""
    query = update.callback_query
    await query.answer()
    
    game_id = query.data.replace("pvp_decline_", "")
    
    if game_id not in pvp_games:
        await query.edit_message_text("❌ Игра не найдена!")
        return
    
    game = pvp_games[game_id]
    user_id = str(query.from_user.id)
    
    # Проверяем, что это нужный игрок
    if user_id != game['opponent']:
        await query.answer("❌ Это не ваша игра!", show_alert=True)
        return
    
    # Возвращаем деньги создателю
    creator = get_user_data(game['creator'])
    creator['balance'] += game['amount']
    save_data()
    
    await query.edit_message_text(
        f"❌ @{game['opponent_name']} отказался от игры.\n"
        f"💰 Деньги возвращены @{game['creator_name']}"
    )
    
    # Удаляем игру
    del pvp_games[game_id]

async def pvp_game_timeout(context: ContextTypes.DEFAULT_TYPE):
    """Таймаут PvP игры"""
    job = context.job
    game_id = job.data['game_id']
    chat_id = job.data['chat_id']
    
    if game_id in pvp_games:
        game = pvp_games[game_id]
        
        if game['status'] == 'waiting':
            # Возвращаем деньги создателю
            creator = get_user_data(game['creator'])
            creator['balance'] += game['amount']
            save_data()
            
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"⏳ Время вышло. @{game['opponent_name']} не принял игру.\n"
                     f"💰 Деньги возвращены @{game['creator_name']}"
            )
            
            del pvp_games[game_id]

def check_achievements(user_id, user_data):
    """Проверяет и начисляет новые достижения"""
    user_id = str(user_id)
    
    if 'achievements' not in user_data:
        user_data['achievements'] = {}
    
    new_achievements = []
    total_reward = 0
    
    for ach_id, ach_data in ACHIEVEMENTS.items():
        # Проверяем, не получено ли уже достижение
        if ach_id in user_data['achievements']:
            continue
        
        # Проверяем условие
        try:
            if ach_data['condition'](user_data):
                # Получаем достижение
                user_data['achievements'][ach_id] = {
                    'unlocked_at': time.time(),
                    'reward_claimed': True
                }
                
                # Начисляем награду
                user_data['balance'] += ach_data['reward']
                total_reward += ach_data['reward']
                
                new_achievements.append(ach_data['name'])
                
                # Обновляем статистику
                if 'total_achievements' not in user_data:
                    user_data['total_achievements'] = 0
                user_data['total_achievements'] += 1
                
        except Exception as e:
            logging.error(f"Ошибка проверки достижения {ach_id}: {e}")
            continue
    
    return new_achievements, total_reward

async def process_user_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text.strip()
    admin = update.effective_user
    action = context.user_data.get('admin_action')
    
    logging.info(f"Админ {admin.username} ввел: '{user_input}' для действия '{action}'")
    
    # Удаляем @ из начала, если есть
    user_input = user_input.lstrip('@')
    
    # Пробуем разные способы поиска пользователя
    target_user_id = None
    target_user_data = None
    
    # 1. Проверяем, является ли ввод числовым ID
    if user_input.isdigit():
        target_user_id = int(user_input)
        if str(target_user_id) in user_data:
            target_user_data = user_data[str(target_user_id)]
    
    # 2. Если не нашли по ID, ищем по username
    if not target_user_data:
        for uid, u_data in user_data.items():
            username = u_data.get('username', '').lower()
            # Ищем полное совпадение username
            if username == user_input.lower() or f"@{username}" == user_input.lower():
                target_user_id = int(uid)
                target_user_data = u_data
                break
    
    # 3. Если все еще не нашли, проверяем частичное совпадение
    if not target_user_data:
        for uid, u_data in user_data.items():
            username = u_data.get('username', '').lower()
            if user_input.lower() in username or username in user_input.lower():
                target_user_id = int(uid)
                target_user_data = u_data
                logging.info(f"Найдено частичное совпадение: {username} для {user_input}")
                break
    
    if not target_user_data:
        await update.message.reply_text(
            f"❌ Пользователь '{user_input}' не найден.\n\n"
            f"Можете ввести:\n"
            f"• Цифровой ID (например: 7665179923)\n"
            f"• Username без @ (например: DanilKolbasenkory)\n"
            f"• Username с @ (например: @DanilKolbasenkory)"
        )
        return AWAITING_USER_ID
    
    target_username = target_user_data.get('username', str(target_user_id))
    
    # ==================== ЗАЩИТА ВЛАДЕЛЬЦА ====================
    # Список защищенных пользователей (владельцы)
    PROTECTED_USERS = [
        'scriptik_kormit',  # Ваш username
        # Добавьте сюда другие защищенные username
    ]
    
    # Также проверяем по ID владельца из ADMINS
    owner_usernames = [username for username, data in ADMINS.items() if data.get('level', 0) >= 3]
    
    # ДЕЛАЕМ ИСКЛЮЧЕНИЕ ДЛЯ ДОБАВЛЕНИЯ ДЕНЕГ!
    # Для ban/unban/warn/remove_money - ЗАПРЕЩАЕМ
    # Для add_money - РАЗРЕШАЕМ
    
    if action in ['ban', 'unban', 'warn', 'remove_money']:
        # Проверяем, является ли цель защищенным пользователем
        if target_username in PROTECTED_USERS or target_username in owner_usernames:
            await update.message.reply_text("⛔ Нельзя воздействовать на владельца бота!")
            return await show_admin_panel(update, context)
    # Для add_money - НЕ ПРОВЕРЯЕМ, разрешаем начислять
    # ==========================================================
    
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
                
        if str(target_user_id) in banned_users:
            await update.message.reply_text("⚠️ Этот пользователь уже забанен.")
        else:
            banned_users.add(str(target_user_id))
            await update.message.reply_text(f"✅ Пользователь @{target_username} (ID: {target_user_id}) забанен.")
            
            # Уведомление в группу администраторов
            notification_text = (
                f"🔨 <b>Администратор @{admin.username} забанил пользователя</b>\n"
                f"👤 Пользователь: @{target_username}\n"
                f"🆔 ID: <code>{target_user_id}</code>\n"
                f"🕒 Время: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
            )
            
            # Пробуем отправить уведомление
            try:
                if ADMIN_GROUP_ID:
                    await context.bot.send_message(
                        chat_id=ADMIN_GROUP_ID,
                        text=notification_text,
                        parse_mode='HTML'
                    )
            except Exception as e:
                logging.error(f"Не удалось отправить уведомление в группу: {e}")
            
            save_data()
        
        return await show_admin_panel(update, context)
    
    elif action == 'unban':
        if admin_level < 1:
            await update.message.reply_text("⛔ Недостаточно прав!")
            return await show_admin_panel(update, context)
            
        if str(target_user_id) not in banned_users:
            await update.message.reply_text("⚠️ Этот пользователь не забанен.")
        else:
            banned_users.remove(str(target_user_id))
            await update.message.reply_text(f"✅ Пользователь @{target_username} (ID: {target_user_id}) разбанен.")
            
            save_data()
    
    elif action == 'warn':
        if admin_level < 1:
            await update.message.reply_text("⛔ Недостаточно прав!")
            return await show_admin_panel(update, context)
            
        # Проверяем, не является ли цель владельцем (уже сделано выше для warn)
        warn_count = user_warns.get(target_user_id, 0) + 1
        user_warns[target_user_id] = warn_count
        
        await update.message.reply_text(
            f"⚠️ Пользователю @{target_username} выдано предупреждение\n"
            f"Всего предупреждений: {warn_count}/3"
        )
        
        if warn_count >= 3:
            # Проверяем еще раз перед авто-баном
            if target_username in PROTECTED_USERS or target_username in owner_usernames:
                await update.message.reply_text("⛔ Владелец не может быть забанен автоматически!")
                return await show_admin_panel(update, context)
            
            banned_users.add(str(target_user_id))
            await update.message.reply_text(
                f"🚨 Пользователь @{target_username} получил 3 предупреждения и был автоматически забанен!"
            )
            
            save_data()
    
    elif action in ('add_money', 'remove_money'):
        context.user_data['target_user'] = target_user_id
        context.user_data['target_username'] = target_username
        
        await update.message.reply_text(
            f"👤 Пользователь: @{target_username} (ID: {target_user_id})\n\n"
            "Введите сумму (для койнов добавьте 'c' в конце):\n"
            "Примеры:\n"
            "1000000 - 1 миллион денег\n"
            "50c - 50 койнов"
        )
        return AWAITING_AMOUNT
    
    return await show_admin_panel(update, context)

async def daily_box_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню ежедневного бокса"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    user = get_user_data(user_id)
    
    today = datetime.now().strftime('%Y-%m-%d')
    last_daily = user.get('last_daily_box', '')
    
    can_claim = (last_daily != today)
    
    text = (
        "📅 <b>ЕЖЕДНЕВНЫЙ БОКС</b>\n"
        "═══════════════════\n\n"
        "Каждый день вы можете получить бонус!\n\n"
        "🎁 <b>Возможные награды:</b>\n"
        f"• Деньги: 10к - 1кк ₽\n"
        f"• Койны: 1 - 20 🪙\n\n"
    )
    
    if can_claim:
        text += "✅ Доступно для получения!"
        keyboard = [[InlineKeyboardButton("🎁 ПОЛУЧИТЬ", callback_data="daily_box_claim")]]
    else:
        text += "❌ Уже получен сегодня.\nЗавтра будет новый!"
        keyboard = []
    
    keyboard.append([InlineKeyboardButton("🔙 НАЗАД", callback_data="box_back")])
    
    await query.edit_message_text(
        text=text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )
    
    return BOX_MENU

async def daily_box_claim(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение ежедневного бонуса"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    user = get_user_data(user_id)
    
    today = datetime.now().strftime('%Y-%m-%d')
    
    if user.get('last_daily_box') == today:
        await query.answer("❌ Вы уже получали сегодня!", show_alert=True)
        return await daily_box_menu(update, context)
    
    # Выбираем случайную награду
    money_choice = random.choice([100000, 500000, 1000000, 500000, 1000000])
    coins_choice = random.choice([1, 3, 5, 10, 20])
    
    # Начисляем
    user['balance'] += money_choice
    user['coins'] = user.get('coins', 0) + coins_choice
    user['last_daily_box'] = today
    
    save_data()
    
    text = (
        f"🎉 <b>БОНУС ПОЛУЧЕН!</b>\n"
        f"═══════════════════\n\n"
        f"💰 Деньги: +{money_choice:,} ₽\n"
        f"🪙 Койны: +{coins_choice}\n\n"
        f"💳 Новый баланс: {user['balance']:,} ₽\n"
        f"🎯 Всего койнов: {user.get('coins', 0)}\n\n"
        f"Завтра будет новый бонус!"
    )
    
    keyboard = [[InlineKeyboardButton("🔙 НАЗАД", callback_data="box_back")]]
    
    await query.edit_message_text(
        text=text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )
    
    return BOX_MENU

async def friend_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда для добавления в друзья"""
    user_id = str(update.effective_user.id)
    
    if not context.args:
        await update.message.reply_text(
            "📱 <b>СИСТЕМА ДРУЗЕЙ</b>\n"
            "═══════════════════\n\n"
            "📨 <b>Команды:</b>\n"
            "• /friend @username - отправить заявку\n"
            "• /friends - список друзей\n"
            "• /friend_requests - заявки в друзья\n"
            "• /friend_accept @username - принять заявку\n"
            "• /friend_decline @username - отклонить\n"
            "• /friend_remove @username - удалить из друзей",
            parse_mode='HTML'
        )
        return
    
    target_username = context.args[0].lstrip('@')
    
    # Ищем пользователя
    target_id = None
    target_name = None
    for uid, u_data in user_data.items():
        saved_username = u_data.get('username')
        # Проверяем, что saved_username не None
        if saved_username and saved_username.lower() == target_username.lower():
            target_id = uid
            target_name = saved_username
            break
    
    if not target_id:
        await update.message.reply_text("❌ Пользователь не найден!")
        return
    
    if target_id == user_id:
        await update.message.reply_text("❌ Нельзя добавить самого себя!")
        return
    
    # Проверяем, уже друзья
    if user_id in friends and target_id in friends.get(user_id, []):
        await update.message.reply_text("❌ Вы уже друзья!")
        return
    
    # Проверяем, есть ли уже заявка
    for req_id, req in friend_requests.items():
        if req['from'] == user_id and req['to'] == target_id:
            await update.message.reply_text("❌ Заявка уже отправлена!")
            return
    
    # Создаем заявку
    request_id = secrets.token_hex(8)
    from_name = user_data[user_id].get('username')
    if not from_name:
        from_name = f"ID: {user_id[-4:]}"
    
    friend_requests[request_id] = {
        'from': user_id,
        'from_name': from_name,
        'to': target_id,
        'to_name': target_name or f"ID: {target_id[-4:]}",
        'time': time.time()
    }
    
    await update.message.reply_text(
        f"✅ Заявка в друзья отправлена пользователю @{target_name or target_id}!"
    )
    
    # Уведомляем получателя
    try:
        await context.bot.send_message(
            chat_id=int(target_id),
            text=(
                f"📨 <b>НОВАЯ ЗАЯВКА В ДРУЗЬЯ!</b>\n\n"
                f"👤 От: @{from_name}\n\n"
                f"Команды:\n"
                f"✅ /friend_accept @{from_name} - принять\n"
                f"❌ /friend_decline @{from_name} - отклонить"
            ),
            parse_mode='HTML'
        )
    except:
        pass
    
    save_friends()

async def give_tokens(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выдать токены пользователю (только для владельца)"""
    user_id = str(update.effective_user.id)
    
    # Проверяем, что это владелец
    if user_id != TOKEN_OWNER_ID:
        await update.message.reply_text("❌ У вас нет прав для этой команды!")
        return
    
    if len(context.args) != 2:
        await update.message.reply_text(
            "❌ Использование: /token @username количество\n"
            "Пример: /token @user 100"
        )
        return
    
    target_username = context.args[0].lstrip('@')
    try:
        amount = int(context.args[1])
        if amount <= 0:
            await update.message.reply_text("❌ Количество должно быть положительным!")
            return
    except ValueError:
        await update.message.reply_text("❌ Укажите корректное число!")
        return
    
    # Ищем пользователя
    target_id = None
    for uid, u_data in user_data.items():
        saved_username = u_data.get('username')
        if saved_username and saved_username.lower() == target_username.lower():
            target_id = uid
            break
    
    if not target_id:
        await update.message.reply_text("❌ Пользователь не найден!")
        return
    
    # Выдаем токены
    add_tokens(target_id, amount)
    
    # Получаем имя пользователя
    target_name = user_data[target_id].get('username', f"ID: {target_id[-4:]}")
    
    await update.message.reply_text(
        f"✅ Пользователю @{target_name} выдано {amount} токенов!\n"
        f"💰 Текущий баланс: {get_token_balance(target_id)} токенов"
    )
    
    # Уведомляем пользователя
    try:
        await context.bot.send_message(
            chat_id=int(target_id),
            text=(
                f"🎁 <b>ВЫ ПОЛУЧИЛИ ТОКЕНЫ!</b>\n\n"
                f"💰 Количество: {amount} токенов\n"
                f"💳 Текущий баланс: {get_token_balance(target_id)} токенов\n\n"
                f"Используйте 🛒 МАГАЗИН → 💎 ДОНАТ МАГАЗИН для покупок!"
            ),
            parse_mode='HTML'
        )
    except:
        pass

async def friend_accept(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Принять заявку в друзья"""
    user_id = str(update.effective_user.id)
    
    if not context.args:
        await update.message.reply_text("❌ Укажите @username")
        return
    
    target_username = context.args[0].lstrip('@')
    
    # Ищем заявку
    request_id = None
    request_data = None
    for rid, req in friend_requests.items():
        if req['to'] == user_id and req['from_name'].lower() == target_username.lower():
            request_id = rid
            request_data = req
            break
    
    if not request_data:
        await update.message.reply_text("❌ Заявка не найдена!")
        return
    
    # Добавляем в друзья
    if user_id not in friends:
        friends[user_id] = []
    if request_data['from'] not in friends:
        friends[request_data['from']] = []
    
    friends[user_id].append(request_data['from'])
    friends[request_data['from']].append(user_id)
    
    # Удаляем заявку
    del friend_requests[request_id]
    
    await update.message.reply_text(
        f"✅ Вы приняли заявку в друзья от @{request_data['from_name']}!"
    )
    
    # Уведомляем отправителя
    try:
        await context.bot.send_message(
            chat_id=int(request_data['from']),
            text=f"✅ @{user_data[user_id].get('username')} принял вашу заявку в друзья!"
        )
    except:
        pass
    
    save_friends()

async def friend_decline(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отклонить заявку в друзья"""
    user_id = str(update.effective_user.id)
    
    if not context.args:
        await update.message.reply_text("❌ Укажите @username")
        return
    
    target_username = context.args[0].lstrip('@')
    
    # Ищем заявку
    request_id = None
    for rid, req in friend_requests.items():
        if req['to'] == user_id and req['from_name'].lower() == target_username.lower():
            request_id = rid
            break
    
    if not request_id:
        await update.message.reply_text("❌ Заявка не найдена!")
        return
    
    # Удаляем заявку
    del friend_requests[request_id]
    
    await update.message.reply_text(
        f"❌ Вы отклонили заявку в друзья от @{target_username}!"
    )
    
    save_friends()

async def friend_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Список друзей"""
    user_id = str(update.effective_user.id)
    
    user_friends = friends.get(user_id, [])
    
    if not user_friends:
        await update.message.reply_text("📱 У вас пока нет друзей.")
        return
    
    text = "👥 <b>ВАШИ ДРУЗЬЯ</b>\n═══════════════\n\n"
    
    for friend_id in user_friends:
        friend_data = user_data.get(friend_id, {})
        friend_name = friend_data.get('username', friend_id)
        last_active = friend_data.get('last_active', 0)
        
        if time.time() - last_active < 86400:
            status = "🟢 Online"
        else:
            status = "⚪ Offline"
        
        text += f"• @{friend_name} - {status}\n"
    
    await update.message.reply_text(text, parse_mode='HTML')

async def friend_requests_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Список заявок в друзья"""
    user_id = str(update.effective_user.id)
    
    incoming = []
    for req in friend_requests.values():
        if req['to'] == user_id:
            incoming.append(req)
    
    if not incoming:
        await update.message.reply_text("📨 У вас нет входящих заявок.")
        return
    
    text = "📨 <b>ВХОДЯЩИЕ ЗАЯВКИ</b>\n════════════════\n\n"
    
    for req in incoming:
        text += f"• @{req['from_name']}\n"
        text += f"  ├ /friend_accept @{req['from_name']} - принять\n"
        text += f"  └ /friend_decline @{req['from_name']} - отклонить\n\n"
    
    await update.message.reply_text(text, parse_mode='HTML')

def save_friends():
    """Сохраняет данные о друзьях"""
    try:
        data = {
            'friends': friends,
            'friend_requests': friend_requests
        }
        with open('friends.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        logging.error(f"Ошибка сохранения друзей: {e}")

def load_friends():
    """Загружает данные о друзьях"""
    global friends, friend_requests
    try:
        if os.path.exists('friends.json'):
            with open('friends.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
                friends = data.get('friends', {})
                friend_requests = data.get('friend_requests', {})
    except Exception as e:
        logging.error(f"Ошибка загрузки друзей: {e}")
        friends = {}
        friend_requests = {}

async def check_business_income(context: ContextTypes.DEFAULT_TYPE):
    """Проверяет и начисляет доход с бизнесов каждую минуту"""
    current_time = datetime.now()
    users_updated = 0
    logging.info("🔄 Проверка дохода с бизнесов...")
    
    for user_id, user in list(user_data.items()):
        if user_id in banned_users:
            continue
        
        # Получаем количество обычных бизнесов
        business_count = user.get('business_count', 0)
        
        # ВАЖНО: Проверяем VIP статус
        is_vip_user = check_vip(user_id)
        
        # ВАЖНО: Проверяем наличие VIP бизнеса
        has_vip_business = user.get('vip_business', False)
        
        # Если нет вообще никаких бизнесов - пропускаем
        if business_count == 0 and not has_vip_business:
            continue
        
        # Получаем время последнего дохода
        last_income_str = user.get('last_business_income')
        
        if not last_income_str:
            user['last_business_income'] = current_time.isoformat()
            continue
        
        try:
            last_income = datetime.fromisoformat(last_income_str)
            
            # Сколько секунд прошло с последнего начисления
            seconds_passed = (current_time - last_income).total_seconds()
            
            # Начисляем если прошло больше 10 секунд
            if seconds_passed < 10:
                continue
            
            # --- РАСЧЕТ ДОХОДА ЗА ЧАС ---
            total_income_per_hour = 0
            
            # 1. Считаем доход с обычных бизнесов
            for i in range(1, business_count + 1):
                biz = BUSINESS_TYPES.get(i)
                if biz:
                    total_income_per_hour += biz['income']
            
            # 2. ВАЖНО: Добавляем доход с VIP бизнеса (30,000,000 ₽/ч)
            if has_vip_business and is_vip_user:
                total_income_per_hour += 30_000_000
                logging.info(f"👑 VIP бизнес для {user_id}: +30,000,000 ₽/ч")
            
            # 3. Применяем VIP бонус 15% ко ВСЕМУ доходу
            if is_vip_user:
                total_income_per_hour = int(total_income_per_hour * 1.15)
            
            # Сколько часов прошло (с дробной частью)
            hours_passed = seconds_passed / 3600
            
            # Начисляем пропорционально прошедшему времени
            amount = int(total_income_per_hour * hours_passed)
            
            if amount > 0:
                user['balance'] += amount
                user['last_business_income'] = current_time.isoformat()
                
                users_updated += 1
                logging.info(f"💰 Начислено {amount:,} ₽ пользователю {user_id} за {hours_passed:.2f} ч (доход/ч: {total_income_per_hour:,} ₽)")
                
        except Exception as e:
            logging.error(f"Ошибка для {user_id}: {e}")
            user['last_business_income'] = current_time.isoformat()
    
    if users_updated > 0:
        save_data()
        logging.info(f"✅ Доход начислен {users_updated} пользователям")
    else:
        logging.info("ℹ️ Нет пользователей для начисления")

async def start_business_scheduler(application: Application):
    """Запускает планировщик для проверки доходов каждую минуту"""
    job_queue = application.job_queue
    if job_queue:
        # Проверяем каждую минуту (60 секунд)
        job_queue.run_repeating(check_business_income, interval=60, first=10)
        logging.info("✅ Планировщик бизнесов запущен (проверка каждую минуту)")

async def box_menu_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Точка входа в меню боксов"""
    user_id = update.effective_user.id
    if str(user_id) in banned_users:
        await update.message.reply_text("⛔ Вы заблокированы и не можете использовать бота.")
        return ConversationHandler.END
        
    user = get_user_data(user_id)
    user['last_active'] = time.time()
    
    keyboard = [
        [InlineKeyboardButton("🎁 Обычный бокс", callback_data="normal_box_menu")],
        [InlineKeyboardButton("💎 Премиум бокс", callback_data="premium_box_menu")],
    ]
    
    if user['inventory']['boxes'] > 0:
        keyboard.append([InlineKeyboardButton(f"🎉 Открыть бокс ({user['inventory']['boxes']} шт.)", callback_data="box_open")])
    
    keyboard.append([InlineKeyboardButton("📦 Мой инвентарь", callback_data="box_inventory")])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="box_back")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"🎁 Меню боксов:\n\n"
        f"🪙 Ваши койны: {user.get('coins', 0)}\n"
        f"💰 Ваш баланс: {user['balance']:,} ₽\n"
        f"🎁 Доступно боксов: {user['inventory'].get('boxes', 0)}",
        reply_markup=reply_markup
    )
    
    return "BOX_MENU_STATE"

async def premium_box_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню премиум бокса"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    user = get_user_data(user_id)
    
    # Проверяем, покупал ли уже сегодня
    last_premium = user.get('last_premium_box', '')
    today = datetime.now().strftime('%Y-%m-%d')
    
    can_buy = (last_premium != today)
    
    # Формируем текст с шансами
    text = (
        "💎 <b>ПРЕМИУМ БОКС</b>\n"
        "═══════════════════\n\n"
        f"💰 Цена: <b>1,000,000,000 ₽</b>\n"
        f"🪙 Ваши койны: {user.get('coins', 0)}\n"
        f"💰 Ваш баланс: {user['balance']:,} ₽\n\n"
        
        "🎁 <b>ВОЗМОЖНЫЕ НАГРАДЫ:</b>\n"
        "═══════════════════\n"
        "💎 <b>Золотой цветок</b> (10%)\n"
        "   • Меняет фото в профиле\n"
        "   • Уникальный эффект\n\n"
        
        "💰 <b>500M - 1B ₽</b> (20%)\n"
        "   • От 500 млн до 1 млрд\n\n"
        
        "💰 <b>100M - 500M ₽</b> (30%)\n"
        "   • От 100 млн до 500 млн\n\n"
        
        "🪙 <b>100 койнов</b> (15%)\n"
        "   • Для покупки обычных боксов\n\n"
        
        "🪙 <b>50 койнов</b> (15%)\n"
        "   • Для покупки обычных боксов\n\n"
        
        "🎁 <b>Сюрприз</b> (10%)\n"
        "   • Случайный бонус\n"
    )
    
    if can_buy:
        text += "\n✅ Доступно для покупки!"
        keyboard = [
            [InlineKeyboardButton("💎 КУПИТЬ ПРЕМИУМ БОКС (1,000,000,000 ₽)", callback_data="premium_box_buy")],
            [InlineKeyboardButton("🔙 НАЗАД", callback_data="box_back")]
        ]
    else:
        text += "\n❌ Уже куплен сегодня.\nЗавтра будет доступен снова!"
        keyboard = [[InlineKeyboardButton("🔙 НАЗАД", callback_data="box_back")]]
    
    await query.edit_message_text(
        text=text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )
    
    return PREMIUM_BOX_MENU

async def buy_premium_box(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Покупка премиум бокса с одним предметом (цветок) - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    user = get_user_data(user_id)
    
    # Проверяем баланс
    if user['balance'] < PREMIUM_BOX_CONFIG['price']:
        await query.answer(f"❌ Недостаточно средств! Нужно {PREMIUM_BOX_CONFIG['price']:,} ₽", show_alert=True)
        return await premium_box_menu(update, context)
    
    # Снимаем деньги
    user['balance'] -= PREMIUM_BOX_CONFIG['price']
    
    # Выбираем награду (правильное распределение шансов)
    total_chance = 100  # Всего 100%
    rand = random.uniform(0, total_chance)
    
    selected_reward = None
    cumulative = 0
    
    for reward in PREMIUM_BOX_CONFIG['rewards']:
        cumulative += reward['chance']
        if rand <= cumulative:
            selected_reward = reward
            break
    
    if not selected_reward:
        # На всякий случай, если что-то пошло не так
        selected_reward = PREMIUM_BOX_CONFIG['rewards'][1]  # Первая валюта
    
    # Выдаем награду
    if selected_reward['type'] == 'money':
        amount = selected_reward['amount']
        user['balance'] += amount
        
        is_rare = selected_reward.get('is_rare', False)
        rare_emoji = "💎" if is_rare else "💰"
        
        # Анимация открытия
        await query.edit_message_text(
            f"📦 Открываем премиум бокс...",
            reply_markup=None
        )
        await asyncio.sleep(1.5)
        
        # Результат
        result_text = (
            f"🎉 Вы открыли премиум бокс!\n\n"
            f"{rare_emoji} Выпало: {selected_reward['description']}\n"
            f"💵 Сумма: {amount:,} ₽\n"
            f"💳 Ваш баланс: {user['balance']:,} ₽"
        )
        
        if is_rare:
            result_text += "\n\n🎊 ПОЗДРАВЛЯЕМ! РЕДКАЯ НАГРАДА!"
        
        await query.edit_message_text(result_text)
    
    elif selected_reward['type'] == 'item':
        # ВЫПАЛ ЦВЕТОК! (2% шанс)
        item_id = selected_reward['item_id']
        item_name = selected_reward['name']
        item_emoji = selected_reward['emoji']
        
        # Анимация открытия
        await query.edit_message_text(
            f"📦 Открываем премиум бокс...",
            reply_markup=None
        )
        await asyncio.sleep(1.5)
        await query.edit_message_text(
            f"✨ Что-то блестит...",
            reply_markup=None
        )
        await asyncio.sleep(1)
        
        # Добавляем цветок в инвентарь
        if 'premium_items' not in user:
            user['premium_items'] = []
        
        # Проверяем, есть ли уже такой цветок
        has_flower = any(item.get('id') == 'golden_flower' for item in user['premium_items'])
        
        if not has_flower:
            user['premium_items'].append({
                'id': item_id,
                'name': item_name,
                'emoji': item_emoji,
                'obtained_at': datetime.now().isoformat(),
                'description': selected_reward['description']
            })
            
            # АВТОМАТИЧЕСКАЯ АКТИВАЦИЯ ЦВЕТКА!
            photo_path = PREMIUM_BOX_CONFIG['item_photos'].get(item_id)
            if photo_path:
                user['active_premium_item'] = {
                    'id': item_id,
                    'name': item_name,
                    'photo_path': photo_path,
                    'activated_at': datetime.now().isoformat(),
                    'is_flower': True
                }
            
            flower_message = "🌸 ВАМ ВЫПАЛ ЗОЛОТОЙ ЦВЕТОК!\n\n"
            flower_message += "🎉 ПОЗДРАВЛЯЕМ! АВТОМАТИЧЕСКИ АКТИВИРОВАН:\n"
            flower_message += "• Редкий золотой цветок удачи\n"
            flower_message += "• Новое фото профиля\n"
            flower_message += "• Статус обладателя цветка\n"
            flower_message += "• Уникальный предмет (только 2% шанс!)"
            
            # Показываем фото цветка
            if photo_path and os.path.exists(photo_path):
                try:
                    with open(photo_path, 'rb') as photo_file:
                        await query.message.reply_photo(
                            photo=photo_file,
                            caption=flower_message
                        )
                except Exception as e:
                    logging.error(f"Ошибка отправки фото цветка: {e}")
                    await query.edit_message_text(flower_message)
            else:
                await query.edit_message_text(flower_message)
        else:
            # Если цветок уже есть - даем бонусные деньги
            bonus = 500_000_000  # 500кк за повторный цветок
            user['balance'] += bonus
            
            await query.edit_message_text(
                f"🌸 У вас уже есть золотой цветок!\n\n"
                f"💎 За повторный цветок вы получаете бонус:\n"
                f"💰 +{bonus:,} ₽\n"
                f"💳 Ваш баланс: {user['balance']:,} ₽"
            )
    
    save_data()
    
    # Кнопки после получения
    keyboard = [
        [InlineKeyboardButton("💎 Ещё премиум бокс", callback_data="premium_box_buy")],
        [InlineKeyboardButton("📊 Профиль", callback_data="show_profile")],
        [InlineKeyboardButton("🔙 Назад", callback_data="premium_box_back")]
    ]
    
    if hasattr(update, 'callback_query'):
        await update.callback_query.message.reply_text(
            "✅ Награда получена!",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    # Возвращаем в меню через 5 секунд
    await asyncio.sleep(3)
    return await premium_box_menu(update, context)

async def show_premium_items(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать мои премиум вещи"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    user = get_user_data(user_id)
    
    premium_items = user.get('premium_items', [])
    active_item = user.get('active_premium_item')
    
    text = "📦 Ваши премиум вещи:\n\n"
    
    if not premium_items:
        text += "Пока нет премиум вещей 😢\n"
        text += f"💎 Купите премиум бокс за {PREMIUM_BOX_CONFIG['price']:,} ₽ чтобы получить их!"
    else:
        text += f"Всего вещей: {len(premium_items)}\n\n"
        
        # Группируем одинаковые вещи
        item_counts = {}
        for item in premium_items:
            item_name = f"{item.get('emoji', '🎁')} {item.get('name', 'Предмет')}"
            item_counts[item_name] = item_counts.get(item_name, 0) + 1
        
        for item_name, count in item_counts.items():
            text += f"{item_name} ×{count}\n"
    
    if active_item:
        text += f"\n🎯 Активная вещь: {active_item.get('name', 'Неизвестно')}\n"
        text += f"📅 Активирована: {datetime.fromisoformat(active_item['activated_at']).strftime('%d.%m.%Y')}"
    
    keyboard = [
        [InlineKeyboardButton("💎 Ещё премиум бокс", callback_data="premium_box_buy")],
        [InlineKeyboardButton("🔙 Назад", callback_data="premium_box_back")]
    ]
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    return "PREMIUM_BOX_MENU" 
    
PREMIUM_BOX_CONFIG = {
    "name": "💎 Премиум бокс",
    "price": 1_000_000_000,  # 1ккк
    "rewards": [
        # ТОЛЬКО ОДИН ПРЕДМЕТ - ЦВЕТОК (2% шанс)
        {
            "type": "item", 
            "name": "🌸 Золотой цветок", 
            "emoji": "🌸", 
            "chance": 7, 
            "item_id": "golden_flower",
            "description": "Редкий золотой цветок удачи"
        },
        
        # ВАЛЮТА (остальные 98%)
        {
            "type": "money", 
            "amount": 10_000_000, 
            "emoji": "💰", 
            "chance": 35, 
            "description": "10кк"
        },  # 40%
        {
            "type": "money", 
            "amount": 250_000_000, 
            "emoji": "💰", 
            "chance": 30, 
            "description": "250кк"
        },  # 30%
        {
            "type": "money", 
            "amount": 300_300_000, 
            "emoji": "💰", 
            "chance": 20, 
            "description": "300кк"
        },  # 20%
        {
            "type": "money", 
            "amount": 1_500_000_000, 
            "emoji": "💎", 
            "chance": 3, 
            "description": "1.5ккк (редкий)",
            "is_rare": True
        },  # 3% - как указано
    ],
    "item_photos": {
        "golden_flower": "/storage/emulated/0/фотобот/цветок.jpg",  # Фото цветка
    }
}    

async def process_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    amount_str = update.message.text
    user_id = context.user_data['target_user']
    action = context.user_data.get('admin_action')
    admin = update.effective_user
    
    admin_data = ADMINS.get(admin.username, {})
    today = datetime.now().strftime('%Y-%m-%d')
    
    # Инициализация счетчиков дневных лимитов
    if 'daily_usage' not in admin_data:
        admin_data['daily_usage'] = {'date': today, 'money': 0, 'coins': 0}
    elif admin_data['daily_usage']['date'] != today:
        admin_data['daily_usage'] = {'date': today, 'money': 0, 'coins': 0}
    
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
    
    # Проверка лимитов для администраторов (кроме владельца citic_at22_828)
    if admin.username != 'citic_at22_828':
        if is_coins:
            if (admin_data['daily_usage']['coins'] + amount) > admin_data.get('daily_limit', {}).get('coins', 0):
                remaining = admin_data['daily_limit']['coins'] - admin_data['daily_usage']['coins']
                await update.message.reply_text(
                    f"❌ Превышен дневной лимит койнов! Осталось сегодня: {remaining}"
                )
                return AWAITING_AMOUNT
        else:
            if (admin_data['daily_usage']['money'] + amount) > admin_data.get('daily_limit', {}).get('money', 0):
                remaining = admin_data['daily_limit']['money'] - admin_data['daily_usage']['money']
                await update.message.reply_text(
                    f"❌ Превышен дневной лимит денег! Осталось сегодня: {remaining:,}"
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
            admin_data['daily_usage']['coins'] += amount
        else:
            user['balance'] += amount
            operation = "начислено денег"
            operation_emoji = "➕💰"
            currency = "₽"
            admin_data['daily_usage']['money'] += amount
            
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
        f"Новый баланс: {user['balance']:,} ₽ | Койны: {user.get('coins', 0)}\n"
        f"Лимиты сегодня: Деньги: {admin_data['daily_usage']['money']:,}/{admin_data.get('daily_limit', {}).get('money', '∞')} | "
        f"Койны: {admin_data['daily_usage']['coins']}/{admin_data.get('daily_limit', {}).get('coins', '∞')}"
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
async def invest_company(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Инвестировать в компанию"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    company_id = data.replace("invest_", "")
    company = INVESTMENT_COMPANIES.get(company_id)
    
    if not company:
        await query.answer("❌ Компания не найдена!", show_alert=True)
        return await investment_menu(update, context)
    
    context.user_data['invest_company'] = company_id
    context.user_data['invest_company_name'] = company['name']
    
    user_id = str(query.from_user.id)
    user = get_user_data(user_id)
    
    text = (
        f"{company['color']} <b>{company['name']}</b> {company['emoji']}\n"
        f"═══════════════════════\n\n"
        f"📋 {company['description']}\n\n"
        f"💰 Минимальная сумма: {company['min_invest']:,} ₽\n"
        f"📈 Средняя доходность: +{int((company['base_return']-1)*100)}%\n"
        f"⚡ Волатильность: {int(company['volatility']*100)}%\n\n"
        f"⏳ Срок инвестиции: 7 дней\n\n"
        f"💰 Ваш баланс: {user['balance']:,} ₽\n\n"
        f"Введите сумму для инвестирования:"
    )
    
    await query.edit_message_text(
        text=text,
        parse_mode='HTML'
    )
    
    return INVEST_AMOUNT

async def my_investments(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать мои инвестиции"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    investments = user_investments.get(user_id, {})
    
    if not investments:
        text = "📊 У вас пока нет активных инвестиций."
    else:
        text = "📊 <b>ВАШИ ИНВЕСТИЦИИ</b>\n═══════════════════\n\n"
        current_time = time.time()
        
        for comp_id, inv in investments.items():
            company = INVESTMENT_COMPANIES.get(comp_id, {})
            if not company:
                continue
            
            # Время до завершения
            end_time = inv['start_time'] + (inv['days'] * 86400)
            time_left = end_time - current_time
            
            if time_left <= 0:
                # Инвестиция завершена, можно получить прибыль
                status = "✅ ГОТОВО К ПОЛУЧЕНИЮ"
                # Рассчитываем прибыль
                min_return = company['base_return'] - company['volatility']
                max_return = company['base_return'] + company['volatility']
                profit_mult = random.uniform(min_return, max_return)
                profit = int(inv['amount'] * profit_mult)
                
                text += (
                    f"{company['color']} {company['name']} {company['emoji']}\n"
                    f"├ 💰 Вложено: {inv['amount']:,} ₽\n"
                    f"├ 📈 Прибыль: {profit - inv['amount']:,} ₽\n"
                    f"└ {status}\n\n"
                )
            else:
                days = int(time_left // 86400)
                hours = int((time_left % 86400) // 3600)
                status = f"⏳ Осталось: {days}д {hours}ч"
                
                text += (
                    f"{company['color']} {company['name']} {company['emoji']}\n"
                    f"├ 💰 Вложено: {inv['amount']:,} ₽\n"
                    f"└ {status}\n\n"
                )
    
    keyboard = [[InlineKeyboardButton("🔙 НАЗАД", callback_data="invest_back")]]
    
    await query.edit_message_text(
        text=text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )
    
    return INVEST_MENU
    
async def process_invest_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка суммы инвестиций"""
    user_id = str(update.message.from_user.id)
    user = get_user_data(user_id)
    
    try:
        amount = parse_bet_amount(update.message.text)
        company_id = context.user_data.get('invest_company')
        company = INVESTMENT_COMPANIES.get(company_id)
        
        if not amount or amount < company['min_invest']:
            await update.message.reply_text(f"❌ Минимальная сумма: {company['min_invest']:,} ₽")
            return INVEST_AMOUNT
        
        if amount > user['balance']:
            await update.message.reply_text(f"❌ Недостаточно средств! Баланс: {user['balance']:,} ₽")
            return INVEST_AMOUNT
        
        # Списываем деньги
        user['balance'] -= amount
        
        # Сохраняем инвестицию
        if user_id not in user_investments:
            user_investments[user_id] = {}
        
        user_investments[user_id][company_id] = {
            'amount': amount,
            'start_time': time.time(),
            'days': 7,
            'company': company['name']
        }
        
        save_investments()
        save_data()
        
        # Формируем текст с возможной прибылью
        min_return = company['base_return'] - company['volatility']
        max_return = company['base_return'] + company['volatility']
        min_profit = int(amount * min_return) - amount
        max_profit = int(amount * max_return) - amount
        
        text = (
            f"✅ <b>ИНВЕСТИЦИЯ СОЗДАНА!</b>\n"
            f"═══════════════════════\n\n"
            f"{company['color']} {company['name']} {company['emoji']}\n"
            f"💰 Сумма: {amount:,} ₽\n"
            f"📅 Срок: 7 дней\n\n"
            f"📊 <b>Прогнозируемая прибыль:</b>\n"
            f"├ Минимум: +{min_profit:,} ₽\n"
            f"└ Максимум: +{max_profit:,} ₽\n\n"
            f"⏳ Через 7 дней вы сможете получить прибыль!"
        )
        
        await update.message.reply_text(text, parse_mode='HTML')
        
        # Очищаем контекст
        context.user_data.pop('invest_company', None)
        context.user_data.pop('invest_company_name', None)
        
        # Возвращаемся в меню инвестиций
        # Для этого нужно создать callback_query
        new_update = Update(update.update_id)
        new_update.callback_query = update.message  # Это не совсем правильно
        
        # Лучше просто отправить сообщение с кнопкой возврата
        keyboard = [[InlineKeyboardButton("🔙 В ИНВЕСТИЦИИ", callback_data="invest_back")]]
        await update.message.reply_text(
            "Выберите действие:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        return ConversationHandler.END
        
    except Exception as e:
        await update.message.reply_text("❌ Ошибка! Введите корректную сумму.")
        return INVEST_AMOUNT
        
# ==================== УМНАЯ ПРОВЕРКА ДОСТИЖЕНИЙ ====================
# Просто добавьте ЭТУ функцию в код и всё будет работать автоматически

async def auto_check_achievements(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Автоматически проверяет достижения при любом действии"""
    
    # Получаем пользователя
    user_id = update.effective_user.id
    user = get_user_data(user_id)
    
    if 'achievements' not in user:
        user['achievements'] = {}
    
    new_achs = []
    total_reward = 0
    
    # Проверяем все достижения
    for ach_id, ach in ACHIEVEMENTS.items():
        if ach_id in user['achievements']:
            continue
        
        try:
            if ach['condition'](user):
                user['achievements'][ach_id] = {
                    'unlocked_at': time.time(),
                    'reward_claimed': True
                }
                user['balance'] += ach['reward']
                total_reward += ach['reward']
                new_achs.append(ach['name'])
        except:
            pass
    
    # Отправляем уведомление если есть новые
    if new_achs:
        text = "🎉 <b>НОВЫЕ ДОСТИЖЕНИЯ!</b>\n\n"
        for ach in new_achs:
            text += f"• {ach}\n"
        text += f"\n💰 Получено: {total_reward:,} ₽"
        
        if update.message:
            await update.message.reply_text(text, parse_mode='HTML')
        elif update.callback_query:
            await update.callback_query.message.reply_text(text, parse_mode='HTML')
    
    save_data()

# ==================== ДОБАВЬТЕ ЭТОТ FILTER В MAIN ====================
# Просто добавьте эти строки в main() после всех обработчиков:


async def update_usernames_job(context: ContextTypes.DEFAULT_TYPE):
    """Проверяет и обновляет username у всех пользователей"""
    logging.info("🔄 Запуск проверки username...")
    updated = 0
    
    for user_id_str, user_data_item in list(user_data.items()):
        try:
            # Пытаемся получить актуальную информацию о пользователе
            chat = await context.bot.get_chat(int(user_id_str))
            
            # Получаем текущий username (может быть None)
            current_username = chat.username
            
            # Получаем сохраненный username
            saved_username = user_data_item.get('username')
            
            # Если username изменился (или был None, а теперь есть)
            if current_username != saved_username:
                old_display = saved_username or 'None'
                new_display = current_username or 'None'
                
                user_data_item['username'] = current_username
                updated += 1
                logging.info(f"🔄 Обновлен username для {user_id_str}: {old_display} -> {new_display}")
                
        except Exception as e:
            # Если не получилось получить чат (пользователь заблокировал бота и т.д.)
            # Просто пропускаем
            pass
    
    if updated > 0:
        save_data()
        logging.info(f"✅ Обновлено username у {updated} пользователей")
    else:
        logging.info("✅ Изменений username не найдено")        
                        
async def claim_investment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получить прибыль от завершенной инвестиции"""
    user_id = str(update.effective_user.id)
    user = get_user_data(user_id)
    
    investments = user_investments.get(user_id, {})
    claimed = 0
    
    for comp_id, inv in list(investments.items()):
        if inv.get('completed') and not inv.get('claimed'):
            user['balance'] += inv['profit']
            inv['claimed'] = True
            claimed += 1
    
    if claimed > 0:
        save_investments()
        save_data()
        await update.message.reply_text(f"✅ Получена прибыль от {claimed} инвестиций!")
    else:
        await update.message.reply_text("❌ Нет доступной прибыли для получения.")
     
async def crash_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Краш-игра в группах"""
    # Проверяем, что это группа
    if update.message.chat.type not in ('group', 'supergroup'):
        await update.message.reply_text("❌ Эта игра доступна только в группах!")
        return
    
    user_id = update.message.from_user.id
    if user_id in banned_users:
        return
    
    # Получаем текст сообщения
    text = update.message.text.lower()
    parts = text.split()
    
    if len(parts) != 2:
        await update.message.reply_text(
            "💥 <b>КРАШ-ИГРА</b>\n\n"
            "Использование:\n"
            "• /crash [сумма] - начать игру\n"
            "• краш [сумма] - тоже самое\n\n"
            "Пример: /crash 100к\n\n"
            "Правила:\n"
            "• Множитель растет каждый шаг\n"
            "• Забери деньги ДО краша\n"
            "• Если краш - теряешь всё!\n"
            f"💰 Мин. ставка: {CRASH_CONFIG['min_bet']:,} ₽\n"
            f"💰 Макс. ставка: {CRASH_CONFIG['max_bet']:,} ₽",
            parse_mode='HTML'
        )
        return
    
    # Парсим сумму
    bet_amount = parse_bet_amount(parts[1])
    
    if not bet_amount or bet_amount <= 0:
        await update.message.reply_text("❌ Неверная сумма!")
        return
    
    if bet_amount < CRASH_CONFIG['min_bet']:
        await update.message.reply_text(f"❌ Минимальная ставка: {CRASH_CONFIG['min_bet']:,} ₽")
        return
    
    if bet_amount > CRASH_CONFIG['max_bet']:
        await update.message.reply_text(f"❌ Максимальная ставка: {CRASH_CONFIG['max_bet']:,} ₽")
        return
    
    # Получаем данные пользователя
    user = get_user_data(user_id)
    username = user.get('username') or update.message.from_user.username or update.message.from_user.full_name
    
    if bet_amount > user['balance']:
        await update.message.reply_text(f"❌ Недостаточно средств! Баланс: {user['balance']:,} ₽")
        return
    
    # Списываем ставку
    user['balance'] -= bet_amount
    save_data()
    
    # Создаем игру
    game_id = str(user_id)
    crash_games[game_id] = {
        'user_id': user_id,
        'username': username,
        'bet': bet_amount,
        'multiplier': 1.0,
        'active': True,
        'cashed_out': False,
        'message_id': None,
        'chat_id': update.message.chat_id
    }
    
    # Отправляем стартовое сообщение
    message = await update.message.reply_text(
        f"💥 <b>КРАШ-ИГРА</b>\n\n"
        f"👤 Игрок: @{username}\n"
        f"💰 Ставка: {bet_amount:,} ₽\n"
        f"📈 Множитель: <b>1.00x</b>\n\n"
        f"🔄 Игра началась! Множитель растет...\n"
        f"👇 Нажмите кнопку, чтобы забрать деньги",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("💰 ЗАБРАТЬ", callback_data=f"crash_cashout_{game_id}")
        ]]),
        parse_mode='HTML'
    )
    
    crash_games[game_id]['message_id'] = message.message_id
    
    # Запускаем игровой цикл
    asyncio.create_task(crash_game_loop(context, game_id))

async def crash_game_loop(context: ContextTypes.DEFAULT_TYPE, game_id: str, chat_id: int):
    """Игровой цикл краш-игры"""
    try:
        # Ждем 1 секунду, чтобы игрок успел нажать
        await asyncio.sleep(1)
        
        # Проверяем, не забрал ли уже игрок деньги
        if 'crash_games' not in context.bot_data or game_id not in context.bot_data['crash_games']:
            return
        
        game = context.bot_data['crash_games'][game_id]
        
        # Если игрок уже забрал деньги - выходим
        if game.get('cashed_out'):
            # Удаляем игру
            if game_id in context.bot_data['crash_games']:
                del context.bot_data['crash_games'][game_id]
            return
        
        multiplier = 1.0
        step_count = 0
        
        while True:
            # Проверяем существование игры
            if 'crash_games' not in context.bot_data or game_id not in context.bot_data['crash_games']:
                return
            
            game = context.bot_data['crash_games'][game_id]
            
            # Если игрок забрал деньги - выходим
            if game.get('cashed_out'):
                if game_id in context.bot_data['crash_games']:
                    del context.bot_data['crash_games'][game_id]
                return
            
            # Если игра не активна - выходим
            if not game.get('active', True):
                if game_id in context.bot_data['crash_games']:
                    del context.bot_data['crash_games'][game_id]
                return
            
            # Ждем
            await asyncio.sleep(0.3)
            
            # Увеличиваем множитель
            multiplier += 0.03
            game['multiplier'] = multiplier
            step_count += 1
            
            # Шанс краша
            crash_chance = 0.02 + (step_count * 0.005)
            if random.random() < crash_chance or multiplier >= 5.0:
                # КРАШ!
                game['active'] = False
                
                try:
                    await context.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=game['message_id'],
                        text=(
                            f"💥 <b>КРАШ!</b>\n\n"
                            f"👤 Игрок: @{game['username']}\n"
                            f"💰 Ставка: {game['bet']:,} ₽\n"
                            f"📈 Множитель: <b>{multiplier:.2f}x</b>\n\n"
                            f"😢 К сожалению, игра оборвалась...\n"
                            f"💰 Вы проиграли {game['bet']:,} ₽"
                        ),
                        parse_mode='HTML'
                    )
                except:
                    pass
                
                # Удаляем игру
                if game_id in context.bot_data['crash_games']:
                    del context.bot_data['crash_games'][game_id]
                return
            
            # Обновляем сообщение
            try:
                potential_win = int(game['bet'] * multiplier)
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=game['message_id'],
                    text=(
                        f"💥 <b>КРАШ-ИГРА</b>\n\n"
                        f"👤 Игрок: @{game['username']}\n"
                        f"💰 Ставка: {game['bet']:,} ₽\n"
                        f"📈 Множитель: <b>{multiplier:.2f}x</b>\n"
                        f"💵 Возможный выигрыш: {potential_win:,} ₽\n\n"
                        f"🔄 Множитель растет...\n"
                        f"👇 Забери деньги, пока не поздно!"
                    ),
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton(f"💰 ЗАБРАТЬ {potential_win:,} ₽", callback_data=f"crash_cashout_{game_id}")
                    ]]),
                    parse_mode='HTML'
                )
            except Exception as e:
                logging.error(f"Ошибка обновления краш-игры: {e}")
                # Если не можем обновить, но игрок еще не забрал - продолжаем
                continue
                
    except Exception as e:
        logging.error(f"Критическая ошибка в краш-цикле: {e}")
        if 'crash_games' in context.bot_data and game_id in context.bot_data['crash_games']:
            del context.bot_data['crash_games'][game_id]

async def crash_cashout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Забрать деньги до краша"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    game_id = data.replace("crash_cashout_", "")
    
    if 'crash_games' not in context.bot_data or game_id not in context.bot_data['crash_games']:
        await query.edit_message_text("❌ Игра уже завершена!")
        return
    
    game = context.bot_data['crash_games'][game_id]
    user_id = query.from_user.id
    
    if user_id != game['user_id']:
        await query.answer("❌ Это не ваша игра!", show_alert=True)
        return
    
    if game.get('cashed_out'):
        await query.edit_message_text("❌ Вы уже забрали деньги!")
        return
    
    # Если игра еще не началась (цикл не запущен)
    if time.time() - game.get('start_time', 0) < 1:
        # Игра только началась, разрешаем забрать с минимальным множителем
        pass
    
    # Забираем деньги
    game['cashed_out'] = True
    game['active'] = False
    
    user = get_user_data(user_id)
    win_amount = int(game['bet'] * game['multiplier'])
    user['balance'] += win_amount
    save_data()
    
    try:
        await query.edit_message_text(
            f"🎉 <b>ВЫ ЗАБРАЛИ ДЕНЬГИ!</b>\n\n"
            f"👤 Игрок: @{game['username']}\n"
            f"💰 Ставка: {game['bet']:,} ₽\n"
            f"📈 Множитель: <b>{game['multiplier']:.2f}x</b>\n"
            f"💵 ВЫИГРЫШ: {win_amount:,} ₽\n"
            f"📈 Чистая прибыль: {win_amount - game['bet']:,} ₽",
            parse_mode='HTML'
        )
    except:
        pass
    
    # Удаляем игру
    if game_id in context.bot_data['crash_games']:
        del context.bot_data['crash_games'][game_id]
        

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда /start"""
    user_id = str(update.effective_user.id)
    username = update.effective_user.username
    
    print(f"🚀 START: Пользователь {user_id} (@{username}) запускает бота")
    
    # ========== ПРОВЕРКА БАНА ==========
    if user_id in banned_users:
        await update.message.reply_text("⛔ Вы заблокированы и не можете использовать бота.")
        return
    
    # ========== ПОЛУЧАЕМ/СОЗДАЕМ ДАННЫЕ ПОЛЬЗОВАТЕЛЯ ==========
    user = get_user_data(user_id)
    
    # Обновляем username если он есть
    if username:
        user['username'] = username
    elif not user.get('username'):
        # Если нет username в Telegram, используем имя
        user['username'] = update.effective_user.full_name.replace(' ', '_')
    
    user['last_active'] = time.time()
    
    # ... остальной код start ...
    
    # ========== ОБРАБОТКА АРГУМЕНТОВ ==========
    if context.args and len(context.args) > 0:
        arg = context.args[0]
        print(f"🔵 START аргумент: {arg}")
        
        # Если это чек
        if arg.startswith('check_'):
            check_id = arg[6:]
            print(f"🔵 Активация чека: {check_id}")
            
            if check_id in checks:
                check = checks[check_id]
                current_time = time.time()
                
                if current_time > check['expires_at']:
                    del checks[check_id]
                    save_data()
                    await update.message.reply_text(
                        "❌ Время действия чека истекло!\n"
                        "Чеки действительны только 30 минут."
                    )
                elif check['used_by']:
                    await update.message.reply_text(
                        f"❌ Этот чек уже был использован!"
                    )
                else:
                    user = get_user_data(user_id)
                    user['balance'] += check['amount']
                    
                    # Обновляем данные чека
                    check['used_by'] = user_id
                    check['used_at'] = current_time
                    
                    await update.message.reply_text(
                        f"🎉 ЧЕК АКТИВИРОВАН!\n\n"
                        f"💰 Вы получили: {check['amount']:,} ₽\n"
                        f"💳 Ваш баланс: {user['balance']:,} ₽\n\n"
                        f"✅ Награда зачислена!"
                    )
                    
                    # Сохраняем изменения
                    save_data()
                    
                    # Уведомляем создателя чека
                    try:
                        creator_id = check.get('created_by')
                        if creator_id:
                            await context.bot.send_message(
                                chat_id=int(creator_id),
                                text=f"🎉 Чек {check_id} был активирован!\n"
                                     f"👤 Пользователь: @{user.get('username', user_id)}\n"
                                     f"💰 Сумма: {check['amount']:,} ₽"
                            )
                    except Exception as e:
                        logging.error(f"Ошибка отправки уведомления создателю: {e}")
                    
                    return
    
    # ========== ОСНОВНОЙ СТАРТ ==========
    user = get_user_data(user_id)
    user['username'] = username
    user['last_active'] = time.time()
    
    if 'referral_code' not in user:
        user['referral_code'] = secrets.token_hex(4)
    
    # Рассчитываем доход от бизнесов
    business_count = user.get('business_count', 0)
    business_income = sum(BUSINESS_TYPES.get(i, {}).get('income', 0) for i in range(1, business_count + 1))
    
    # ========== ОПРЕДЕЛЯЕМ ФОТО ПОЛЬЗОВАТЕЛЯ ==========
    photo_info = get_user_photo_info(user_id)
    photo_path = photo_info["path"]
    photo_caption = photo_info["caption"]
    
    # Получаем имя бота для реферальной ссылки
    bot_username = (await context.bot.get_me()).username
    
    welcome_text = (
        f"👋 Привет, {username}!\n\n"
        f"💰 Твой баланс: {user['balance']:,} ₽\n"
        f"🪙 Твои койны: {user.get('coins', 0)}\n"
        f"🏢 Бизнесы: {business_count} (Доход: {business_income:,} ₽/час)\n"
        f"📨 Рефералов: {len(user.get('referrals', []))}\n\n"
        f"🔗 Твоя реферальная ссылка:\n"
        f"https://t.me/{bot_username}?start=ref_{user['referral_code']}"
    )
    
    # Добавляем информацию о предметах, если есть
    if photo_caption:
        welcome_text += f"\n\n{photo_caption}"
    
    # Проверяем дополнительные статусы
    extra_statuses = []
    
    # Определяем наличие цветка
    has_flower = False
    flower_activated = False
    if 'premium_items' in user:
        for item in user['premium_items']:
            if item.get('id') == 'golden_flower':
                has_flower = True
                if user.get('active_premium_item', {}).get('id') == 'golden_flower':
                    flower_activated = True
                break
    
    # Проверяем, есть ли цветок в инвентаре, но не активен
    if has_flower and not flower_activated:
        extra_statuses.append("🌸 Золотой цветок в инвентаре")
    
    # Проверяем, есть ли огнетушитель в инвентаре, но не активен
    user_item_data = user_items.get(user_id, {})
    if 'fire_extinguisher' in user_item_data.get('items_owned', []) and not photo_caption.startswith("🎯"):
        extra_statuses.append("🚒 Огнетушитель в инвентаре")
    
    if extra_statuses:
        welcome_text += f"\n\n📦 Дополнительно: {' | '.join(extra_statuses)}"
    
    # Отправляем фото
    try:
        if os.path.exists(photo_path):
            with open(photo_path, 'rb') as photo_file:
                await context.bot.send_photo(
                    chat_id=update.message.chat_id,
                    photo=photo_file,
                    caption=welcome_text,
                    reply_markup=get_main_keyboard(),
                    parse_mode='HTML'
                )
        else:
            # Если файла нет, используем стандартное фото
            if os.path.exists(PHOTO_NORMAL_PATH):
                with open(PHOTO_NORMAL_PATH, 'rb') as photo_file:
                    await context.bot.send_photo(
                        chat_id=update.message.chat_id,
                        photo=photo_file,
                        caption=welcome_text + "\n\n⚠️ Фото предмета временно недоступно",
                        reply_markup=get_main_keyboard(),
                        parse_mode='HTML'
                    )
            else:
                # Если и стандартного нет - только текст
                await update.message.reply_text(
                    welcome_text,
                    reply_markup=get_main_keyboard(),
                    parse_mode='HTML'
                )
    except Exception as e:
        print(f"❌ Ошибка отправки фото в start: {e}")
        # Если фото не отправилось, отправляем только текст
        await update.message.reply_text(
            welcome_text,
            reply_markup=get_main_keyboard(),
            parse_mode='HTML'
        )
    
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

# Хранилище для подтверждений переводов
transfer_confirmations = {}  # {code: {'from': user_id, 'to': user_id, 'amount': сумма, 'time': timestamp}}

async def pay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда перевода денег"""
    user_id = str(update.message.from_user.id)
    
    if user_id in banned_users:
        await update.message.reply_text("⛔ Вы заблокированы и не можете использовать бота.")
        return
    
    user = get_user_data(user_id)
    settings = get_user_settings(user_id)
    
    if len(context.args) != 2:
        await update.message.reply_text(
            "❌ Использование: /pay @username сумма\n"
            "Пример: /pay @friend 100000"
        )
        return
    
    recipient_username = context.args[0].lstrip('@')
    try:
        amount = int(context.args[1])
        if amount <= 0:
            await update.message.reply_text("❌ Сумма должна быть положительной!")
            return
    except ValueError:
        await update.message.reply_text("❌ Пожалуйста, укажите корректную сумму!")
        return
    
    if amount > user['balance']:
        await update.message.reply_text("❌ Недостаточно средств на балансе!")
        return
    
    # Ищем получателя
    recipient_id = None
    recipient_data = None
    
    # Сначала ищем по username
    for uid, u_data in user_data.items():
        saved_username = u_data.get('username')
        # Проверяем, что saved_username не None и совпадает
        if saved_username and saved_username.lower() == recipient_username.lower():
            recipient_id = uid
            recipient_data = u_data
            break
    
    # Если не нашли, пробуем найти по ID
    if not recipient_id and recipient_username.isdigit():
        if recipient_username in user_data:
            recipient_id = recipient_username
            recipient_data = user_data[recipient_id]
    
    if not recipient_id:
        await update.message.reply_text("❌ Пользователь не найден!")
        return
    
    if recipient_id == user_id:
        await update.message.reply_text("❌ Нельзя переводить самому себе!")
        return
    
    # Если включено подтверждение
    if settings['confirm_transfer']:
        # Генерируем код подтверждения
        confirm_code = secrets.token_hex(3).upper()
        transfer_confirmations[confirm_code] = {
            'from': user_id,
            'to': recipient_id,
            'amount': amount,
            'time': time.time()
        }
        
        keyboard = [[InlineKeyboardButton(f"✅ ПОДТВЕРДИТЬ ПЕРЕВОД {amount:,} ₽", callback_data=f"confirm_transfer_{confirm_code}")]]
        
        await update.message.reply_text(
            f"🔄 <b>ПОДТВЕРДИТЕ ПЕРЕВОД</b>\n\n"
            f"👤 Кому: @{recipient_username}\n"
            f"💰 Сумма: {amount:,} ₽\n\n"
            f"Нажмите кнопку ниже для подтверждения\n"
            f"⏳ Код действителен 30 секунд",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
        return
    
    # Если подтверждение не требуется - сразу переводим
    user['balance'] -= amount
    recipient_data['balance'] += amount
    save_data()
    
    # Получаем имя отправителя для красивого вывода
    sender_name = user.get('username')
    if not sender_name:
        sender_name = f"ID: {user_id[-4:]}"
    else:
        sender_name = f"@{sender_name}"
    
    # Получаем имя получателя
    recipient_name = recipient_data.get('username')
    if not recipient_name:
        recipient_name = f"ID: {recipient_id[-4:]}"
    else:
        recipient_name = f"@{recipient_name}"
    
    await update.message.reply_text(
        f"✅ Вы перевели {amount:,} ₽ пользователю {recipient_name}\n"
        f"💰 Ваш баланс: {user['balance']:,} ₽"
    )
    
    # Уведомляем получателя
    try:
        await context.bot.send_message(
            chat_id=int(recipient_id),
            text=(
                f"💸 <b>ПЕРЕВОД ПОЛУЧЕН</b>\n\n"
                f"👤 От: {sender_name}\n"
                f"💰 Сумма: {amount:,} ₽\n"
                f"💳 Новый баланс: {recipient_data['balance']:,} ₽"
            ),
            parse_mode='HTML'
        )
    except Exception as e:
        logging.error(f"Не удалось уведомить получателя: {e}")

async def confirm_transfer_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подтверждение перевода"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    confirm_code = data.replace("confirm_transfer_", "")
    
    # Проверяем, есть ли такое подтверждение
    if confirm_code not in transfer_confirmations:
        await query.edit_message_text("❌ Код подтверждения недействителен или истек!")
        return
    
    confirm_data = transfer_confirmations[confirm_code]
    
    # Проверяем время (30 секунд)
    if time.time() - confirm_data['time'] > 30:
        del transfer_confirmations[confirm_code]
        await query.edit_message_text("❌ Время подтверждения истекло!")
        return
    
    # Проверяем, что подтверждает тот же пользователь
    if str(query.from_user.id) != confirm_data['from']:
        await query.answer("❌ Это не ваш перевод!", show_alert=True)
        return
    
    # Выполняем перевод
    from_user = get_user_data(confirm_data['from'])
    to_user = get_user_data(confirm_data['to'])
    
    from_user['balance'] -= confirm_data['amount']
    to_user['balance'] += confirm_data['amount']
    
    # Удаляем подтверждение
    del transfer_confirmations[confirm_code]
    save_data()
    
    await query.edit_message_text(
        f"✅ <b>ПЕРЕВОД ПОДТВЕРЖДЕН!</b>\n\n"
        f"💰 Сумма: {confirm_data['amount']:,} ₽\n"
        f"💳 Новый баланс: {from_user['balance']:,} ₽",
        parse_mode='HTML'
    )
    
    # Уведомляем получателя
    try:
        to_username = to_user.get('username', 'Пользователь')
        await context.bot.send_message(
            chat_id=int(confirm_data['to']),
            text=f"💸 Вам перевели {confirm_data['amount']:,} ₽ от @{from_user.get('username')}\n"
                 f"💰 Ваш баланс: {to_user['balance']:,} ₽"
        )
    except:
        pass

async def group_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Бан пользователя в группе (только для @scriptik_kormit)"""
    # Проверяем, что команда в группе
    if update.message.chat.type not in ('group', 'supergroup'):
        return
    
    # Проверяем, что это нужная группа
    if str(update.message.chat.id) != "-1003505311472":
        return
    
    # Проверяем, что команду дал @scriptik_kormit
    if update.message.from_user.username != "scriptik_kormit":
        await update.message.reply_text("❌ У вас нет прав для этой команды!")
        return
    
    if len(context.args) < 2:
        await update.message.reply_text(
            "❌ Использование: /ban @username [дни/навсегда]\n"
            "Пример: /ban @user 7\n"
            "Пример: /ban @user навсегда"
        )
        return
    
    target_username = context.args[0].lstrip('@')
    ban_duration = context.args[1].lower()
    
    # Ищем пользователя
    target_id = None
    target_data = None
    
    # Сначала ищем по username
    for uid, u_data in user_data.items():
        saved_username = u_data.get('username')
        if saved_username and saved_username.lower() == target_username.lower():
            target_id = uid
            target_data = u_data
            break
    
    # Если не нашли, пробуем найти по ID
    if not target_id and target_username.isdigit():
        if target_username in user_data:
            target_id = target_username
            target_data = user_data[target_id]
    
    if not target_id:
        await update.message.reply_text("❌ Пользователь не найден в базе бота!")
        return
    
    # Определяем длительность бана
    ban_time = None
    duration_text = ""
    
    if ban_duration == "навсегда":
        ban_time = float('inf')
        duration_text = "навсегда"
    else:
        try:
            days = int(ban_duration)
            if days <= 0:
                raise ValueError
            ban_time = time.time() + (days * 86400)
            duration_text = f"{days} дн."
        except ValueError:
            await update.message.reply_text("❌ Неверный формат длительности! Используйте число или 'навсегда'")
            return
    
    # Баним пользователя
    banned_users.add(target_id)
    
    # Сохраняем информацию о бане
    if 'ban_info' not in target_data:
        target_data['ban_info'] = {}
    
    target_data['ban_info'] = {
        'banned_by': update.message.from_user.username,
        'banned_at': time.time(),
        'banned_until': ban_time,
        'reason': f"Бан в группе от @scriptik_kormit"
    }
    
    save_data()
    
    # Получаем имя пользователя для ответа
    target_name = target_data.get('username')
    if not target_name:
        target_name = f"ID: {target_id[-4:]}"
    else:
        target_name = f"@{target_name}"
    
    await update.message.reply_text(
        f"✅ Пользователь {target_name} забанен {duration_text}!"
    )
    
    # Уведомляем пользователя
    try:
        await context.bot.send_message(
            chat_id=int(target_id),
            text=(
                f"⛔ <b>ВЫ ЗАБАНЕНЫ</b>\n\n"
                f"👤 Администратор: @scriptik_kormit\n"
                f"⏱️ Длительность: {duration_text}\n"
                f"📍 Группа: {update.message.chat.title}\n\n"
                f"💬 Причина: бан в группе"
            ),
            parse_mode='HTML'
        )
    except Exception as e:
        logging.error(f"Не удалось уведомить пользователя о бане: {e}")

async def group_unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Разбан пользователя в группе (только для @scriptik_kormit)"""
    # Проверяем, что команда в группе
    if update.message.chat.type not in ('group', 'supergroup'):
        return
    
    # Проверяем, что это нужная группа
    if str(update.message.chat.id) != "-1003505311472":
        return
    
    # Проверяем, что команду дал @scriptik_kormit
    if update.message.from_user.username != "scriptik_kormit":
        await update.message.reply_text("❌ У вас нет прав для этой команды!")
        return
    
    if len(context.args) != 1:
        await update.message.reply_text(
            "❌ Использование: /unban @username\n"
            "Пример: /unban @user"
        )
        return
    
    target_username = context.args[0].lstrip('@')
    
    # Ищем пользователя
    target_id = None
    target_data = None
    
    # Сначала ищем по username
    for uid, u_data in user_data.items():
        saved_username = u_data.get('username')
        if saved_username and saved_username.lower() == target_username.lower():
            target_id = uid
            target_data = u_data
            break
    
    # Если не нашли, пробуем найти по ID
    if not target_id and target_username.isdigit():
        if target_username in user_data:
            target_id = target_username
            target_data = user_data[target_id]
    
    if not target_id:
        await update.message.reply_text("❌ Пользователь не найден в базе бота!")
        return
    
    # Проверяем, забанен ли пользователь
    if target_id not in banned_users:
        await update.message.reply_text("❌ Этот пользователь не забанен!")
        return
    
    # Разбаниваем
    banned_users.remove(target_id)
    
    # Очищаем информацию о бане
    if 'ban_info' in target_data:
        del target_data['ban_info']
    
    save_data()
    
    # Получаем имя пользователя для ответа
    target_name = target_data.get('username')
    if not target_name:
        target_name = f"ID: {target_id[-4:]}"
    else:
        target_name = f"@{target_name}"
    
    await update.message.reply_text(
        f"✅ Пользователь {target_name} разбанен!"
    )
    
    # Уведомляем пользователя
    try:
        await context.bot.send_message(
            chat_id=int(target_id),
            text=(
                f"✅ <b>ВЫ РАЗБАНЕНЫ</b>\n\n"
                f"👤 Администратор: @scriptik_kormit\n"
                f"📍 Группа: {update.message.chat.title}\n\n"
                f"Теперь вы снова можете использовать бота!"
            ),
            parse_mode='HTML'
        )
    except Exception as e:
        logging.error(f"Не удалось уведомить пользователя о разбане: {e}")

async def confirm_pay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подтвердить перевод"""
    user_id = str(update.message.from_user.id)
    user = get_user_data(user_id)
    
    # Проверяем есть ли ожидающий перевод
    if 'pending_payment' not in context.user_data:
        await update.message.reply_text("❌ Нет ожидающих переводов!")
        return
    
    pending = context.user_data['pending_payment']
    recipient_id = pending['recipient_id']
    recipient_username = pending['recipient_username']
    amount = pending['amount']
    
    # Проверяем баланс еще раз
    if amount > user['balance']:
        await update.message.reply_text(f"❌ Недостаточно средств! У вас {user['balance']:,} ₽")
        del context.user_data['pending_payment']
        return
    
    # Получаем данные получателя
    recipient_data = get_user_data(recipient_id)
    
    # Выполняем перевод
    user['balance'] -= amount
    recipient_data['balance'] += amount
    
    # Сохраняем
    save_data()
    
    sender_username = user.get('username', user_id)
    
    await update.message.reply_text(
        f"✅ Перевод выполнен!\n\n"
        f"👤 Отправитель: @{sender_username}\n"
        f"👤 Получатель: @{recipient_username}\n"
        f"💰 Сумма: {amount:,} ₽\n"
        f"💳 Ваш баланс: {user['balance']:,} ₽"
    )
    
    # Уведомляем получателя
    try:
        await context.bot.send_message(
            chat_id=int(recipient_id),
            text=f"💸 Вам перевели {amount:,} ₽ от @{sender_username}\n"
                 f"💰 Ваш баланс: {recipient_data['balance']:,} ₽"
        )
    except Exception as e:
        logging.error(f"Не удалось уведомить получателя: {e}")
    
    # Очищаем данные
    del context.user_data['pending_payment']
    
async def create_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Создание чека (только для разрешенных пользователей)"""
    user_id = update.effective_user.id
    
    # Проверяем, имеет ли пользователь право создавать чеки
    if user_id not in CHECK_ALLOWED_USERS:
        await update.message.reply_text("❌ У вас нет прав на создание чеков!")
        return
    
    # Проверяем формат команды
    if len(context.args) != 2:
        await update.message.reply_text(
            "❌ Неверный формат. Используйте:\n"
            "/check [сумма] [количество активаций]\n\n"
            "Примеры:\n"
            "/check 1000000 1  - чек на 1 млн, 1 активация\n"
            "/check 500000 10   - чек на 500к, 10 активаций\n"
            "/check 10000000 100 - чек на 10 млн, 100 активаций"
        )
        return
    
    try:
        # Парсим сумму
        amount_str = context.args[0]
        amount = parse_bet_amount(amount_str)
        if not amount or amount < CHECK_CONFIG['min_amount'] or amount > CHECK_CONFIG['max_amount']:
            await update.message.reply_text(
                f"❌ Неверная сумма!\n"
                f"Минимум: {CHECK_CONFIG['min_amount']:,} ₽\n"
                f"Максимум: {CHECK_CONFIG['max_amount']:,} ₽"
            )
            return
        
        # Парсим количество активаций
        max_activations = int(context.args[1])
        if max_activations < 1 or max_activations > CHECK_CONFIG['max_activations']:
            await update.message.reply_text(
                f"❌ Неверное количество активаций!\n"
                f"Минимум: 1\n"
                f"Максимум: {CHECK_CONFIG['max_activations']}"
            )
            return
        
        # Проверяем баланс пользователя
        user = get_user_data(user_id)
        total_cost = amount * max_activations
        if user['balance'] < total_cost:
            await update.message.reply_text(
                f"❌ Недостаточно средств!\n"
                f"Нужно: {total_cost:,} ₽ ({amount:,} ₽ × {max_activations})\n"
                f"У вас: {user['balance']:,} ₽"
            )
            return
        
        # Создаем чек
        check_id = secrets.token_hex(8)
        current_time = time.time()
        
        checks[check_id] = {
            'id': check_id,
            'creator_id': str(user_id),
            'creator_name': user.get('username', str(user_id)),
            'amount': amount,
            'max_activations': max_activations,
            'used_activations': 0,
            'created_at': current_time,
            'expires_at': current_time + CHECK_CONFIG['expire_time'],
            'activated_by': [],  # Список пользователей, кто активировал
            'active': True
        }
        
        # Списываем деньги
        user['balance'] -= total_cost
        
        # Сохраняем
        save_data()
        save_checks()
        
        # Формируем сообщение для канала
        channel_text = (
            f"🎫 <b>НОВЫЙ ЧЕК!</b>\n\n"
            f"💰 Сумма: {amount:,} ₽\n"
            f"🎯 Активаций: {max_activations}\n"
            f"👤 Создатель: @{user.get('username', 'Аноним')}\n"
            f"🕒 Срок: 24 часа\n\n"
            f"Нажмите кнопку ниже, чтобы активировать чек!"
        )
        
        # Создаем клавиатуру с кнопкой активации
        keyboard = [[InlineKeyboardButton(
            f"🎫 АКТИВИРОВАТЬ ЧЕК ({amount:,} ₽)", 
            callback_data=f"activate_check_{check_id}"
        )]]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Отправляем в канал
        try:
            await context.bot.send_message(
                chat_id=CHECK_CHANNEL_ID,
                text=channel_text,
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
            
            await update.message.reply_text(
                f"✅ Чек успешно создан!\n\n"
                f"💰 Сумма: {amount:,} ₽\n"
                f"🎯 Активаций: {max_activations}\n"
                f"💳 Списано: {total_cost:,} ₽\n"
                f"📊 Осталось активаций: {max_activations}\n\n"
                f"Чек отправлен в канал!"
            )
            
        except Exception as e:
            logging.error(f"Ошибка отправки в канал: {e}")
            await update.message.reply_text(
                f"❌ Ошибка отправки в канал!\n"
                f"Проверьте, добавлен ли бот в канал и имеет ли права администратора."
            )
    
    except ValueError:
        await update.message.reply_text("❌ Ошибка в формате числа!")
    except Exception as e:
        logging.error(f"Ошибка создания чека: {e}")
        await update.message.reply_text("❌ Произошла ошибка при создании чека")
       
async def activate_check_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик активации чека"""
    query = update.callback_query
    await query.answer()
    
    if not query.data.startswith("activate_check_"):
        return
    
    check_id = query.data.replace("activate_check_", "")
    user_id = str(query.from_user.id)
    
    # Проверяем существование чека
    if check_id not in checks:
        await query.answer("❌ Чек не найден!", show_alert=True)
        return
    
    check = checks[check_id]
    
    # Проверяем, активен ли чек
    if not check.get('active', True):
        await query.answer("❌ Этот чек уже неактивен!", show_alert=True)
        return
    
    # Проверяем срок действия
    current_time = time.time()
    if current_time > check['expires_at']:
        check['active'] = False
        save_checks()
        await query.answer("❌ Срок действия чека истек!", show_alert=True)
        
        # Обновляем сообщение в канале
        try:
            await query.edit_message_text(
                text=query.message.text + "\n\n❌ <b>ЧЕК ИСТЕК</b>",
                parse_mode='HTML'
            )
        except:
            pass
        return
    
    # Проверяем, не исчерпаны ли активации
    if check['used_activations'] >= check['max_activations']:
        check['active'] = False
        save_checks()
        await query.answer("❌ Все активации чека использованы!", show_alert=True)
        
        # Обновляем сообщение в канале
        try:
            await query.edit_message_text(
                text=query.message.text + "\n\n❌ <b>ВСЕ АКТИВАЦИИ ИСПОЛЬЗОВАНЫ</b>",
                parse_mode='HTML'
            )
        except:
            pass
        return
    
    # Проверяем, не активировал ли пользователь уже этот чек
    if user_id in check['activated_by']:
        await query.answer("❌ Вы уже активировали этот чек!", show_alert=True)
        return
    
    # Получаем данные пользователя
    user = get_user_data(user_id)
    
    # Начисляем деньги
    user['balance'] += check['amount']
    
    # Обновляем статистику чека
    check['used_activations'] += 1
    check['activated_by'].append(user_id)
    
    # Если все активации использованы, деактивируем чек
    if check['used_activations'] >= check['max_activations']:
        check['active'] = False
    
    # Сохраняем
    save_data()
    save_checks()
    
    # Отправляем уведомление создателю
    try:
        creator_id = int(check['creator_id'])
        await context.bot.send_message(
            chat_id=creator_id,
            text=f"🎫 Чек был активирован!\n\n"
                 f"👤 Пользователь: @{user.get('username', user_id)}\n"
                 f"💰 Сумма: {check['amount']:,} ₽\n"
                 f"📊 Осталось активаций: {check['max_activations'] - check['used_activations']}"
        )
    except Exception as e:
        logging.error(f"Ошибка уведомления создателя: {e}")
    
    # Поздравляем пользователя
    await query.answer(f"✅ Вы получили {check['amount']:,} ₽!", show_alert=True)
    
    # Обновляем сообщение в канале
    remaining = check['max_activations'] - check['used_activations']
    status_text = "✅ ЧЕК АКТИВЕН" if check['active'] else "❌ ЧЕК ЗАВЕРШЕН"
    
    try:
        new_text = (
            f"🎫 <b>ЧЕК</b>\n\n"
            f"💰 Сумма: {check['amount']:,} ₽\n"
            f"🎯 Активаций: {check['used_activations']}/{check['max_activations']}\n"
            f"👤 Создатель: @{check['creator_name']}\n"
            f"📊 Статус: {status_text}\n\n"
            f"Последний активировавший: @{user.get('username', user_id)}"
        )
        
        # Если чек еще активен, оставляем кнопку
        if check['active'] and remaining > 0:
            keyboard = [[InlineKeyboardButton(
                f"🎫 АКТИВИРОВАТЬ ЧЕК ({check['amount']:,} ₽)", 
                callback_data=f"activate_check_{check_id}"
            )]]
            await query.edit_message_text(
                text=new_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='HTML'
            )
        else:
            # Если чек неактивен, убираем кнопку
            await query.edit_message_text(
                text=new_text,
                parse_mode='HTML'
            )
    except Exception as e:
        logging.error(f"Ошибка обновления сообщения в канале: {e}")
        
async def check_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Просмотр статистики чеков (только для создателя)"""
    user_id = update.effective_user.id
    
    # Проверяем права
    if user_id not in CHECK_ALLOWED_USERS:
        await update.message.reply_text("❌ У вас нет прав!")
        return
    
    creator_id = str(user_id)
    
    # Собираем чеки создателя
    creator_checks = []
    for check_id, check in checks.items():
        if check['creator_id'] == creator_id:
            creator_checks.append((check_id, check))
    
    if not creator_checks:
        await update.message.reply_text("📊 У вас пока нет созданных чеков.")
        return
    
    # Сортируем по дате создания (новые сверху)
    creator_checks.sort(key=lambda x: x[1]['created_at'], reverse=True)
    
    text = "📊 <b>СТАТИСТИКА ЧЕКОВ</b>\n\n"
    
    total_created = len(creator_checks)
    total_activations = sum(check['used_activations'] for _, check in creator_checks)
    total_spent = sum(check['amount'] * check['used_activations'] for _, check in creator_checks)
    
    text += f"📊 Всего создано: {total_created}\n"
    text += f"🎯 Всего активаций: {total_activations}\n"
    text += f"💰 Всего выплачено: {total_spent:,} ₽\n\n"
    
    text += "📋 <b>Последние 10 чеков:</b>\n\n"
    
    for i, (check_id, check) in enumerate(creator_checks[:10], 1):
        status = "✅ Активен" if check['active'] else "❌ Завершен"
        expires = datetime.fromtimestamp(check['expires_at']).strftime('%d.%m.%Y %H:%M')
        
        text += (
            f"{i}. ID: <code>{check_id}</code>\n"
            f"   💰 {check['amount']:,} ₽\n"
            f"   🎯 {check['used_activations']}/{check['max_activations']}\n"
            f"   📊 {status}\n"
            f"   🕒 Истекает: {expires}\n\n"
        )
    
    await update.message.reply_text(text, parse_mode='HTML')
    
async def cancel_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена чека (только для создателя)"""
    user_id = update.effective_user.id
    
    # Проверяем права
    if user_id not in CHECK_ALLOWED_USERS:
        await update.message.reply_text("❌ У вас нет прав!")
        return
    
    if len(context.args) != 1:
        await update.message.reply_text("❌ Используйте: /cancel_check [ID чека]")
        return
    
    check_id = context.args[0]
    
    if check_id not in checks:
        await update.message.reply_text("❌ Чек не найден!")
        return
    
    check = checks[check_id]
    
    if str(check['creator_id']) != str(user_id):
        await update.message.reply_text("❌ Это не ваш чек!")
        return
    
    if not check['active']:
        await update.message.reply_text("❌ Чек уже неактивен!")
        return
    
    # Рассчитываем возврат средств
    remaining_activations = check['max_activations'] - check['used_activations']
    refund_amount = check['amount'] * remaining_activations
    
    # Возвращаем деньги создателю
    creator = get_user_data(user_id)
    creator['balance'] += refund_amount
    
    # Деактивируем чек
    check['active'] = False
    
    save_data()
    save_checks()
    
    await update.message.reply_text(
        f"✅ Чек отменен!\n\n"
        f"💰 Возвращено: {refund_amount:,} ₽\n"
        f"🎯 Неиспользованных активаций: {remaining_activations}"
    )                                                
        
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

# ==================== КОМАНДЫ КАЗИНО (НОВАЯ ВЕРСИЯ) ====================
async def process_bet_amount_with_donate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ставки со всеми типами"""
    user_id = update.message.from_user.id
    if user_id in banned_users:
        await update.message.reply_text("⛔ Вы заблокированы и не можете использовать бота.")
        return ConversationHandler.END
    
    user = get_user_data(user_id)
    user['last_active'] = time.time()
    
    if not user.get('username'):
        await update.message.reply_text(
            "❌ У вас не установлен никнейм!\n"
            "Напишите боту в ЛС: /set_nick [ваш ник]"
        )
        return ConversationHandler.END
    
    bet_amount_str = update.message.text.lower()
    bet_type = context.user_data.get('bet_type')
    
    # Проверка на половину
    is_half = False
    if bet_amount_str in ['половина', 'пол']:
        is_half = True
        bet_amount = user['balance'] // 2
        if bet_amount <= 0:
            await update.message.reply_text("❌ У вас нет денег для ставки!")
            return BET_AMOUNT
        half_text = f" (50% от {user['balance']:,} ₽)"
    else:
        # Проверка на весь баланс
        if bet_amount_str in ['все', 'алл', 'вб', 'весь', 'весь баланс', 'all', 'вабанк']:
            bet_amount = user['balance']
            if bet_amount <= 0:
                await update.message.reply_text("❌ У вас нет денег для ставки!")
                return BET_AMOUNT
            half_text = ""
        else:
            bet_amount = parse_bet_amount(bet_amount_str)
            if not bet_amount or bet_amount <= 0:
                await update.message.reply_text("❌ Неверная сумма ставки!")
                return BET_AMOUNT
            half_text = ""
    
    if bet_amount > user['balance']:
        await update.message.reply_text("❌ Недостаточно средств на балансе!")
        return BET_AMOUNT
    
    username = user['username']
    old_balance = user['balance']
    
    # Списываем ставку
    user['balance'] -= bet_amount
    
    # Генерируем число
    win_number = random.randint(0, 36)
    
    # Определяем цвета и ряды
    red_numbers = {1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36}
    black_numbers = {2,4,6,8,10,11,13,15,17,20,22,24,26,28,29,31,33,35}
    
    # Ряды
    row1_numbers = {1,4,7,10,13,16,19,22,25,28,31,34}
    row2_numbers = {2,5,8,11,14,17,20,23,26,29,32,35}
    row3_numbers = {3,6,9,12,15,18,21,24,27,30,33,36}
    
    # Дюжины
    dozen1_numbers = set(range(1, 13))
    dozen2_numbers = set(range(13, 25))
    dozen3_numbers = set(range(25, 37))
    
    is_red = win_number in red_numbers
    is_black = win_number in black_numbers
    is_even = win_number % 2 == 0 and win_number != 0
    is_odd = win_number % 2 == 1
    is_zero = win_number == 0
    is_row1 = win_number in row1_numbers
    is_row2 = win_number in row2_numbers
    is_row3 = win_number in row3_numbers
    is_dozen1 = win_number in dozen1_numbers
    is_dozen2 = win_number in dozen2_numbers
    is_dozen3 = win_number in dozen3_numbers
    is_small = 1 <= win_number <= 18
    is_big = 19 <= win_number <= 36
    
    # Определяем цвет для вывода
    if is_zero:
        color = "⚪ (зеро)"
    elif is_red:
        color = "🔴 (красное)"
    else:
        color = "⚫ (черное)"
    
    # Дополнительная информация
    extra_info = []
    if is_row1:
        extra_info.append("1-й ряд")
    elif is_row2:
        extra_info.append("2-й ряд")
    elif is_row3:
        extra_info.append("3-й ряд")
    
    if is_dozen1:
        extra_info.append("1-12")
    elif is_dozen2:
        extra_info.append("13-24")
    elif is_dozen3:
        extra_info.append("25-36")
    
    extra_text = f" ({', '.join(extra_info)})" if extra_info else ""
    
    win = False
    multiplier = 1
    
    # Проверяем выигрыш по типу ставки
    if bet_type == "zero" and is_zero:
        win = True
        multiplier = 36
    elif bet_type == "red" and is_red:
        win = True
        multiplier = 2
    elif bet_type == "black" and is_black:
        win = True
        multiplier = 2
    elif bet_type == "even" and is_even:
        win = True
        multiplier = 2
    elif bet_type == "odd" and is_odd:
        win = True
        multiplier = 2
    elif bet_type == "small" and is_small:
        win = True
        multiplier = 2
    elif bet_type == "big" and is_big:
        win = True
        multiplier = 2
    elif bet_type == "row1" and is_row1:
        win = True
        multiplier = 3
    elif bet_type == "row2" and is_row2:
        win = True
        multiplier = 3
    elif bet_type == "row3" and is_row3:
        win = True
        multiplier = 3
    elif bet_type == "1-12" and is_dozen1:
        win = True
        multiplier = 3
    elif bet_type == "13-24" and is_dozen2:
        win = True
        multiplier = 3
    elif bet_type == "25-36" and is_dozen3:
        win = True
        multiplier = 3
    
    # Формируем текст типа ставки
    type_names = {
        "red": "красное",
        "black": "черное",
        "even": "чётное",
        "odd": "нечётное",
        "small": "малое 1-18",
        "big": "большое 19-36",
        "zero": "зеро",
        "row1": "1-й ряд",
        "row2": "2-й ряд",
        "row3": "3-й ряд",
        "1-12": "1-12",
        "13-24": "13-24",
        "25-36": "25-36"
    }
    type_text = type_names.get(bet_type, bet_type)
    
    # Обновляем статистику казино
    if 'total_bets' not in user:
        user['total_bets'] = 0
    user['total_bets'] += 1
    
    if win:
        win_amount = bet_amount * multiplier
        user['balance'] += win_amount
        
        # Обновляем статистику побед
        if 'max_casino_win' not in user or win_amount > user['max_casino_win']:
            user['max_casino_win'] = win_amount
        
        if 'win_streak' not in user:
            user['win_streak'] = 0
        user['win_streak'] += 1
        
        if 'max_win_streak' not in user or user['win_streak'] > user['max_win_streak']:
            user['max_win_streak'] = user['win_streak']
        
        update_casino_stats(user_id, bet_amount, win_amount)
        
        result_text = (
            f"🎲 <b>РУЛЕТКА - ВЫИГРЫШ!</b>\n\n"
            f"👤 Игрок: @{username}\n"
            f"🎰 Выпало: {win_number} {color}{extra_text}\n"
            f"🎯 Ставка: {bet_amount:,} ₽ на {type_text}{half_text}\n"
            f"💰 Множитель: x{multiplier}\n"
            f"💵 ВЫИГРЫШ: {win_amount:,} ₽\n"
            f"📈 Чистая прибыль: {win_amount - bet_amount:,} ₽\n\n"
            f"💰 Было: {old_balance:,} ₽\n"
            f"💰 Стало: {user['balance']:,} ₽\n\n"
            f"🎉 ПОЗДРАВЛЯЕМ!"
        )
    else:
        user['win_streak'] = 0
        update_casino_stats(user_id, bet_amount, 0)
        
        result_text = (
            f"🎲 <b>РУЛЕТКА - ПРОИГРЫШ</b>\n\n"
            f"👤 Игрок: @{username}\n"
            f"🎰 Выпало: {win_number} {color}{extra_text}\n"
            f"🎯 Ставка: {bet_amount:,} ₽ на {type_text}{half_text}\n"
            f"❌ Проигрыш: {bet_amount:,} ₽\n\n"
            f"💰 Было: {old_balance:,} ₽\n"
            f"💰 Стало: {user['balance']:,} ₽\n\n"
            f"😢 Повезет в следующий раз!"
        )
    
    await update.message.reply_text(result_text, parse_mode='HTML')
    save_data()
    
    # Проверяем достижения
    new_achs, reward = check_achievements(user_id, user)
    if new_achs:
        await update.message.reply_text(
            f"🎉 <b>НОВЫЕ ДОСТИЖЕНИЯ!</b>\n\n"
            f"{chr(10).join(['• ' + ach for ach in new_achs])}\n\n"
            f"💰 Получено: {reward:,} ₽",
            parse_mode='HTML'
        )
    
    # Очищаем user_data для следующей ставки
    if 'bet_type' in context.user_data:
        del context.user_data['bet_type']
    
    # Возвращаем в меню казино
    keyboard = [
        [
            InlineKeyboardButton("1-12 (x3)", callback_data="bet:1-12"),
            InlineKeyboardButton("13-24 (x3)", callback_data="bet:13-24"),
            InlineKeyboardButton("25-36 (x3)", callback_data="bet:25-36")
        ],
        [
            InlineKeyboardButton("1-й ряд (x3)", callback_data="bet:row1"),
            InlineKeyboardButton("2-й ряд (x3)", callback_data="bet:row2"),
            InlineKeyboardButton("3-й ряд (x3)", callback_data="bet:row3")
        ],
        [
            InlineKeyboardButton("Чёт (x2)", callback_data="bet:even"),
            InlineKeyboardButton("Нечёт (x2)", callback_data="bet:odd")
        ],
        [
            InlineKeyboardButton("Красное (x2)", callback_data="bet:red"),
            InlineKeyboardButton("Чёрное (x2)", callback_data="bet:black")
        ],
        [
            InlineKeyboardButton("Малое (x2)", callback_data="bet:small"),
            InlineKeyboardButton("Большое (x2)", callback_data="bet:big")
        ],
        [
            InlineKeyboardButton("Зеро (x36)", callback_data="bet:zero"),
            InlineKeyboardButton("Выход", callback_data="bet:cancel")
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "🎰 Выберите тип ставки для следующей игры:",
        reply_markup=reply_markup
    )
    await check_all_achievements(update, user_id, user)
    return BET_TYPE

async def casino(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню казино со всеми типами ставок"""
    user_id = update.effective_user.id
    if user_id in banned_users:
        await update.message.reply_text("⛔ Вы заблокированы и не можете использовать бота.")
        return
    
    keyboard = [
        [
            InlineKeyboardButton("1-12 (x3)", callback_data="bet:1-12"),
            InlineKeyboardButton("13-24 (x3)", callback_data="bet:13-24"),
            InlineKeyboardButton("25-36 (x3)", callback_data="bet:25-36")
        ],
        [
            InlineKeyboardButton("1-й ряд (x3)", callback_data="bet:row1"),
            InlineKeyboardButton("2-й ряд (x3)", callback_data="bet:row2"),
            InlineKeyboardButton("3-й ряд (x3)", callback_data="bet:row3")
        ],
        [
            InlineKeyboardButton("Чёт (x2)", callback_data="bet:even"),
            InlineKeyboardButton("Нечёт (x2)", callback_data="bet:odd")
        ],
        [
            InlineKeyboardButton("Красное (x2)", callback_data="bet:red"),
            InlineKeyboardButton("Чёрное (x2)", callback_data="bet:black")
        ],
        [
            InlineKeyboardButton("Малое 1-18 (x2)", callback_data="bet:small"),
            InlineKeyboardButton("Большое 19-36 (x2)", callback_data="bet:big")
        ],
        [
            InlineKeyboardButton("Зеро (x36)", callback_data="bet:zero"),
            InlineKeyboardButton("Отмена", callback_data="bet:cancel")
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🎰 Выберите тип ставки:",
        reply_markup=reply_markup
    )
    return BET_TYPE

async def handle_bet_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора типа ставки"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "bet:cancel":
        await query.edit_message_text("❌ Ставка отменена.")
        return ConversationHandler.END
    
    bet_type = query.data.split(":")[1]
    context.user_data['bet_type'] = bet_type
    
    bet_types = {
        "1-12": "1-12 (x3)",
        "13-24": "13-24 (x3)",
        "25-36": "25-36 (x3)",
        "row1": "1-й ряд (x3)",
        "row2": "2-й ряд (x3)", 
        "row3": "3-й ряд (x3)",
        "even": "чётное (x2)",
        "odd": "нечётное (x2)",
        "red": "красное (x2)",
        "black": "чёрное (x2)",
        "small": "малое 1-18 (x2)",
        "big": "большое 19-36 (x2)",
        "zero": "зеро (x36)"
    }
    
    text = (
        f"Вы выбрали: {bet_types[bet_type]}\n\n"
        "Введите сумму ставки (например: 100к, 1м, 500кк):\n\n"
        "Сокращения:\n"
        "к = 1,000\n"
        "кк = 1,000,000\n"
        "ккк = 1,000,000,000\n\n"
        "Или используйте:\n"
        "• все, алл, вб - весь баланс\n"
        "• половина, пол - 50% баланса\n\n"
        "Для отмены введите /cancel"
    )
    
    # Проверяем, есть ли текст в сообщении
    if query.message.text:
        await query.edit_message_text(text)
    else:
        await query.message.reply_text(text)
    
    return BET_AMOUNT

async def process_bet_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id in banned_users:
        await update.message.reply_text("⛔ Вы заблокированы и не можете использовать бота.")
        return ConversationHandler.END
        
    user = get_user_data(user_id)
    user['last_active'] = time.time()
    
    if not user.get('username'):
        await update.message.reply_text(
            "❌ У вас не установлен никнейм!\n"
            "Пожалуйста, укажите ник командой /set_nick [ваш ник]\n"
            "Это нужно для отображения в рейтингах и при взаимодействиях с другими игроками."
        )
        return ConversationHandler.END
    
    bet_amount_str = update.message.text
    bet_amount = parse_bet_amount(bet_amount_str)
    
    if not bet_amount or bet_amount <= 0:
        await update.message.reply_text("❌ Неверная сумма ставки! Введите положительное число.")
        return BET_AMOUNT  # ВОТ ЭТО ВАЖНО: возвращаемся в состояние BET_AMOUNT
    
    if bet_amount > user['balance']:
        await update.message.reply_text("❌ Недостаточно средств на балансе!")
        return BET_AMOUNT  # ВОТ ЭТО ВАЖНО: возвращаемся в состояние BET_AMOUNT
    
    bet_type = context.user_data.get('bet_type')
    username = user['username']
    win_number = random.randint(0, 36)
    
    # Определяем выигрышные условия
    is_red = win_number in {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}
    is_black = win_number in {2, 4, 6, 8, 10, 11, 13, 15, 17, 20, 22, 24, 26, 28, 29, 31, 33, 35}
    is_even = win_number % 2 == 0 and win_number != 0
    is_odd = win_number % 2 == 1
    is_zero = win_number == 0
    is_small = 1 <= win_number <= 18
    is_big = 19 <= win_number <= 36
    is_first12 = 1 <= win_number <= 12
    is_second12 = 13 <= win_number <= 24
    is_third12 = 25 <= win_number <= 36
    
    win = False
    multiplier = 1
    result_text = f"🎲 Игрок: @{username}\nВыпало: {win_number} "
    
    if bet_type == "zero":
        if is_zero:
            win = True
            multiplier = 36
            result_text += "(зеро)"
        else:
            result_text += "(не зеро)"
            
    elif bet_type == "red":
        if is_red:
            win = True
            multiplier = 2
            result_text += "(красное)"
        else:
            result_text += "(не красное)"
            
    elif bet_type == "black":
        if is_black:
            win = True
            multiplier = 2
            result_text += "(чёрное)"
        else:
            result_text += "(не чёрное)"
            
    elif bet_type == "even":
        if is_even:
            win = True
            multiplier = 2
            result_text += "(чётное)"
        else:
            result_text += "(не чётное)"
            
    elif bet_type == "odd":
        if is_odd:
            win = True
            multiplier = 2
            result_text += "(нечётное)"
        else:
            result_text += "(не нечётное)"
            
    elif bet_type == "small":
        if is_small:
            win = True
            multiplier = 2
            result_text += "(малое)"
        else:
            result_text += "(не малое)"
            
    elif bet_type == "big":
        if is_big:
            win = True
            multiplier = 2
            result_text += "(большое)"
        else:
            result_text += "(не большое)"
            
    elif bet_type == "1-12":
        if is_first12:
            win = True
            multiplier = 3
            result_text += "(1-12)"
        else:
            result_text += "(не 1-12)"
            
    elif bet_type == "13-24":
        if is_second12:
            win = True
            multiplier = 3
            result_text += "(13-24)"
        else:
            result_text += "(не 13-24)"
            
    elif bet_type == "25-36":
        if is_third12:
            win = True
            multiplier = 3
            result_text += "(25-36)"
        else:
            result_text += "(не 25-36)"
    
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
    
    # Очищаем user_data для следующей ставки
    if 'bet_type' in context.user_data:
        del context.user_data['bet_type']
    
    return ConversationHandler.END
    
# ==================== УЛУЧШЕННАЯ СИСТЕМА РАБОТ ====================

# ==================== НОВАЯ СИСТЕМА РАБОТ ====================

async def work_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопок работы"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    if user_id in banned_users:
        await query.answer("⛔ Вы заблокированы", show_alert=True)
        return
    
    user = get_user_data(user_id)
    user['last_active'] = time.time()
    
    # Инициализация данных о работе
    if 'jobs' not in user:
        user['jobs'] = {
            'taxi': {'level': 1, 'completed': 0, 'last_work': None},
            'accountant': {'level': 1, 'completed': 0, 'last_work': None},
            'builder': {'level': 1, 'completed': 0, 'last_work': None},
            'businessman': {'level': 1, 'completed': 0, 'last_work': None}
        }
    
    data = query.data
    print(f"work_handler: {data}")  # Для отладки
    
    if data == "work_back":
        return await work_menu(update, context)
    
    # Проверяем, что это работа (убираем префикс "work_")
    if data.startswith("work_"):
        job_type = data.replace("work_", "")  # убираем "work_"
        return await show_job_info(update, context, job_type)




# ==================== ИСПРАВЛЕННЫЕ ФУНКЦИИ РАБОТ ====================

# ==================== УЛУЧШЕННАЯ СИСТЕМА РАБОТ ====================

# Конфигурация профессий
JOBS_CONFIG = {
    'taxi': {
        'name': '🚕 ТАКСИСТ',
        'emoji': '🚕',
        'description': 'Развозите пассажиров по городу',
        'salary': [20000, 40000, 80000, 150000, 300000],
        'cooldown': [300, 240, 180, 120, 60],  # секунды
        'exp_needed': [0, 50, 150, 300, 500],  # работ для уровня
        'max_level': 5,
        'city_scale': ['🏘️', '🏙️', '🌆', '🌃', '🗼'],  # город разрастается
        'car': ['🛵', '🚗', '🚙', '🏎️', '🚁'],  # машины улучшаются
        'bonuses': {
            2: '🚗 Быстрая езда (кулдаун -1 мин)',
            3: '💰 Чаевые (+20% к доходу)',
            4: '🏎️ Спорткар (шанс x2 10%)',
            5: '🚁 VIP-клиенты (доход +50%)'
        },
        'events': [
            'пробка на дороге',
            'щедрый пассажир',
            'дальняя поездка',
            'ночной тариф',
            'праздничный бонус'
        ]
    },
    'accountant': {
        'name': '📊 БУХГАЛТЕР',
        'emoji': '📊',
        'description': 'Ведите учет и находите ошибки',
        'salary': [1000000, 2000000, 4000000, 8000000, 15000000],
        'cooldown': [3600, 3000, 2400, 1800, 1200],  # секунды
        'exp_needed': [0, 30, 80, 150, 250],
        'max_level': 5,
        'office': ['🏢', '🏛️', '🏦', '💼', '👔'],
        'tools': ['🧮', '📠', '💻', '🖥️', '📡'],
        'bonuses': {
            2: '📈 Аналитика (шанс найти ошибку +5%)',
            3: '💼 VIP-клиенты (доход +40%)',
            4: '🔍 Аудит (шанс x2 15%)',
            5: '👑 Финдиректор (ежедневный бонус)'
        },
        'events': [
            'ошибка в отчете',
            'выгодный контракт',
            'налоговая проверка',
            'премия за квартал',
            'бухгалтерская рокировка'
        ]
    },
    'builder': {
        'name': '👷 СТРОИТЕЛЬ',
        'emoji': '👷',
        'description': 'Стройте здания и небоскребы',
        'salary': [50000, 100000, 200000, 400000, 800000],
        'cooldown': [1800, 1500, 1200, 900, 600],
        'exp_needed': [0, 40, 100, 200, 350],
        'max_level': 5,
        'building': ['🏗️', '🏘️', '🏢', '🏭', '🏰'],
        'tools': ['🔨', '🪚', '🔧', '🏗️', '🚁'],
        'bonuses': {
            2: '🔨 Прораб (шанс найти стройматериалы)',
            3: '🏗️ Кран (доход +35%)',
            4: '🏭 Завод (шанс x2 12%)',
            5: '🏰 Небоскреб (еженедельный бонус)'
        },
        'events': [
            'доставка материалов',
            'перекрытие дороги',
            'высотные работы',
            'новая стройка',
            'премия за скорость'
        ]
    },
    'businessman': {
        'name': '👨‍💼 БИЗНЕСМЕН',
        'emoji': '👨‍💼',
        'description': 'Заключайте выгодные сделки',
        'salary': [500000, 1000000, 2000000, 4000000, 10000000],
        'cooldown': [3600, 3000, 2400, 1800, 1200],
        'exp_needed': [0, 25, 70, 150, 300],
        'max_level': 5,
        'office': ['💼', '📈', '🏦', '🌍', '👑'],
        'suit': ['👔', '🤵', '👑', '💎', '✨'],
        'bonuses': {
            2: '🤝 Связи (шанс на бонус)',
            3: '💎 Элитные клиенты (доход +50%)',
            4: '📊 Биржа (шанс x3 10%)',
            5: '👑 Магнат (пассивный доход)'
        },
        'events': [
            'слияние компаний',
            'инвестиции',
            'кризис',
            'IPO компании',
            'мега-сделка'
        ]
    }
}

# Достижения
ACHIEVEMENTS = {
    'taxi': {
        100: {'name': '🏆 НОВИЧОК ДОРОГ', 'reward': 100000},
        500: {'name': '🏆 МАСТЕР РУЛЯ', 'reward': 500000},
        1000: {'name': '🏆 КОРОЛЬ ДОРОГ', 'reward': 2000000}
    },
    'accountant': {
        50: {'name': '🏆 СЧЕТОВОД', 'reward': 500000},
        200: {'name': '🏆 ФИНАНСИСТ', 'reward': 2000000},
        500: {'name': '🏆 ГЕНИЙ УЧЕТА', 'reward': 5000000}
    },
    'builder': {
        100: {'name': '🏆 СТРОИТЕЛЬ', 'reward': 300000},
        300: {'name': '🏆 ПРОРАБ', 'reward': 1000000},
        600: {'name': '🏆 АРХИТЕКТОР', 'reward': 3000000}
    },
    'businessman': {
        50: {'name': '🏆 БИЗНЕСМЕН', 'reward': 1000000},
        150: {'name': '🏆 ИНВЕСТОР', 'reward': 5000000},
        300: {'name': '🏆 ОЛИГАРХ', 'reward': 10000000}
    }
}

# ==================== КЛИКЕР ====================
clicker_games = {}
clicker_banned = {}

async def clicker_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    
    if user_id in clicker_banned:
        if time.time() < clicker_banned[user_id]:
            await query.answer("❌ Бан на 10 минут!", show_alert=True)
            return
    
    clicker_games[user_id] = {'correct': random.randint(0, 4)}
    await show_clicker(update, context)

async def show_clicker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = str(query.from_user.id)
    game = clicker_games.get(user_id)
    if not game:
        return
    
    keyboard = []
    row = []
    for i in range(5):
        if i == game['correct']:
            row.append(InlineKeyboardButton("✅", callback_data=f"clicker_{i}"))
        else:
            row.append(InlineKeyboardButton("❌", callback_data=f"clicker_{i}"))
        if len(row) == 3:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    
    keyboard.append([InlineKeyboardButton("🚪 ВЫЙТИ", callback_data="clicker_exit")])
    
    await query.edit_message_text(
        "🎮 <b>КЛИКЕР</b>\n\nНажми на ✅, чтобы получить 10,000,000 ₽\n\n⚠️ Ошибка = бан 10 минут",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )

async def clicker_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    idx = int(query.data.replace("clicker_", ""))
    game = clicker_games.get(user_id)
    
    if not game:
        return
    
    if idx == game['correct']:
        user = get_user_data(user_id)
        user['balance'] += 10_000_000
        save_data()
        await query.answer("✅ +10,000,000 ₽!", show_alert=True)
        game['correct'] = random.randint(0, 4)
        await show_clicker(update, context)
    else:
        clicker_banned[user_id] = time.time() + 600
        del clicker_games[user_id]
        await query.edit_message_text("💥 ОШИБКА! Вы забанены в кликере на 10 минут.")

async def clicker_exit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = str(query.from_user.id)
    if user_id in clicker_games:
        del clicker_games[user_id]
    await query.edit_message_text("🚪 Выход из игры")

async def work_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню работы"""
    user_id = update.effective_user.id
    
    if str(user_id) in banned_users:
        if update.callback_query:
            await update.callback_query.answer("⛔ Вы заблокированы", show_alert=True)
            return ConversationHandler.END
        else:
            await update.message.reply_text("⛔ Вы заблокированы и не можете использовать бота.")
            return ConversationHandler.END
    
    user = get_user_data(user_id)
    user['last_active'] = time.time()
    
    # Инициализация данных о работе
    if 'jobs' not in user:
        user['jobs'] = {}
    
    # Статистика работ
    total_works = 0
    total_earned = 0
    for job_type, job_data in user['jobs'].items():
        total_works += job_data.get('completed', 0)
    
    # Красивое меню
    text = (
        "🏢 <b>ЦЕНТР ЗАНЯТОСТИ</b>\n"
        "═══════════════════\n\n"
        
        "📊 <b>Ваша статистика:</b>\n"
        f"├ Всего работ: {total_works}\n"
        f"└ Активных профессий: {len(user['jobs'])}/4\n\n"
        
        "🎯 <b>Доступные профессии:</b>\n"
        "🚕 Таксист    - быстрые поездки\n"
        "📊 Бухгалтер  - высокий доход\n"
        "👷 Строитель  - стабильный заработок\n"
        "👨‍💼 Бизнесмен - рискованные сделки\n\n"
        
        "👇 <b>Выберите профессию:</b>"
    )
    
    keyboard = [
    [InlineKeyboardButton("🚕 Таксист", callback_data="work_taxi")],
    [InlineKeyboardButton("📊 Бухгалтер", callback_data="work_accountant")],
    [InlineKeyboardButton("👷 Строитель", callback_data="work_builder")],
    [InlineKeyboardButton("👨‍💼 Бизнесмен", callback_data="work_businessman")],
    [InlineKeyboardButton("🎮 КЛИКЕР", callback_data="work_clicker")],  # НОВАЯ КНОПКА
    [InlineKeyboardButton("🔙 НАЗАД", callback_data="work_back_to_main")]
]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        await update.callback_query.edit_message_text(
            text=text,
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    else:
        await update.message.reply_text(
            text=text,
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    
    return WORK_MENU

async def work_show_job(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать информацию о работе"""
    query = update.callback_query
    await query.answer()
    
    job_type = query.data.replace("work_", "")
    config = JOBS_CONFIG[job_type]
    
    user_id = query.from_user.id
    user = get_user_data(user_id)
    
    # Инициализация данных
    if 'jobs' not in user:
        user['jobs'] = {}
    if job_type not in user['jobs']:
        user['jobs'][job_type] = {
            'level': 1,
            'completed': 0,
            'last_work': None,
            'uses_today': 0,
            'last_date': datetime.now().strftime('%Y-%m-%d'),
            'achievements': []
        }
    
    job_data = user['jobs'][job_type]
    level = job_data['level']
    completed = job_data['completed']
    
    # Прогресс до следующего уровня
    if level < config['max_level']:
        next_req = config['exp_needed'][level]
        progress = completed
        percent = min(100, int(progress / next_req * 100))
        progress_bar = "🟩" * (percent // 10) + "⬜" * (10 - (percent // 10))
        progress_text = f"{progress_bar} {percent}% ({progress}/{next_req})"
    else:
        progress_text = "⭐ МАКСИМАЛЬНЫЙ УРОВЕНЬ ⭐"
    
    # Проверка доступности
    can_work = True
    time_left = 0
    
    if job_data.get('last_work'):
        last_work = datetime.fromisoformat(job_data['last_work'])
        cooldown = config['cooldown'][level-1]
        time_passed = (datetime.now() - last_work).total_seconds()
        
        if time_passed < cooldown:
            can_work = False
            time_left = cooldown - time_passed
    
    # Красивое отображение времени
    if time_left > 0:
        hours = int(time_left // 3600)
        minutes = int((time_left % 3600) // 60)
        seconds = int(time_left % 60)
        
        if hours > 0:
            time_text = f"{hours}ч {minutes}м"
        elif minutes > 0:
            time_text = f"{minutes}м {seconds}с"
        else:
            time_text = f"{seconds}с"
    else:
        time_text = "✅ ГОТОВО К РАБОТЕ"
    
    # Информация о зарплате
    salary = config['salary'][level-1]
    
    # Бонусы за уровень
    bonuses_text = ""
    if level > 1:
        bonuses_text = "\n\n✨ <b>Активные бонусы:</b>\n"
        for lvl in range(2, level + 1):
            if lvl in config['bonuses']:
                bonuses_text += f"├ Ур.{lvl}: {config['bonuses'][lvl]}\n"
    
    # Достижения
    achievements_text = ""
    achievements = ACHIEVEMENTS.get(job_type, {})
    for req, ach in achievements.items():
        if completed >= req and str(req) not in job_data.get('achievements', []):
            user['balance'] += ach['reward']
            job_data.setdefault('achievements', []).append(str(req))
            achievements_text += f"\n🎉 {ach['name']} +{ach['reward']:,} ₽"
    
    # Формируем текст
    text = (
        f"{config['emoji']} <b>{config['name']}</b>\n"
        f"<i>{config['description']}</i>\n"
        f"═══════════════════\n\n"
        
        f"🏙️ <b>УРОВЕНЬ {level}</b> {config['city_scale'][level-1]}\n"
        f"🚗 Транспорт: {config['car'][level-1]}\n\n"
        
        f"📊 <b>Статистика:</b>\n"
        f"├ Выполнено работ: {completed}\n"
        f"└ Прогресс: {progress_text}\n\n"
        
        f"💰 <b>Зарплата:</b> {salary:,} ₽\n"
        f"⏱️ <b>Статус:</b> {time_text}\n"
        f"{bonuses_text}"
        f"{achievements_text}"
    )
    
    # Клавиатура
    keyboard = []
    if can_work:
        keyboard.append([InlineKeyboardButton("🔄 НАЧАТЬ РАБОТУ", callback_data=f"start_work_{job_type}")])
    keyboard.append([InlineKeyboardButton("🔙 НАЗАД", callback_data="work_back")])
    
    await query.edit_message_text(
        text=text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )
    
    save_data()
    return WORK_MENU

async def work_start_job(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начать работу с анимацией"""
    query = update.callback_query
    await query.answer()
    
    job_type = query.data.replace("start_work_", "")
    config = JOBS_CONFIG[job_type]
    
    user_id = query.from_user.id
    user = get_user_data(user_id)
    job_data = user['jobs'][job_type]
    level = job_data['level']
    
    # Проверка кулдауна
    if job_data.get('last_work'):
        last_work = datetime.fromisoformat(job_data['last_work'])
        cooldown = config['cooldown'][level-1]
        if (datetime.now() - last_work).total_seconds() < cooldown:
            await query.answer("⏳ Еще не время! Подождите.", show_alert=True)
            return WORK_MENU
    
    # Анимация для разных профессий
    if job_type == 'taxi':
        # Такси - анимация поездки
        frames = [
            f"🚕 <b>{config['name']}</b>\n═══════════════\n\n🚦 Садим пассажира... {config['passengers'][level-1]}",
            f"🚕 <b>{config['name']}</b>\n═══════════════\n\n🛣️ Выезжаем на маршрут... {config['city'][level-1]}",
            f"🚕 <b>{config['name']}</b>\n═══════════════\n\n🏁 Прибываем к месту назначения!",
            f"🚕 <b>{config['name']}</b>\n═══════════════\n\n💰 Получаем оплату..."
        ]
        
        for frame in frames:
            await query.edit_message_text(frame, parse_mode='HTML')
            await asyncio.sleep(1.5)
    
    elif job_type == 'accountant':
        # Бухгалтер - анимация подсчета
        frames = [
            f"📊 <b>{config['name']}</b>\n═══════════════\n\n🧮 Считаем цифры...",
            f"📊 <b>{config['name']}</b>\n═══════════════\n\n📑 Проверяем отчеты...",
            f"📊 <b>{config['name']}</b>\n═══════════════\n\n🔍 Ищем ошибки...",
            f"📊 <b>{config['name']}</b>\n═══════════════\n\n✅ Баланс сошелся!"
        ]
        
        for frame in frames:
            await query.edit_message_text(frame, parse_mode='HTML')
            await asyncio.sleep(1.5)
    
    elif job_type == 'builder':
        # Строитель - анимация стройки
        progress = ["🟫", "🧱", "🏗️", "🏢"]
        for i, stage in enumerate(progress):
            text = (
                f"👷 <b>{config['name']}</b>\n"
                f"═══════════════\n\n"
                f"Строим этаж {i+1}/4:\n"
                f"{'█' * (i+1)}{'░' * (3-i)} {stage}\n"
                f"{config['building'][level-1]} Прогресс: {25*(i+1)}%"
            )
            await query.edit_message_text(text, parse_mode='HTML')
            await asyncio.sleep(1.5)
    
    elif job_type == 'businessman':
        # Бизнесмен - анимация сделки
        frames = [
            f"👨‍💼 <b>{config['name']}</b>\n═══════════════\n\n🤝 Ведем переговоры... {config['office'][level-1]}",
            f"👨‍💼 <b>{config['name']}</b>\n═══════════════\n\n📝 Подписываем контракт... {config['suit'][level-1]}",
            f"👨‍💼 <b>{config['name']}</b>\n═══════════════\n\n💼 Закрываем сделку...",
            f"👨‍💼 <b>{config['name']}</b>\n═══════════════\n\n💰 Получаем прибыль!"
        ]
        
        for frame in frames:
            await query.edit_message_text(frame, parse_mode='HTML')
            await asyncio.sleep(1.5)
    
    # Завершаем работу
    await work_finish_job(update, context, job_type)

async def work_finish_job(update: Update, context: ContextTypes.DEFAULT_TYPE, job_type: str):
    """Завершение работы с визуальным результатом"""
    query = update.callback_query
    user_id = query.from_user.id
    user = get_user_data(user_id)
    
    config = JOBS_CONFIG[job_type]
    job_data = user['jobs'][job_type]
    level = job_data['level']
    
    # Базовая зарплата
    min_earn = config['min_earn'][level-1]
    max_earn = config['max_earn'][level-1]
    base_salary = random.randint(min_earn, max_earn)
    
    # Случайные бонусы
    bonus_mult = 1.0
    bonus_effects = []
    
    # Бонусы за уровень
    if level >= 3 and random.random() < 0.2:
        bonus_mult *= 1.5
        bonus_effects.append("💰 Чаевые! +50%")
    
    if level >= 4 and random.random() < 0.1:
        bonus_mult *= 2.0
        bonus_effects.append("✨ КРИТИЧЕСКИЙ УСПЕХ! x2")
    
    if level >= 5 and random.random() < 0.05:
        bonus_mult *= 3.0
        bonus_effects.append("💎 ДЖЕКПОТ! x3")
    
    # Спецэффекты для разных профессий
    if job_type == 'taxi' and level >= 4 and random.random() < 0.15:
        bonus_mult *= 1.8
        bonus_effects.append("🏎️ Спорткар! +80%")
    
    if job_type == 'accountant' and level >= 4 and random.random() < 0.15:
        bonus_mult *= 1.8
        bonus_effects.append("🔍 Нашел ошибку! +80%")
    
    if job_type == 'builder' and level >= 4 and random.random() < 0.15:
        bonus_mult *= 1.8
        bonus_effects.append("🏗️ Премия за высоту! +80%")
    
    if job_type == 'businessman' and level >= 4 and random.random() < 0.15:
        bonus_mult *= 2.5
        bonus_effects.append("📈 Мега-сделка! x2.5")
    
    # Итоговая зарплата
    final_salary = int(base_salary * bonus_mult)
    user['balance'] += final_salary
    
    # Обновляем статистику
    job_data['completed'] += 1
    job_data['last_work'] = datetime.now().isoformat()
    
    # Проверка повышения уровня
    level_up = False
    old_level = level
    
    if level < config['levels']:
        next_level_req = config['requirements'].get(level + 1, 999)
        if job_data['completed'] >= next_level_req:
            job_data['level'] += 1
            level_up = True
            level = job_data['level']
    
    # Создаем визуально красивый результат
    result_parts = []
    
    # Заголовок
    result_parts.append(f"✅ <b>РАБОТА ЗАВЕРШЕНА!</b>")
    result_parts.append(f"═══════════════════")
    result_parts.append("")
    
    # Профессия и уровень
    level_emoji = ["⚪", "🟢", "🔵", "🟣", "🟡"][level-1]
    result_parts.append(f"{config['emoji']} <b>{config['name']}</b> {level_emoji} Ур.{level}")
    
    # Визуал для разных профессий
    if job_type == 'taxi':
        result_parts.append(f"🚗 Машина: {config['cars'][level-1]}")
        result_parts.append(f"🏙️ Город: {config['city'][level-1]}")
    elif job_type == 'accountant':
        result_parts.append(f"📠 Офис: {config['office'][level-1]}")
        result_parts.append(f"💻 Техника: {config['tools'][level-1]}")
    elif job_type == 'builder':
        result_parts.append(f"🏗️ Стройка: {config['building'][level-1]}")
        result_parts.append(f"🔧 Инструменты: {config['tools'][level-1]}")
    elif job_type == 'businessman':
        result_parts.append(f"💼 Офис: {config['office'][level-1]}")
        result_parts.append(f"👔 Костюм: {config['suit'][level-1]}")
    
    result_parts.append("")
    
    # Доход
    result_parts.append(f"💰 <b>ДОХОД:</b>")
    result_parts.append(f"├ База: {base_salary:,} ₽")
    
    if bonus_mult > 1.0:
        result_parts.append(f"├ Множитель: x{bonus_mult:.1f}")
        result_parts.append(f"└ ИТОГО: {final_salary:,} ₽")
    else:
        result_parts.append(f"└ ИТОГО: {final_salary:,} ₽")
    
    result_parts.append("")
    
    # Бонусы
    if bonus_effects:
        result_parts.append(f"🎁 <b>БОНУСЫ:</b>")
        for bonus in bonus_effects:
            result_parts.append(f"├ {bonus}")
        result_parts.append("")
    
    # Статистика
    result_parts.append(f"📊 <b>СТАТИСТИКА:</b>")
    result_parts.append(f"├ Всего работ: {job_data['completed']}")
    
    # Прогресс до следующего уровня
    if level < config['levels']:
        next_req = config['requirements'].get(level + 1, 999)
        progress = job_data['completed']
        percent = min(100, int(progress / next_req * 100))
        
        # Визуальный прогресс-бар
        filled = "█" * (percent // 10)
        empty = "░" * (10 - (percent // 10))
        progress_bar = f"{filled}{empty}"
        
        result_parts.append(f"├ До ур.{level + 1}: {progress_bar} {percent}%")
        result_parts.append(f"└ {progress}/{next_req} работ")
    else:
        result_parts.append(f"└ ⭐ МАКСИМАЛЬНЫЙ УРОВЕНЬ ⭐")
    
    # Повышение уровня
    if level_up:
        result_parts.append("")
        result_parts.append(f"🎉 <b>УРОВЕНЬ ПОВЫШЕН!</b> 🎉")
        result_parts.append(f"✨ Теперь {level} уровень!")
        
        # Новые возможности
        if level == 2:
            result_parts.append(f"🔓 {config['bonuses'].get(2, 'Новый бонус!')}")
        elif level == 3:
            result_parts.append(f"🔓 {config['bonuses'].get(3, 'Новый бонус!')}")
        elif level == 4:
            result_parts.append(f"🔓 {config['bonuses'].get(4, 'Новый бонус!')}")
        elif level == 5:
            result_parts.append(f"🔓 {config['bonuses'].get(5, 'Максимальный бонус!')}")
    
    # Конец
    result_parts.append("")
    result_parts.append("⬇️ Выберите действие ⬇️")
    
    # Клавиатура
    keyboard = [
        [InlineKeyboardButton("🔄 РАБОТАТЬ СНОВА", callback_data=f"work_{job_type}")],
        [InlineKeyboardButton("🔙 В МЕНЮ РАБОТ", callback_data="work_back")]
    ]
    
    final_text = "\n".join(result_parts)
    
    await query.edit_message_text(
        text=final_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )
    
    save_data()
    return WORK_MENU


async def work_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Вернуться в меню работ"""
    query = update.callback_query
    await query.answer()
    return await work_menu(update, context)

async def work_back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Вернуться в главное меню"""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "Главное меню",
        reply_markup=get_main_keyboard()
    )
    return ConversationHandler.END

async def start_work(update: Update, context: ContextTypes.DEFAULT_TYPE, job_type: str):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user = get_user_data(user_id)
    job_data = user['jobs'][job_type]
    
    # Проверяем, можно ли начать работу
    if job_data.get('last_work'):
        cooldowns = {
            'taxi': [60, 45, 30],
            'accountant': [3600, 2700, 1800],
            'builder': [1800, 1200, 900],
            'businessman': [3600, 2700, 1800]
        }
        last_work = datetime.fromisoformat(job_data['last_work'])
        cooldown = cooldowns[job_type][job_data['level']-1]
        if (datetime.now() - last_work).total_seconds() < cooldown:
            await query.answer("⏳ Вы еще не можете начать работу!", show_alert=True)
            return await show_job_info(update, context, job_type)
    
    # Для таксиста добавим таймер
    if job_type == 'taxi':
        # Случайное время ожидания от 15 до 60 секунд
        wait_time = random.randint(15, 60)
        await query.edit_message_text(
            f"🚕 Вы приняли заказ! Ожидайте {wait_time} секунд...",
            reply_markup=None
        )
        
        # Сохраняем данные в контекст работы
        context.job_queue.run_once(
            callback=finish_work_callback,
            when=wait_time,
            data={
                'job_type': job_type,
                'user_id': user_id,
                'chat_id': query.message.chat_id,
                'message_id': query.message.message_id
            },
            name=f"work_{user_id}_{job_type}"
        )
    else:
        # Для других работ сразу завершаем
        await finish_work(
            context=context,
            job_type=job_type,
            user_id=user_id,
            chat_id=query.message.chat_id,
            message_id=query.message.message_id
        )
# ==================== ХРАНИЛИЩА ДАННЫХ БАНД ====================
gangs = {}
gang_invites = {}
gang_wars = {}
async def gang_show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    
    # Находим банду пользователя
    user_gang = None
    for gang in gangs.values():
        if user_id in gang['members']:
            user_gang = gang
            break
    
    if not user_gang:
        await query.answer("❌ Вы не в банде!", show_alert=True)
        return GANG_MENU
    
    # Простая статистика
    text = (
        f"📊 Статистика банды '{user_gang['name']}':\n\n"
        f"🏆 Кубки: {user_gang['trophies']}\n"
        f"💰 Казна: {user_gang['bank']:,} ₽\n"
        f"📊 Уровень: {user_gang['level']}\n"
        f"👥 Участники: {len(user_gang['members'])}\n"
        f"⚔️ Войны: {user_gang['wins']}побед / {user_gang['losses']}поражений"
    )
    
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="gang_back")]]
    
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return GANG_MENU

async def gang_show_manage(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("📝 Изменить описание", callback_data="gang_change_desc")],
        [InlineKeyboardButton("👥 Назначить зама", callback_data="gang_promote")],
        [InlineKeyboardButton("👢 Выгнать участника", callback_data="gang_kick")],
        [InlineKeyboardButton("🔧 Настройки вступления", callback_data="gang_join_settings")],
        [InlineKeyboardButton("🔙 Назад", callback_data="gang_back")]
    ]
    
    await query.edit_message_text(
        "⚙️ Меню управления бандой:\n\n"
        "Доступные действия:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return GANG_MENU
    
async def gang_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_id in banned_users:
        if update.callback_query:
            await update.callback_query.answer("⛔ Вы заблокированы", show_alert=True)
            return
        else:
            await update.message.reply_text("⛔ Вы заблокированы и не можете использовать бота.")
            return
    
    user = get_user_data(user_id)
    user['last_active'] = time.time()
    
    # Ищем банду пользователя
    user_gang = None
    gang_role = None
    for gang_id, gang in gangs.items():
        if user_id in gang['members']:
            user_gang = gang
            gang_role = gang['members'][user_id]['role']
            break
    
    keyboard = []
    
    if not user_gang:
        # Пользователь не в банде
        keyboard = [
            [InlineKeyboardButton("🏴 Создать банду", callback_data="gang_create")],
            [InlineKeyboardButton("🔍 Поиск банд", callback_data="gang_search")],
            [InlineKeyboardButton("📥 Мои приглашения", callback_data="gang_invites_list")],
            [InlineKeyboardButton("🏆 Топ банд", callback_data="gang_top")],
        ]
        text = "🏴 Меню банд:\n\nВы не состоите в банде."
    else:
        # Пользователь в банде
        gang = user_gang
        member_count = len(gang['members'])
        max_members = GANG_CONFIG['max_members'][gang['level']]
        
        # Определяем место в топе
        sorted_gangs = sorted(gangs.values(), key=lambda x: x['trophies'], reverse=True)
        position = None
        for i, g in enumerate(sorted_gangs, 1):
            if g['id'] == gang['id']:
                position = i
                break
        
        # Определяем роль текстом
        role_text = {
            'leader': '👑 Лидер',
            'co-leader': '👥 Зам',
            'member': '👤 Участник'
        }.get(gang_role, '👤 Участник')
        
        # Формируем полный текст
        text = (
            f"🏴 Банда: {gang['name']}\n"
            f"👑 Лидер: @{gang['leader_name']}\n"
            f"🎯 Ваша роль: {role_text}\n\n"
            
            f"📊 Уровень: {gang['level']}\n"
            f"👥 Участники: {member_count}/{max_members}\n"
            f"🏆 Кубки: {gang['trophies']}\n"
            f"📍 Место в топе: #{position if position else '—'}\n"
            f"💰 Казна: {gang['bank']:,} ₽\n\n"
            
            f"⚔️ Войны: {gang['wins']}побед / {gang['losses']}поражений"
        )
        
        keyboard.append([InlineKeyboardButton("👥 Участники", callback_data="gang_members")])
        keyboard.append([InlineKeyboardButton("📊 Подробная статистика", callback_data="gang_stats")])
        
        if gang_role in ['leader', 'co-leader']:
            keyboard.append([InlineKeyboardButton("⚙️ Управление", callback_data="gang_manage")])
            keyboard.append([InlineKeyboardButton("📨 Пригласить", callback_data="gang_invite")])
        
        keyboard.append([InlineKeyboardButton("⚔️ Атаковать банду", callback_data="gang_war")])
        keyboard.append([InlineKeyboardButton("🎁 Внести в казну", callback_data="gang_donate")])
        
        if gang_role == 'leader':
            keyboard.append([InlineKeyboardButton("⚠️ Роспуск банды", callback_data="gang_disband")])
        
        keyboard.append([InlineKeyboardButton("🚪 Покинуть банду", callback_data="gang_leave")])
    
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="gang_back")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(text, reply_markup=reply_markup)
    
    return GANG_MENU

async def gang_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "gang_create":
        return await gang_create_start(update, context)
    elif query.data == "gang_search":
        return await gang_search(update, context)
    elif query.data == "gang_invites_list":
        return await gang_show_invites(update, context)
    elif query.data == "gang_top":
        return await gang_show_top(update, context)
    elif query.data == "gang_members":
        return await gang_show_members(update, context)
    elif query.data == "gang_stats":
        return await gang_show_stats(update, context)  # Добавлено
    elif query.data == "gang_manage":
        return await gang_show_manage(update, context)  # Добавлено
    elif query.data == "gang_invite":
        return await gang_invite_start(update, context)
    elif query.data == "gang_war":
        return await gang_war_start(update, context)
    elif query.data == "gang_donate":
        return await gang_donate_start(update, context)
    elif query.data == "gang_disband":
        return await gang_disband_start(update, context)
    elif query.data == "gang_leave":
        return await gang_leave_start(update, context)
    elif query.data == "gang_back":
        return await gang_menu(update, context)
    elif query.data.startswith("gang_war_target_"):
        return await gang_war_target(update, context)
    elif query.data.startswith("gang_war_start_"):
        return await gang_war_execute(update, context)
    elif query.data == "gang_accept_invite":
        return await gang_accept_invite_start(update, context)
    elif query.data == "gang_reject_invite":
        return await gang_reject_invite_start(update, context)
    elif query.data == "gang_leave_confirm":
        return await gang_leave_confirm(update, context)
    elif query.data == "gang_disband_confirm":
        return await gang_disband_confirm(update, context)
    
    return GANG_MENU

async def gang_create_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    user = get_user_data(user_id)
    
    # Проверяем, не в банде ли уже
    for gang in gangs.values():
        if user_id in gang['members']:
            await query.answer("❌ Вы уже в банде!", show_alert=True)
            return GANG_MENU
    
    # Проверяем баланс (100ккк = 100,000,000,000)
    if user['balance'] < 100_000_000_000:
        await query.answer("❌ Нужно 100ккк для создания банды!", show_alert=True)
        return GANG_MENU
    
    await query.edit_message_text(
        "🏴 Создание банды\n\n"
        "💰 Стоимость: 100,000,000,000 ₽ (100ккк)\n"
        "💳 Ваш баланс: {:,} ₽\n\n"
        "Введите название банды (3-20 символов):".format(user['balance']),
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="gang_back")]])
    )
    return GANG_CREATE

# ==================== УПРАВЛЕНИЕ ПРОМОКОДАМИ ====================
# ==================== УПРАВЛЕНИЕ ПРОМОКОДАМИ ====================
async def process_promo_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ПРОСТО УБЕРИ ПРОВЕРКУ СЕССИИ - ПРОБЛЕМА В НЕЙ
    # user_id = str(update.effective_user.id)
    # if user_id not in active_sessions:
    #     await update.message.reply_text("⛔ Сессия истекла!")
    #     return ConversationHandler.END
    
    # Вместо проверки - просто обновляем если есть
    user_id = str(update.effective_user.id)
    if user_id in active_sessions:
        active_sessions[user_id]['last_activity'] = time.time()
    
    action = context.user_data.get('admin_action')
    promo_name = update.message.text.strip().upper()
    
    if action == 'delete_promo':
        if promo_name not in PROMOCODES:
            await update.message.reply_text("❌ Такой промокод не существует!")
            return await show_admin_panel(update, context)
        
        # Удаляем промокод
        deleted_promo = PROMOCODES[promo_name]
        del PROMOCODES[promo_name]
        
        # Сохраняем данные
        save_data()
        
        # Формируем сообщение об удалении
        money = deleted_promo['reward'].get('money', 0)
        coins = deleted_promo['reward'].get('coins', 0)
        item = deleted_promo['reward'].get('item', 'Нет')
        
        await update.message.reply_text(
            f"✅ Промокод {promo_name} удален!\n\n"
            f"📊 Было использовано: {deleted_promo.get('used', 0)}/{deleted_promo.get('max_uses', 0)}\n"
            f"💰 Награда: {money:,} ₽, {coins} койнов\n"
            f"🎁 Предмет: {item}"
        )
        return await show_admin_panel(update, context)
    
    # Проверяем на существование для создания нового промокода
    if promo_name in PROMOCODES:
        await update.message.reply_text("❌ Такой промокод уже существует! Введите другое название:")
        return AWAITING_PROMO_NAME
    
    # Проверяем формат
    if not promo_name.isalnum() or len(promo_name) < 3:
        await update.message.reply_text("❌ Неверный формат! Используйте только латинские буквы и цифры (мин. 3 символа):")
        return AWAITING_PROMO_NAME
    
    context.user_data['promo_name'] = promo_name
    
    keyboard = [
        [InlineKeyboardButton("💰 Деньги", callback_data="promo_type_money")],
        [InlineKeyboardButton("🪙 Койны", callback_data="promo_type_coins")],
        [InlineKeyboardButton("💰+🪙 Деньги и койны", callback_data="promo_type_both")],
        [InlineKeyboardButton("🎁 Предмет", callback_data="promo_type_item")]
    ]
    
    await update.message.reply_text(
        f"✅ Название промокода: {promo_name}\n\n"
        "Выберите тип награды:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return AWAITING_PROMO_TYPE

async def process_promo_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    # Обновляем сессию если есть
    user_id = str(query.from_user.id)
    if user_id in active_sessions:
        active_sessions[user_id]['last_activity'] = time.time()
    
    promo_type = query.data.split('_')[2]
    context.user_data['promo_type'] = promo_type
    
    if promo_type == 'money':
        await query.edit_message_text(
            "💰 Введите сумму денег (например: 1000000, 5кк, 1м):"
        )
        return AWAITING_PROMO_VALUE
    elif promo_type == 'coins':
        await query.edit_message_text(
            "🪙 Введите количество койнов:"
        )
        return AWAITING_PROMO_VALUE
    elif promo_type == 'both':
        await query.edit_message_text(
            "Введите сумму денег и койнов через пробел (пример: 1000000 50):\n"
            "Формат: [деньги] [койны]"
        )
        return AWAITING_PROMO_VALUE
    elif promo_type == 'item':
        await query.edit_message_text(
            "🎁 Введите название предмета (например: fire_extinguisher):"
        )
        return AWAITING_PROMO_VALUE

async def process_promo_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Просто обрабатываем, без проверок сессии
    text = update.message.text.strip()
    promo_type = context.user_data.get('promo_type')
    
    try:
        if promo_type == 'money':
            amount = parse_bet_amount(text)
            if not amount or amount <= 0:
                raise ValueError
            context.user_data['promo_reward'] = {'money': amount}
            
        elif promo_type == 'coins':
            coins = int(text)
            if coins <= 0:
                raise ValueError
            context.user_data['promo_reward'] = {'coins': coins}
            
        elif promo_type == 'both':
            parts = text.split()
            if len(parts) != 2:
                raise ValueError
            money = parse_bet_amount(parts[0])
            coins = int(parts[1])
            if money <= 0 or coins <= 0:
                raise ValueError
            context.user_data['promo_reward'] = {'money': money, 'coins': coins}
            
        elif promo_type == 'item':
            context.user_data['promo_reward'] = {'item': text}
        
        await update.message.reply_text(
            "Введите максимальное количество использований промокода:"
        )
        return AWAITING_PROMO_USES  # ВОТ ЭТО ВАЖНО - возвращаем следующее состояние
        
    except ValueError:
        await update.message.reply_text("❌ Неверный формат! Попробуйте снова:")
        return AWAITING_PROMO_VALUE  # Остаемся в том же состоянии

async def process_promo_uses(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # УБРАТЬ ВСЕ ПРОВЕРКИ СЕССИИ
    # Просто обрабатываем
    
    try:
        max_uses = int(update.message.text.strip())
        if max_uses <= 0:
            raise ValueError
        context.user_data['promo_max_uses'] = max_uses
        
        keyboard = [
            [InlineKeyboardButton("⏰ Установить срок", callback_data="promo_set_expire")],
            [InlineKeyboardButton("♾ Без срока", callback_data="promo_no_expire")]
        ]
        
        await update.message.reply_text(
            "Установить срок действия промокода?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return AWAITING_PROMO_EXPIRE
        
    except ValueError:
        await update.message.reply_text("❌ Введите положительное число!")
        return AWAITING_PROMO_USES

async def process_promo_expire(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ЕСЛИ ЭТО CALLBACK ОТ КНОПКИ
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        
        if query.data == 'promo_no_expire':
            context.user_data['promo_expires'] = None
            await query.edit_message_text(
                "Введите минимальный уровень для активации (0 для любого уровня):"
            )
            return AWAITING_PROMO_EXPIRE
            
        elif query.data == 'promo_set_expire':
            await query.edit_message_text(
                "Введите дату окончания в формате ДД.ММ.ГГГГ (например: 31.12.2024):"
            )
            return AWAITING_PROMO_EXPIRE
    
    # ЕСЛИ ЭТО СООБЩЕНИЕ (ввод даты или уровня)
    elif update.message:
        text = update.message.text.strip()
        
        # Проверяем - это дата или уровень?
        if '.' in text and text.count('.') == 2:  # Это дата ДД.ММ.ГГГГ
            try:
                expire_date = datetime.strptime(text, "%d.%m.%Y").date()
                context.user_data['promo_expires'] = expire_date.strftime("%Y-%m-%d")
                await update.message.reply_text(
                    "Введите минимальный уровень для активации (0 для любого уровня):"
                )
                return AWAITING_PROMO_EXPIRE
            except ValueError:
                await update.message.reply_text("❌ Неверный формат даты! Используйте ДД.ММ.ГГГГ:")
                return AWAITING_PROMO_EXPIRE
        
        else:  # Это уровень
            try:
                min_level = int(text)
                if min_level < 0:
                    await update.message.reply_text("❌ Уровень не может быть отрицательным! Введите 0 или больше:")
                    return AWAITING_PROMO_EXPIRE
                    
                # СОЗДАЕМ ПРОМОКОД
                promo_name = context.user_data.get('promo_name')
                if not promo_name:
                    await update.message.reply_text("❌ Ошибка: не найдено название промокода")
                    return await show_admin_panel(update, context)
                
                # Создаем промокод
                PROMOCODES[promo_name] = {
                    'reward': context.user_data.get('promo_reward', {}),
                    'max_uses': context.user_data.get('promo_max_uses', 1),
                    'used': 0,
                    'expires': context.user_data.get('promo_expires'),
                    'min_level': min_level,
                    'created_by': update.effective_user.username,
                    'created_at': datetime.now().isoformat()
                }
                
                save_data()
                
                # Формируем сообщение
                reward = context.user_data.get('promo_reward', {})
                money = reward.get('money', 0)
                coins = reward.get('coins', 0)
                item = reward.get('item', '')
                
                message = f"✅ Промокод <b>{promo_name}</b> создан!\n\n"
                if money > 0:
                    message += f"💰 Деньги: {money:,} ₽\n"
                if coins > 0:
                    message += f"🪙 Койны: {coins}\n"
                if item:
                    message += f"🎁 Предмет: {item}\n"
                
                message += f"📊 Лимит: {context.user_data.get('promo_max_uses', 1)} использований\n"
                message += f"📈 Мин. уровень: {min_level}\n"
                message += f"📅 Срок: {context.user_data.get('promo_expires', 'Без срока')}\n"
                message += f"👤 Создал: @{update.effective_user.username}"
                
                await update.message.reply_text(message, parse_mode='HTML')
                
                # Очищаем данные
                keys_to_remove = ['promo_name', 'promo_reward', 'promo_max_uses', 'promo_expires', 'promo_type']
                for key in keys_to_remove:
                    if key in context.user_data:
                        del context.user_data[key]
                
                # Возвращаемся в админ-панель
                return await show_admin_panel(update, context)
                
            except ValueError:
                await update.message.reply_text("❌ Неверный уровень! Введите число:")
                return AWAITING_PROMO_EXPIRE
    
    # Если что-то пошло не так
    return await show_admin_panel(update, context)
    # В конце функции process_promo_expire, после создания промокода:
    return ConversationHandler.END  # Выходим из ConversationHandler

# ==================== УПРАВЛЕНИЕ АДМИНИСТРАТОРАМИ ====================

async def process_admin_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ввода username администратора"""
    username_input = update.message.text.strip()
    
    if not username_input:
        await update.message.reply_text("❌ Введите username пользователя!")
        return AWAITING_ADMIN_USERNAME
    
    # Убираем @ если есть
    username = username_input.lstrip('@')
    
    if not username:
        await update.message.reply_text("❌ Введите корректный username!")
        return AWAITING_ADMIN_USERNAME
    
    action = context.user_data.get('admin_action')
    
    if action == 'add_admin':
        # Для добавления админа - просто сохраняем username
        context.user_data['target_admin'] = username
        
        keyboard = [
            [InlineKeyboardButton("👑 Владелец (уровень 3)", callback_data="admin_level_3")],
            [InlineKeyboardButton("🛡 Администратор (уровень 2)", callback_data="admin_level_2")],
            [InlineKeyboardButton("👮 Модератор (уровень 1)", callback_data="admin_level_1")]
        ]
        
        await update.message.reply_text(
            f"👤 Пользователь: @{username}\n\n"
            "Выберите уровень доступа:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return AWAITING_ADMIN_LEVEL
        
    elif action == 'edit_admin':
        if username not in ADMINS:
            await update.message.reply_text("❌ Этот пользователь не является администратором!")
            return await show_admin_panel(update, context)
        
        current_level = ADMINS[username].get('level', 1)
        keyboard = [
            [InlineKeyboardButton("👑 Владелец (уровень 3)", callback_data="admin_level_3")],
            [InlineKeyboardButton("🛡 Администратор (уровень 2)", callback_data="admin_level_2")],
            [InlineKeyboardButton("👮 Модератор (уровень 1)", callback_data="admin_level_1")],
            [InlineKeyboardButton("❌ Снять права", callback_data="admin_level_0")]
        ]
        
        await update.message.reply_text(
            f"👤 Администратор: @{username}\n"
            f"📊 Текущий уровень: {current_level}\n\n"
            "Выберите новый уровень:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return AWAITING_ADMIN_LEVEL
        
    elif action == 'remove_admin':
        if username not in ADMINS:
            await update.message.reply_text("❌ Этот пользователь не является администратором!")
            return await show_admin_panel(update, context)
        
        # Нельзя удалить себя
        if username == update.effective_user.username:
            await update.message.reply_text("❌ Вы не можете удалить сами себя!")
            return await show_admin_panel(update, context)
        
        # Подтверждение удаления
        keyboard = [
            [InlineKeyboardButton("✅ Да, удалить", callback_data="confirm_remove")],
            [InlineKeyboardButton("❌ Нет, оставить", callback_data="cancel_remove")]
        ]
        
        await update.message.reply_text(
            f"⚠️ Вы уверены, что хотите удалить администратора @{username}?\n"
            f"Его уровень: {ADMINS[username].get('level', 1)}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return AWAITING_ADMIN_LEVEL
        
    elif action == 'change_password':
        if username not in ADMINS:
            await update.message.reply_text("❌ Этот пользователь не является администратором!")
            return await show_admin_panel(update, context)
        
        # Запрашиваем пароль
        context.user_data['target_admin'] = username
        await update.message.reply_text(
            f"👤 Администратор: @{username}\n\n"
            "🔐 Введите новый пароль (минимум 6 символов):"
        )
        return AWAITING_ADMIN_PASSWORD
    
    return await show_admin_panel(update, context)

async def process_admin_level(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора уровня администратора"""
    # Если это сообщение (не callback), возвращаем ошибку
    if not update.callback_query:
        await update.message.reply_text("❌ Используйте кнопки для выбора уровня!")
        return AWAITING_ADMIN_LEVEL
    
    query = update.callback_query
    await query.answer()
    
    # Обработка отмены удаления
    if query.data == 'cancel_remove':
        await query.edit_message_text("❌ Удаление отменено.")
        return await show_admin_panel(update, context)
    
    elif query.data == 'confirm_remove':
        username = context.user_data.get('target_admin')
        if username and username in ADMINS:
            del ADMINS[username]
            save_data()
            await query.edit_message_text(f"✅ Администратор @{username} удален!")
        else:
            await query.edit_message_text("❌ Администратор не найден!")
        
        # Очищаем данные
        context.user_data.pop('target_admin', None)
        context.user_data.pop('admin_action', None)
        return await show_admin_panel(update, context)
    
    # Определяем уровень
    level = 0
    if query.data == 'admin_level_0':
        level = 0
    else:
        try:
            level = int(query.data.split('_')[2])
        except (IndexError, ValueError):
            await query.edit_message_text("❌ Ошибка выбора уровня!")
            return await show_admin_panel(update, context)
    
    username = context.user_data.get('target_admin')
    action = context.user_data.get('admin_action')
    
    if not username:
        await query.edit_message_text("❌ Ошибка: username не найден!")
        return await show_admin_panel(update, context)
    
    if action == 'add_admin':
        # Для добавления админа СОХРАНЯЕМ ДАННЫЕ ДЛЯ СОЗДАНИЯ
        context.user_data['pending_admin'] = {  # ВОТ ЭТО ВАЖНО!
            'username': username,
            'level': level
        }
        
        level_names = {3: "👑 Владелец", 2: "🛡 Администратор", 1: "👮 Модератор"}
        
        await query.edit_message_text(
            f"👤 Пользователь: @{username}\n"
            f"🛡 Уровень: {level_names.get(level, 'Неизвестно')}\n\n"
            "🔐 Введите пароль для администратора (минимум 6 символов):"
        )
        return AWAITING_ADMIN_PASSWORD  # ВАЖНО: возвращаем это состояние!
        
    elif action == 'edit_admin':
        if username not in ADMINS:
            await query.answer("❌ Администратор не найден!", show_alert=True)
            return await show_admin_panel(update, context)
        
        if level == 0:  # Снятие прав
            del ADMINS[username]
            save_data()
            await query.edit_message_text(f"✅ Администратор @{username} лишен прав!")
        else:
            old_level = ADMINS[username].get('level', 1)
            ADMINS[username]['level'] = level
            save_data()
            
            level_names = {3: "Владелец", 2: "Администратор", 1: "Модератор"}
            await query.edit_message_text(
                f"✅ Уровень администратора изменен!\n\n"
                f"👤 Администратор: @{username}\n"
                f"📊 Было: {level_names.get(old_level, 'Неизвестно')}\n"
                f"📈 Стало: {level_names.get(level, 'Неизвестно')}"
            )
        
        # Очищаем временные данные
        context.user_data.pop('target_admin', None)
        context.user_data.pop('admin_action', None)
        
        return await show_admin_panel(update, context)
    
    # Если действие не определено
    await query.edit_message_text("❌ Неизвестное действие!")
    return await show_admin_panel(update, context)
    
    

async def gang_create_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    user = get_user_data(user_id)
    gang_name = update.message.text.strip()
    
    if len(gang_name) < 3 or len(gang_name) > 20:
        await update.message.reply_text("❌ Название должно быть 3-20 символов!")
        return GANG_CREATE
    
    # Проверяем уникальность
    for gang in gangs.values():
        if gang['name'].lower() == gang_name.lower():
            await update.message.reply_text("❌ Такое название уже занято!")
            return GANG_CREATE
    
    # Снимаем деньги
    user['balance'] -= 100_000_000_000
    
    # Создаем банду
    gang_id = secrets.token_hex(8)
    gangs[gang_id] = {
        'id': gang_id,
        'name': gang_name,
        'leader_id': user_id,
        'leader_name': user.get('username', user_id),
        'members': {
            user_id: {
                'role': 'leader',
                'joined': datetime.now().isoformat(),
                'donations': 0,
                'trophies': 0
            }
        },
        'bank': 0,
        'trophies': 1000,  # Стартовые кубки
        'level': 1,
        'wins': 0,
        'losses': 0,
        'description': "Новая банда",
        'join_type': 'invite',  # invite, request, open
        'created': datetime.now().isoformat(),
        'last_war': None
    }
    
    await update.message.reply_text(
        f"✅ Банда '{gang_name}' создана!\n"
        f"💰 Списано: 100,000,000,000 ₽\n"
        f"💳 Ваш баланс: {user['balance']:,} ₽\n"
        f"🏆 Стартовые кубки: 1000\n"
        f"👥 Максимум участников: 10"
    )
    
    save_data()
    return await gang_menu(update, context)

async def gang_invite_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    
    # Находим банду пользователя
    user_gang = None
    for gang in gangs.values():
        if user_id in gang['members']:
            user_gang = gang
            break
    
    if not user_gang or gang['members'][user_id]['role'] not in ['leader', 'co-leader']:
        await query.answer("❌ Нет прав для приглашения!", show_alert=True)
        return GANG_MENU
    
    await query.edit_message_text(
        f"📨 Приглашение в банду '{user_gang['name']}'\n\n"
        "Введите @username или ID пользователя:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="gang_back")]])
    )
    return GANG_INVITE

async def gang_invite_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    target_input = update.message.text.strip().lstrip('@')
    
    # Находим банду приглашающего
    user_gang = None
    for gang in gangs.values():
        if user_id in gang['members']:
            user_gang = gang
            break
    
    if not user_gang:
        await update.message.reply_text("❌ Ошибка: банда не найдена")
        return await gang_menu(update, context)
    
    # Ищем пользователя для приглашения
    target_user = None
    target_username = None
    
    for uid, u_data in user_data.items():
        if str(u_data.get('username', '')).lower() == target_input.lower() or str(uid) == target_input:
            target_user = str(uid)
            target_username = u_data.get('username', str(uid))
            break
    
    if not target_user:
        await update.message.reply_text("❌ Пользователь не найден!")
        return GANG_INVITE
    
    # Проверяем, не в банде ли уже
    for gang in gangs.values():
        if target_user in gang['members']:
            await update.message.reply_text("❌ Этот пользователь уже в банде!")
            return GANG_INVITE
    
    # Создаем приглашение
    invite_id = secrets.token_hex(6)
    gang_invites[invite_id] = {
        'gang_id': user_gang['id'],
        'gang_name': user_gang['name'],
        'inviter_id': user_id,
        'inviter_name': user_data.get(user_id, {}).get('username', user_id),
        'target_id': target_user,
        'created': datetime.now().isoformat()
    }
    
    await update.message.reply_text(
        f"✅ Приглашение отправлено @{target_username}!"
    )
    
    # Уведомляем получателя
    try:
        await context.bot.send_message(
            chat_id=int(target_user),
            text=f"📥 Вас пригласили в банду '{user_gang['name']}'!\n\n"
                 f"Используйте /gang для просмотра приглашений."
        )
    except:
        pass
    
    save_data()
    return await gang_menu(update, context)

async def gang_show_invites(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    
    # Ищем приглашения для пользователя
    user_invites = []
    for invite_id, invite in gang_invites.items():
        if invite['target_id'] == user_id:
            user_invites.append((invite_id, invite))
    
    if not user_invites:
        await query.edit_message_text(
            "📥 У вас нет приглашений в банды.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="gang_back")]])
        )
        return GANG_MENU
    
    text = "📥 Ваши приглашения:\n\n"
    for i, (invite_id, invite) in enumerate(user_invites[:10], 1):
        text += (
            f"{i}. Банда: {invite['gang_name']}\n"
            f"   Пригласил: @{invite['inviter_name']}\n"
            f"   ID: <code>{invite_id}</code>\n\n"
        )
    
    keyboard = [
        [InlineKeyboardButton("✅ Принять", callback_data="gang_accept_invite")],
        [InlineKeyboardButton("❌ Отклонить", callback_data="gang_reject_invite")],
        [InlineKeyboardButton("🔙 Назад", callback_data="gang_back")]
    ]
    
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )
    return GANG_MENU

async def gang_war_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    
    # Находим банду пользователя
    user_gang = None
    user_role = None
    for gang in gangs.values():
        if user_id in gang['members']:
            user_gang = gang
            user_role = gang['members'][user_id]['role']
            break
    
    if not user_gang:
        await query.answer("❌ Вы не в банде!", show_alert=True)
        return GANG_MENU
    
    if user_role not in ['leader', 'co-leader']:
        await query.answer("❌ Только лидер и замы могут атаковать!", show_alert=True)
        return GANG_MENU
    
    # Проверяем кулдаун (24 часа)
    if user_gang.get('last_war'):
        last_war = datetime.fromisoformat(user_gang['last_war'])
        if (datetime.now() - last_war).total_seconds() < 86400:
            await query.answer("❌ Можно атаковать раз в 24 часа!", show_alert=True)
            return GANG_MENU
    
    # Ищем банды для атаки (разница в кубках до 300)
    available_gangs = []
    for gang_id, gang in gangs.items():
        if gang_id != user_gang['id']:
            if abs(gang['trophies'] - user_gang['trophies']) <= 300:
                available_gangs.append(gang)
    
    if not available_gangs:
        await query.answer("❌ Нет подходящих банд для атаки!", show_alert=True)
        return GANG_MENU
    
    keyboard = []
    for gang in available_gangs[:10]:
        keyboard.append([InlineKeyboardButton(
            f"{gang['name']} 🏆{gang['trophies']} 👥{len(gang['members'])}",
            callback_data=f"gang_war_target_{gang['id']}"
        )])
    
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="gang_back")])
    
    await query.edit_message_text(
        f"⚔️ Выберите банду для атаки:\n\n"
        f"Ваша банда: {user_gang['name']} 🏆{user_gang['trophies']}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return GANG_WAR_TARGET

async def gang_war_target(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if not query.data.startswith("gang_war_target_"):
        return GANG_MENU
    
    target_gang_id = query.data.split('_')[3]
    user_id = str(query.from_user.id)
    
    # Находим обе банды
    attacker_gang = None
    target_gang = gangs.get(target_gang_id)
    
    for gang in gangs.values():
        if user_id in gang['members']:
            attacker_gang = gang
            break
    
    if not attacker_gang or not target_gang:
        await query.answer("❌ Ошибка!", show_alert=True)
        return GANG_MENU
    
    # Подтверждение
    keyboard = [
        [InlineKeyboardButton("✅ Начать атаку", callback_data=f"gang_war_start_{target_gang_id}")],
        [InlineKeyboardButton("🔙 Отмена", callback_data="gang_war")]
    ]
    
    await query.edit_message_text(
        f"⚔️ Подтверждение атаки\n\n"
        f"Нападающая банда: {attacker_gang['name']}\n"
        f"🏆 Кубки: {attacker_gang['trophies']}\n"
        f"👥 Участников: {len(attacker_gang['members'])}\n\n"
        f"Защищающаяся банда: {target_gang['name']}\n"
        f"🏆 Кубки: {target_gang['trophies']}\n"
        f"👥 Участников: {len(target_gang['members'])}\n\n"
        f"При победе: +15-30 кубков\n"
        f"При поражении: -15-30 кубков",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return GANG_WAR_CONFIRM

async def gang_war_execute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if not query.data.startswith("gang_war_start_"):
        return GANG_MENU
    
    target_gang_id = query.data.split('_')[3]
    user_id = str(query.from_user.id)
    
    # Находим обе банды
    attacker_gang = None
    target_gang = gangs.get(target_gang_id)
    
    for gang in gangs.values():
        if user_id in gang['members']:
            attacker_gang = gang
            break
    
    if not attacker_gang or not target_gang:
        await query.answer("❌ Ошибка!", show_alert=True)
        return GANG_MENU
    
    # Рассчитываем силы
    attacker_power = (
        attacker_gang['trophies'] * 0.5 +
        attacker_gang['level'] * 100 +
        len(attacker_gang['members']) * 10 +
        random.randint(-50, 50)
    )
    
    target_power = (
        target_gang['trophies'] * 0.5 +
        target_gang['level'] * 100 +
        len(target_gang['members']) * 10 +
        random.randint(-50, 50)
    )
    
    # Определяем победителя
    trophy_change = random.randint(15, 30)
    
    if attacker_power > target_power:
        # Атакующий победил
        attacker_gang['trophies'] += trophy_change
        target_gang['trophies'] -= trophy_change
        if target_gang['trophies'] < 0:
            target_gang['trophies'] = 0
        
        attacker_gang['wins'] += 1
        target_gang['losses'] += 1
        
        # Добыча (5% от казны проигравшего)
        loot = int(target_gang['bank'] * 0.05)
        target_gang['bank'] -= loot
        attacker_gang['bank'] += loot
        
        result_text = (
            f"🎉 Победа! Банда '{attacker_gang['name']}' победила '{target_gang['name']}'\n\n"
            f"🏆 +{trophy_change} кубков\n"
            f"💰 +{loot:,} ₽ добычи\n\n"
            f"Новые кубки: {attacker_gang['trophies']}"
        )
    else:
        # Защищающийся победил
        target_gang['trophies'] += trophy_change
        attacker_gang['trophies'] -= trophy_change
        if attacker_gang['trophies'] < 0:
            attacker_gang['trophies'] = 0
        
        target_gang['wins'] += 1
        attacker_gang['losses'] += 1
        
        result_text = (
            f"💀 Поражение! Банда '{target_gang['name']}' победила '{attacker_gang['name']}'\n\n"
            f"🏆 -{trophy_change} кубков\n\n"
            f"Новые кубки: {attacker_gang['trophies']}"
        )
    
    # Обновляем время последней войны
    attacker_gang['last_war'] = datetime.now().isoformat()
    target_gang['last_war'] = datetime.now().isoformat()
    
    # Уведомляем участников
    for member_id in attacker_gang['members']:
        try:
            await context.bot.send_message(
                chat_id=int(member_id),
                text=f"⚔️ Результат войны с '{target_gang['name']}':\n\n{result_text}"
            )
        except:
            pass
    
    for member_id in target_gang['members']:
        try:
            opposite_result = "победили" if attacker_power <= target_power else "проиграли"
            await context.bot.send_message(
                chat_id=int(member_id),
                text=f"⚔️ Ваша банда {opposite_result} в войне с '{attacker_gang['name']}'!"
            )
        except:
            pass
    
    await query.edit_message_text(result_text)
    
    save_data()
    return await gang_menu(update, context)

async def gang_show_top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    # Сортируем банды по кубкам
    sorted_gangs = sorted(
        gangs.values(),
        key=lambda x: x['trophies'],
        reverse=True
    )
    
    text = "🏆 Топ банд по кубкам:\n\n"
    for i, gang in enumerate(sorted_gangs[:20], 1):
        win_rate = gang['wins'] / (gang['wins'] + gang['losses']) * 100 if (gang['wins'] + gang['losses']) > 0 else 0
        text += (
            f"{i}. {gang['name']}\n"
            f"   🏆 {gang['trophies']} | 👥 {len(gang['members'])} | ⚔️ {gang['wins']}-{gang['losses']} ({win_rate:.1f}%)\n"
            f"   👑 @{gang['leader_name']}\n\n"
        )
    
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="gang_back")]]
    
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return GANG_MENU

async def gang_show_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    
    # Находим банду пользователя
    user_gang = None
    for gang in gangs.values():
        if user_id in gang['members']:
            user_gang = gang
            break
    
    if not user_gang:
        await query.answer("❌ Вы не в банде!", show_alert=True)
        return GANG_MENU
    
    text = f"👥 Участники банды '{user_gang['name']}':\n\n"
    
    # Сортируем по роли: лидер, замы, участники
    leader_id = user_gang['leader_id']
    co_leaders = []
    members = []
    
    for member_id, member_data in user_gang['members'].items():
        if member_id == leader_id:
            text += f"👑 Лидер: @{user_data.get(member_id, {}).get('username', member_id)}\n"
        elif member_data['role'] == 'co-leader':
            co_leaders.append(member_id)
        else:
            members.append(member_id)
    
    if co_leaders:
        text += "\n👥 Заместители:\n"
        for member_id in co_leaders:
            text += f"  • @{user_data.get(member_id, {}).get('username', member_id)}\n"
    
    if members:
        text += "\n👤 Участники:\n"
        for member_id in members:
            member_data = user_gang['members'][member_id]
            donations = member_data.get('donations', 0)
            text += f"  • @{user_data.get(member_id, {}).get('username', member_id)} (💎 {donations:,})\n"
    
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="gang_back")]]
    
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return GANG_MENU

async def gang_donate_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    
    # Находим банду пользователя
    user_gang = None
    for gang in gangs.values():
        if user_id in gang['members']:
            user_gang = gang
            break
    
    if not user_gang:
        await query.answer("❌ Вы не в банде!", show_alert=True)
        return GANG_MENU
    
    user = get_user_data(user_id)
    
    await query.edit_message_text(
        f"🎁 Взнос в казну банды '{user_gang['name']}'\n\n"
        f"💰 Текущая казна: {user_gang['bank']:,} ₽\n"
        f"💳 Ваш баланс: {user['balance']:,} ₽\n\n"
        f"Введите сумму для взноса:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="gang_back")]])
    )
    return GANG_DONATE

async def gang_donate_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    amount_str = update.message.text
    
    try:
        amount = parse_bet_amount(amount_str)
        if not amount or amount <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Неверная сумма!")
        return GANG_DONATE
    
    # Находим банду пользователя
    user_gang = None
    for gang in gangs.values():
        if user_id in gang['members']:
            user_gang = gang
            break
    
    if not user_gang:
        await update.message.reply_text("❌ Ошибка: банда не найдена")
        return await gang_menu(update, context)
    
    user = get_user_data(user_id)
    
    if amount > user['balance']:
        await update.message.reply_text("❌ Недостаточно средств!")
        return GANG_DONATE
    
    # Делаем взнос
    user['balance'] -= amount
    user_gang['bank'] += amount
    
    # Обновляем статистику донора
    if 'donations' not in user_gang['members'][user_id]:
        user_gang['members'][user_id]['donations'] = 0
    user_gang['members'][user_id]['donations'] += amount
    
    await update.message.reply_text(
        f"✅ Вы внесли {amount:,} ₽ в казну банды!\n\n"
        f"💰 Новая казна: {user_gang['bank']:,} ₽\n"
        f"💳 Ваш баланс: {user['balance']:,} ₽\n"
        f"💎 Всего внесено: {user_gang['members'][user_id]['donations']:,} ₽"
    )
    
    save_data()
    return await gang_menu(update, context)

async def gang_leave_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("✅ Да, покинуть банду", callback_data="gang_leave_confirm")],
        [InlineKeyboardButton("❌ Нет, остаться", callback_data="gang_back")]
    ]
    
    await query.edit_message_text(
        "⚠️ Вы уверены, что хотите покинуть банду?\n\n"
        "Вы потеряете доступ ко всем бандитским функциям.",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return GANG_MENU

async def gang_leave_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    
    # Находим банду пользователя
    user_gang = None
    for gang in gangs.values():
        if user_id in gang['members']:
            user_gang = gang
            break
    
    if not user_gang:
        await query.answer("❌ Вы не в банде!", show_alert=True)
        return GANG_MENU
    
    # Если лидер пытается уйти
    if user_id == user_gang['leader_id']:
        await query.answer("❌ Лидер не может покинуть банду! Передайте лидерство или распустите банду.", show_alert=True)
        return GANG_MENU
    
    # Удаляем из банды
    del user_gang['members'][user_id]
    
    await query.edit_message_text(
        "✅ Вы покинули банду!"
    )
    
    save_data()
    return await gang_menu(update, context)

async def gang_disband_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("✅ Да, распустить банду", callback_data="gang_disband_confirm")],
        [InlineKeyboardButton("❌ Нет, оставить", callback_data="gang_back")]
    ]
    
    await query.edit_message_text(
        "⚠️ ВЫ УВЕРЕНЫ? Роспуск банды:\n\n"
        "• Все участники будут исключены\n"
        "• Казна будет распределена между участниками\n"
        "• Все достижения будут потеряны\n"
        "• Отменить действие НЕВОЗМОЖНО!",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return GANG_MENU

async def gang_disband_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    
    # Находим банду пользователя
    user_gang = None
    for gang in gangs.values():
        if user_id in gang['members'] and user_id == gang['leader_id']:
            user_gang = gang
            break
    
    if not user_gang:
        await query.answer("❌ Только лидер может распустить банду!", show_alert=True)
        return GANG_MENU
    
    gang_name = user_gang['name']
    member_count = len(user_gang['members'])
    bank_total = user_gang['bank']
    
    # Распределяем казну между участниками
    if bank_total > 0 and member_count > 0:
        share = bank_total // member_count
        for member_id in user_gang['members']:
            if member_id in user_data:
                user_data[member_id]['balance'] += share
    
    # Удаляем банду
    del gangs[user_gang['id']]
    
    await query.edit_message_text(
        f"💥 Банда '{gang_name}' распущена!\n\n"
        f"👥 Участников: {member_count}\n"
        f"💰 Распределено из казны: {bank_total:,} ₽"
    )
    
    save_data()
    return await gang_menu(update, context)

# Обработчик для всех кнопок банд
async def gang_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "gang_create":
        return await gang_create_start(update, context)
    elif query.data == "gang_search":
        return await gang_search(update, context)
    elif query.data == "gang_invites_list":
        return await gang_show_invites(update, context)
    elif query.data == "gang_top":
        return await gang_show_top(update, context)
    elif query.data == "gang_members":
        return await gang_show_members(update, context)
    elif query.data == "gang_stats":
        return await gang_show_stats(update, context)
    elif query.data == "gang_manage":
        return await gang_show_manage(update, context)
    elif query.data == "gang_invite":
        return await gang_invite_start(update, context)
    elif query.data == "gang_war":
        return await gang_war_start(update, context)
    elif query.data == "gang_donate":
        return await gang_donate_start(update, context)
    elif query.data == "gang_disband":
        return await gang_disband_start(update, context)
    elif query.data == "gang_leave":
        return await gang_leave_start(update, context)
    elif query.data == "gang_back":
        return await gang_menu(update, context)
    elif query.data.startswith("gang_war_target_"):
        return await gang_war_target(update, context)
    elif query.data.startswith("gang_war_start_"):
        return await gang_war_execute(update, context)
    elif query.data == "gang_accept_invite":
        return await gang_accept_invite_start(update, context)
    elif query.data == "gang_reject_invite":
        return await gang_reject_invite_start(update, context)
    elif query.data == "gang_leave_confirm":
        return await gang_leave_confirm(update, context)
    elif query.data == "gang_disband_confirm":
        return await gang_disband_confirm(update, context)
    
    return GANG_MENU
    
async def finish_work_callback(context: ContextTypes.DEFAULT_TYPE):
    # Получаем данные из job.data вместо job.context
    job_data = context.job.data
    
    await finish_work(
        context=context,
        job_type=job_data['job_type'],
        user_id=job_data['user_id'],
        chat_id=job_data['chat_id'],
        message_id=job_data['message_id']
    )

async def finish_work(context: ContextTypes.DEFAULT_TYPE, job_type: str, user_id: int, chat_id: int, message_id: int):
    try:
        user = get_user_data(user_id)
        job_data = user['jobs'][job_type]
        level = job_data['level']
        
        # Зарплаты по уровням
        salaries = {
            'taxi': [20000, 40000, 80000],
            'accountant': [
                random.randint(1_000_000, 4_000_000),
                random.randint(2_000_000, 6_000_000),
                random.randint(4_000_000, 10_000_000)
            ],
            'builder': [
                random.randint(50_000, 150_000),
                random.randint(100_000, 250_000),
                random.randint(200_000, 500_000)
            ],
            'businessman': [
                random.randint(500_000, 2_000_000),
                random.randint(1_000_000, 3_000_000),
                random.randint(2_000_000, 5_000_000)
            ]
        }
        
        # Начисление зарплаты
        salary = salaries[job_type][level-1]
        user['balance'] += salary
        
        # Обновление статистики
        job_data['completed'] += 1
        job_data['last_work'] = datetime.now().isoformat()
        
        # Проверка повышения уровня
        level_up = False
        if level < 3:
            next_level = {1: 100, 2: 250}[level]
            if job_data['completed'] >= next_level:
                job_data['level'] += 1
                level_up = True
        
        # Формирование сообщения
        job_names = {
            'taxi': "🚕 Таксист",
            'accountant': "📊 Бухгалтер",
            'builder': "👷 Строитель",
            'businessman': "👨‍💼 Бизнесмен"
        }
        
        message_text = (
            f"✅ Работа завершена!\n\n"
            f"{job_names[job_type]} - Уровень {level}\n"
            f"💰 Вы заработали: {salary:,} ₽\n"
            f"📊 Всего выполнено: {job_data['completed']} работ"
        )
        
        if level_up:
            message_text += f"\n\n🎉 Поздравляем! Вы достигли {level+1} уровня!"
        
        # Создание клавиатуры
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Снова работать", callback_data=f"start_work_{job_type}")],
            [InlineKeyboardButton("🔙 Назад", callback_data=f"work_{job_type}")]
        ])
        
        try:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=message_text,
                reply_markup=keyboard
            )
        except Exception as e:
            logging.error(f"Ошибка редактирования: {str(e)}")
            await context.bot.send_message(
                chat_id=chat_id,
                text=message_text,
                reply_markup=keyboard
            )
        
        save_data()
        
    except Exception as e:
        logging.error(f"Критическая ошибка: {str(e)}")
        await context.bot.send_message(
            chat_id=chat_id,
            text="⚠️ Произошла техническая ошибка. Администратор уже уведомлен."
        )

async def finish_work(context: ContextTypes.DEFAULT_TYPE, job_type: str, user_id: int, chat_id: int, message_id: int):
    try:
        user = get_user_data(user_id)
        job_data = user['jobs'][job_type]
        level = job_data['level']
        
        # Зарплаты по уровням
        salaries = {
            'taxi': [20000, 40000, 80000],
            'accountant': [
                random.randint(1_000_000, 4_000_000),
                random.randint(2_000_000, 6_000_000),
                random.randint(4_000_000, 10_000_000)
            ],
            'builder': [
                random.randint(50_000, 150_000),
                random.randint(100_000, 250_000),
                random.randint(200_000, 500_000)
            ],
            'businessman': [
                random.randint(500_000, 2_000_000),
                random.randint(1_000_000, 3_000_000),
                random.randint(2_000_000, 5_000_000)
            ]
        }
        
        # Начисление зарплаты
        salary = salaries[job_type][level-1]
        user['balance'] += salary
        
        # Обновление статистики
        job_data['completed'] += 1
        job_data['last_work'] = datetime.now().isoformat()
        
        # Проверка повышения уровня
        level_up = False
        if level < 3:
            next_level = {1: 100, 2: 250}[level]
            if job_data['completed'] >= next_level:
                job_data['level'] += 1
                level_up = True
        
        # Формирование сообщения
        job_names = {
            'taxi': "🚕 Таксист",
            'accountant': "📊 Бухгалтер",
            'builder': "👷 Строитель",
            'businessman': "👨‍💼 Бизнесмен"
        }
        
        message_text = (
            f"✅ Работа завершена!\n\n"
            f"{job_names[job_type]} - Уровень {level}\n"
            f"💰 Вы заработали: {salary:,} ₽\n"
            f"📊 Всего выполнено: {job_data['completed']} работ"
        )
        
        if level_up:
            message_text += f"\n\n🎉 Поздравляем! Вы достигли {level+1} уровня!"
        
        # Создание клавиатуры
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Снова работать", callback_data=f"start_work_{job_type}")],
            [InlineKeyboardButton("🔙 Назад", callback_data=f"work_{job_type}")]
        ])
        
        try:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=message_text,
                reply_markup=keyboard
            )
        except Exception as e:
            logging.error(f"Ошибка редактирования: {str(e)}")
            await context.bot.send_message(
                chat_id=chat_id,
                text=message_text,
                reply_markup=keyboard
            )
        
        save_data()
        
    except Exception as e:
        logging.error(f"Критическая ошибка: {str(e)}")
        await context.bot.send_message(
            chat_id=chat_id,
            text="⚠️ Произошла техническая ошибка. Администратор уже уведомлен."
        )
            
async def show_job_info(update: Update, context: ContextTypes.DEFAULT_TYPE, job_type: str):
    """Показать информацию о работе"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    user = get_user_data(user_id)
    
    # Инициализация данных, если их нет
    if 'jobs' not in user:
        user['jobs'] = {}
    if job_type not in user['jobs']:
        user['jobs'][job_type] = {
            'level': 1,
            'completed': 0,
            'last_work': None,
            'achievements': []
        }
    
    job_data = user['jobs'][job_type]
    level = job_data['level']
    completed = job_data['completed']
    
    # Зарплаты
    salaries = {
        'taxi': [20000, 40000, 80000],
        'accountant': [1000000, 2000000, 4000000],
        'builder': [50000, 100000, 200000],
        'businessman': [500000, 1000000, 2000000]
    }
    
    # Кулдауны
    cooldowns = {
        'taxi': [60, 45, 30],
        'accountant': [3600, 2700, 1800],
        'builder': [1800, 1200, 900],
        'businessman': [3600, 2700, 1800]
    }
    
    # Названия
    job_names = {
        'taxi': "🚕 ТАКСИСТ",
        'accountant': "📊 БУХГАЛТЕР",
        'builder': "👷 СТРОИТЕЛЬ",
        'businessman': "👨‍💼 БИЗНЕСМЕН"
    }
    
    # Проверка кулдауна
    can_work = True
    remaining = 0
    
    if job_data.get('last_work'):
        last_work = datetime.fromisoformat(job_data['last_work'])
        cooldown = cooldowns[job_type][level-1]
        time_passed = (datetime.now() - last_work).total_seconds()
        
        if time_passed < cooldown:
            can_work = False
            remaining = cooldown - time_passed
    
    # Формируем текст
    text = (
        f"{job_names[job_type]} - Уровень {level}\n\n"
        f"📊 Выполнено работ: {completed}\n"
        f"💰 Зарплата: {salaries[job_type][level-1]:,} ₽"
    )
    
    if level < 3:
        next_level = {1: 100, 2: 250}[level]
        text += f"\n\n🔜 До следующего уровня: {next_level - completed} работ"
    
    if not can_work:
        mins, secs = divmod(int(remaining), 60)
        text += f"\n\n⏳ До следующей работы: {mins} мин {secs} сек"
    
    # Клавиатура
    keyboard = []
    if can_work:
        keyboard.append([InlineKeyboardButton("🔄 НАЧАТЬ РАБОТУ", callback_data=f"start_work_{job_type}")])
    keyboard.append([InlineKeyboardButton("🔙 НАЗАД", callback_data="work_back")])
    
    await query.edit_message_text(
        text=text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
    return WORK_MENU

async def start_work_job(update: Update, context: ContextTypes.DEFAULT_TYPE, job_type: str):
    """Начать работу"""
    query = update.callback_query
    
    user_id = query.from_user.id
    user = get_user_data(user_id)
    job_data = user['jobs'][job_type]
    level = job_data['level']
    
    # Кулдауны
    cooldowns = {
        'taxi': [60, 45, 30],
        'accountant': [3600, 2700, 1800],
        'builder': [1800, 1200, 900],
        'businessman': [3600, 2700, 1800]
    }
    
    # Проверка кулдауна
    if job_data.get('last_work'):
        last_work = datetime.fromisoformat(job_data['last_work'])
        cooldown = cooldowns[job_type][level-1]
        if (datetime.now() - last_work).total_seconds() < cooldown:
            remaining = cooldown - (datetime.now() - last_work).total_seconds()
            mins, secs = divmod(int(remaining), 60)
            await query.answer(f"⏳ Подождите {mins} мин {secs} сек", show_alert=True)
            return
    
    # Анимация работы
    work_messages = {
        'taxi': "🚕 Вы приняли заказ! Ожидайте...",
        'accountant': "📊 Считаем цифры...",
        'builder': "👷 Строим...",
        'businessman': "👨‍💼 Заключаем сделку..."
    }
    
    await query.edit_message_text(work_messages[job_type])
    
    # Случайное время работы (3-8 секунд)
    work_time = random.randint(3, 8)
    await asyncio.sleep(work_time)
    
    # Завершаем работу
    await finish_work_job(update, context, job_type)
    
async def finish_work_job(update: Update, context: ContextTypes.DEFAULT_TYPE, job_type: str):
    """Завершение работы"""
    query = update.callback_query
    user_id = query.from_user.id
    user = get_user_data(user_id)
    job_data = user['jobs'][job_type]
    level = job_data['level']
    
    # Зарплаты
    salaries = {
        'taxi': [20000, 40000, 80000],
        'accountant': [1000000, 2000000, 4000000],
        'builder': [50000, 100000, 200000],
        'businessman': [500000, 1000000, 2000000]
    }
    
    # Названия
    job_names = {
        'taxi': "🚕 Таксист",
        'accountant': "📊 Бухгалтер",
        'builder': "👷 Строитель",
        'businessman': "👨‍💼 Бизнесмен"
    }
    
    # Базовая зарплата
    salary = salaries[job_type][level-1]
    
    # Случайный бонус (10% шанс)
    bonus = 1.0
    bonus_text = ""
    if random.random() < 0.1:
        bonus = 2.0
        bonus_text = "\n✨ БОНУС! x2"
    
    final_salary = int(salary * bonus)
    user['balance'] += final_salary
    
    # Обновляем статистику
    job_data['completed'] += 1
    job_data['last_work'] = datetime.now().isoformat()
    
    # Проверка повышения уровня
    level_up = False
    if level < 3:
        next_level_req = {1: 100, 2: 250}[level]
        if job_data['completed'] >= next_level_req:
            job_data['level'] += 1
            level_up = True
    
    # Формируем результат
    text = (
        f"✅ РАБОТА ЗАВЕРШЕНА!\n\n"
        f"{job_names[job_type]} - Уровень {level}\n"
        f"💰 Заработано: {final_salary:,} ₽{bonus_text}\n"
        f"📊 Всего работ: {job_data['completed']}"
    )
    
    if level_up:
        text += f"\n\n🎉 ПОЗДРАВЛЯЕМ! Достигнут {job_data['level']} уровень!"
    
    # Клавиатура
    keyboard = [
        [InlineKeyboardButton("🔄 РАБОТАТЬ СНОВА", callback_data=f"work_{job_type}")],
        [InlineKeyboardButton("🔙 В МЕНЮ", callback_data="work_back")]
    ]
    
    await query.edit_message_text(
        text=text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
    save_data()
    return WORK_MENU  # ВАЖНО: возвращаем состояние!

async def work_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Вернуться в меню работ"""
    query = update.callback_query
    await query.answer()
    return await work_menu(update, context)

async def work_back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Вернуться в главное меню"""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "Главное меню",
        reply_markup=get_main_keyboard()
    )
    return ConversationHandler.END



async def finish_work_job(update: Update, context: ContextTypes.DEFAULT_TYPE, job_type: str):
    """Завершение работы с начислением зарплаты"""
    query = update.callback_query
    user_id = query.from_user.id
    user = get_user_data(user_id)
    job_data = user['jobs'][job_type]
    level = job_data['level']
    
    # Зарплаты
    salaries = {
        'taxi': [20000, 40000, 80000],
        'accountant': [random.randint(1_000_000, 4_000_000), 
                      random.randint(2_000_000, 6_000_000), 
                      random.randint(4_000_000, 10_000_000)],
        'builder': [random.randint(50_000, 150_000), 
                    random.randint(100_000, 250_000), 
                    random.randint(200_000, 500_000)],
        'businessman': [random.randint(500_000, 2_000_000), 
                        random.randint(1_000_000, 3_000_000), 
                        random.randint(2_000_000, 5_000_000)]
    }
    
    # Случайные бонусы
    bonus_mult = 1.0
    bonus_text = ""
    
    # Бонус за уровень
    if level >= 3 and random.random() < 0.2:
        bonus_mult = 1.5
        bonus_text = "\n✨ БОНУС ЗА УРОВЕНЬ! x1.5"
    
    # Редкий бонус (5%)
    if random.random() < 0.05:
        bonus_mult *= 2
        bonus_text += "\n🎉 ДЖЕКПОТ! x2"
    
    # Профессиональные бонусы
    if job_type == 'taxi' and random.random() < 0.1:
        bonus_mult *= 1.3
        bonus_text += "\n💰 ЧАЕВЫЕ! +30%"
    elif job_type == 'accountant' and random.random() < 0.1:
        bonus_mult *= 1.4
        bonus_text += "\n🔍 НАШЕЛ ОШИБКУ! +40%"
    elif job_type == 'builder' and random.random() < 0.1:
        bonus_mult *= 1.3
        bonus_text += "\n🏗️ ПРЕМИЯ! +30%"
    elif job_type == 'businessman' and random.random() < 0.1:
        bonus_mult *= 1.5
        bonus_text += "\n📈 ВЫГОДНАЯ СДЕЛКА! +50%"
    
    # Итоговая зарплата
    base_salary = salaries[job_type][level-1]
    final_salary = int(base_salary * bonus_mult)
    user['balance'] += final_salary
    
    # Обновляем статистику
    job_data['completed'] += 1
    job_data['last_work'] = datetime.now().isoformat()
    
    # Проверка повышения уровня
    level_up = False
    if level < 3:
        next_level_req = {1: 100, 2: 250}[level]
        if job_data['completed'] >= next_level_req:
            job_data['level'] += 1
            level_up = True
    
    # Формируем результат
    job_names = {
        'taxi': "🚕 Таксист",
        'accountant': "📊 Бухгалтер",
        'builder': "👷 Строитель",
        'businessman': "👨‍💼 Бизнесмен"
    }
    
    result_text = (
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"     ✅ РАБОТА ЗАВЕРШЕНА     \n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        f"{job_names[job_type]} - Уровень {level}\n\n"
        
        f"💰 <b>ЗАРАБОТАНО:</b>\n"
        f"├ База: {base_salary:,} ₽\n"
    )
    
    if bonus_mult > 1.0:
        result_text += f"├ Множитель: x{bonus_mult:.1f}\n"
        result_text += f"└ ИТОГО: {final_salary:,} ₽"
    else:
        result_text += f"└ ИТОГО: {final_salary:,} ₽"
    
    result_text += f"\n\n📊 <b>СТАТИСТИКА:</b>\n"
    result_text += f"├ Всего работ: {job_data['completed']}\n"
    
    if level_up:
        result_text += f"└ 🎉 НОВЫЙ УРОВЕНЬ! Теперь {level + 1} уровень!"
    else:
        result_text += f"└ Текущий уровень: {level}"
    
    if bonus_text:
        result_text += f"\n\n✨ <b>БОНУСЫ:</b>{bonus_text}"
    
    result_text += f"\n\n━━━━━━━━━━━━━━━━━━━━━"
    
    # Клавиатура
    keyboard = [
        [InlineKeyboardButton("🔄 РАБОТАТЬ СНОВА", callback_data=f"work_{job_type}")],
        [InlineKeyboardButton("🔙 В МЕНЮ РАБОТ", callback_data="work_back")]
    ]
    
    await query.edit_message_text(
        text=result_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )
    
    save_data()

async def businesses_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Главное меню бизнесов"""
    user_id = str(update.effective_user.id)
    user = get_user_data(user_id)
    
    # Инициализируем business_count если его нет
    if 'business_count' not in user:
        user['business_count'] = 0
    
    # Проверяем VIP статус
    is_vip = check_vip(user_id)
    has_vip_business = user.get('vip_business', False) and is_vip
    
    # Рассчитываем доход с обычных бизнесов
    total_income = 0
    for i in range(1, user['business_count'] + 1):
        biz = BUSINESS_TYPES.get(i)
        if biz:
            total_income += biz['income']
    
    # Добавляем VIP бизнес
    if has_vip_business:
        vip_income = 30_000_000
        total_income += vip_income
    
    # Применяем VIP бонус 15%
    if is_vip:
        total_income = int(total_income * 1.15)
    
    # Рассчитываем накопленное
    last_income = datetime.fromisoformat(user['last_business_income'])
    now = datetime.now()
    seconds_passed = (now - last_income).total_seconds()
    income_per_second = total_income / 3600 if total_income > 0 else 0
    accumulated = int(income_per_second * seconds_passed) if total_income > 0 else 0
    
    # Определяем следующий бизнес
    next_business_id = user['business_count'] + 1
    next_biz_info = ""
    
    if next_business_id in BUSINESS_TYPES:
        next_biz = BUSINESS_TYPES[next_business_id]
        next_biz_info = (
            f"\n\n📈 <b>СЛЕДУЮЩИЙ БИЗНЕС:</b>\n"
            f"{next_biz['emoji']} {next_biz['name']}\n"
            f"💰 Цена: {next_biz['price']:,} ₽\n"
            f"💵 Доход/час: {next_biz['income']:,} ₽"
        )
    elif user['business_count'] >= len(BUSINESS_TYPES):
        next_biz_info = "\n\n🎉 <b>ПОЗДРАВЛЯЕМ!</b>\nУ вас все обычные бизнесы!"
    
    # Формируем текст
    text = (
        f"🏢 <b>ИМПЕРИЯ БИЗНЕСОВ</b>\n"
        f"═══════════════════\n\n"
        
        f"👤 Владелец: @{user.get('username', 'Игрок')}\n"
        f"💰 Баланс: {user['balance']:,} ₽\n"
        f"🏢 Обычных бизнесов: {user['business_count']}/{len(BUSINESS_TYPES)}\n"
    )
    
    if has_vip_business:
        text += f"👑 VIP бизнес: +1\n"
    
    text += (
        f"\n📊 <b>ДОХОД:</b>\n"
        f"├ В час: {total_income:,} ₽\n"
        f"├ В день: {total_income * 24:,} ₽\n"
        f"└ Накоплено: {accumulated:,} ₽\n\n"
        
        f"⏱️ <b>СТАТУС:</b>\n"
        f"└ Последний сбор: {last_income.strftime('%d.%m.%Y %H:%M')}\n"
        f"{next_biz_info}"
    )
    
    if is_vip:
        text += f"\n\n👑 <b>VIP СТАТУС АКТИВЕН</b>\n"
        text += f"💰 Ежедневный бонус: 5,000,000 ₽\n"
        text += f"📈 Бонус к доходу: +15%"
    
    # Создаем клавиатуру
    keyboard = []
    keyboard.append([InlineKeyboardButton("📊 МОИ БИЗНЕСЫ", callback_data="business_list")])
    
    if next_business_id in BUSINESS_TYPES:
        next_biz = BUSINESS_TYPES[next_business_id]
        keyboard.append([InlineKeyboardButton(
            f"🛒 КУПИТЬ {next_biz['emoji']} {next_biz['name']}",
            callback_data=f"business_buy_{next_business_id}"
        )])
    
    available = len(BUSINESS_TYPES) - user['business_count']
    if available > 1:
        keyboard.append([InlineKeyboardButton(
            f"🔍 ВЫБРАТЬ ИЗ {available}",
            callback_data="business_show_buy"
        )])
    
    if accumulated > 0:
        if seconds_passed < 60:
            time_text = f"{int(seconds_passed)} сек"
        elif seconds_passed < 3600:
            minutes = int(seconds_passed // 60)
            time_text = f"{minutes} мин"
        else:
            hours = int(seconds_passed // 3600)
            time_text = f"{hours} ч"
        
        keyboard.append([InlineKeyboardButton(
            f"💰 ЗАБРАТЬ {accumulated:,} ₽ (за {time_text})",
            callback_data="business_collect"
        )])
    
    keyboard.append([InlineKeyboardButton("📈 ТАБЛИЦА ДОХОДОВ", callback_data="business_income_table")])
    keyboard.append([InlineKeyboardButton("🔙 НАЗАД", callback_data="business_back")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        if update.callback_query:
            await update.callback_query.edit_message_text(
                text=text,
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
        else:
            await update.message.reply_text(
                text=text,
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
    except Exception as e:
        logging.error(f"Ошибка в businesses_menu: {e}")
    
    return BUY_BUSINESS
    
async def business_collect(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сбор дохода с бизнесов"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    user = get_user_data(user_id)
    
    # Получаем время последнего АВТОМАТИЧЕСКОГО начисления
    # НЕ ИЗ user['last_business_income'], а из отдельной переменной!
    last_auto_income = user.get('last_auto_income')
    
    if not last_auto_income:
        # Если нет, создаём
        user['last_auto_income'] = datetime.now().isoformat()
        save_data()
        await query.answer("🔄 Система синхронизируется...", show_alert=True)
        return await businesses_menu(update, context)
    
    last = datetime.fromisoformat(last_auto_income)
    now = datetime.now()
    seconds = (now - last).total_seconds()
    
    if seconds < 10:
        remaining = 10 - int(seconds)
        await query.answer(f"⏳ Подождите {remaining} сек", show_alert=True)
        return await businesses_menu(update, context)
    
    # ========== ПРОВЕРЯЕМ VIP СТАТУС ==========
    is_vip = check_vip(user_id)
    has_vip_business = user.get('vip_business', False)
    
    # Логируем для отладки
    logging.info(f"🔥 СБОР: user={user_id}, is_vip={is_vip}, has_vip_business={has_vip_business}, seconds={seconds}")
    
    # ========== СЧИТАЕМ ДОХОД ==========
    total_earned = 0
    details = []
    
    # 1. Обычные бизнесы
    business_count = user.get('business_count', 0)
    for i in range(1, business_count + 1):
        biz = BUSINESS_TYPES.get(i)
        if biz:
            biz_earned = int((biz['income'] / 3600) * seconds)
            total_earned += biz_earned
            details.append(f"📊 {biz['name']}: +{biz_earned} ₽")
    
    # 2. VIP бизнес - ОБЯЗАТЕЛЬНО ДОБАВЛЯЕМ!
    if has_vip_business and is_vip:
        vip_earned = int((30_000_000 / 3600) * seconds)
        total_earned += vip_earned
        details.append(f"👑 VIP бизнес: +{vip_earned} ₽")
        logging.info(f"🔥 VIP ДОБАВЛЕН: +{vip_earned} ₽ за {seconds} сек")
    
    # 3. VIP бонус 15%
    if is_vip:
        old_total = total_earned
        total_earned = int(total_earned * 1.15)
        bonus = total_earned - old_total
        details.append(f"✨ VIP бонус 15%: +{bonus} ₽")
    
    if total_earned <= 0:
        await query.answer("❌ Нет дохода", show_alert=True)
        return await businesses_menu(update, context)
    
    # НАЧИСЛЯЕМ
    user['balance'] += total_earned
    
    # ВАЖНО: Обновляем ТОЛЬКО last_auto_income, НЕ ТРОГАЕМ last_business_income!
    user['last_auto_income'] = now.isoformat()
    save_data()
    
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    
    detail_text = "\n".join(details[:3])
    await query.answer(
        f"✅ +{total_earned:,} ₽ за {minutes} мин {secs} сек\n{detail_text}",
        show_alert=True
    )
    
    return await businesses_menu(update, context)
    
async def business_income_table(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает таблицу доходов по уровням"""
    query = update.callback_query
    await query.answer()
    
    text = "📈 <b>Таблица доходов по уровням</b>\n\n"
    
    # Группируем по уровням
    levels = {}
    for biz_id, biz in BUSINESS_TYPES.items():
        level = biz['level']
        if level not in levels:
            levels[level] = []
        levels[level].append((biz_id, biz))
    
    # Сортируем уровни
    for level in sorted(levels.keys()):
        text += f"\n<b>УРОВЕНЬ {level}</b>\n"
        text += "═══════════════════\n"
        
        for biz_id, biz in sorted(levels[level], key=lambda x: x[0]):
            text += (
                f"{biz['emoji']} {biz['name']}\n"
                f"   💰 Цена: {biz['price']:,} ₽\n"
                f"   💵 Доход: {biz['income']:,} ₽/час\n"
                f"   ⏱️ Окупаемость: {biz['price'] // biz['income']} ч\n\n"
            )
    
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="business_back")]]
    
    await query.edit_message_text(
        text=text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )
    return BUY_BUSINESS    

async def business_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Исправленный обработчик кнопок бизнесов"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_id = str(query.from_user.id)
    user = get_user_data(user_id)
    
    print(f"🔍 DEBUG: Нажата кнопка {data}")
    
    # ===== ВАЖНО: ПРОВЕРКА НА КНОПКУ СБОРА ДОХОДА =====
    if data == "business_collect":
        print(f"💰 Обработка сбора дохода")
        return await business_collect(update, context)
    
    # ===== ПЕРЕДАЧА КНОПОК ДРУГИХ МЕНЮ =====
    if data.startswith('top_'):
        print(f"🔄 Передаем кнопку топа в обработчик: {data}")
        new_update = Update(update.update_id, callback_query=query)
        return await top_button_handler(new_update, context)
    
    if data.startswith('work_') or data.startswith('start_work_'):
        print(f"🔄 Передаем кнопку работы в обработчик: {data}")
        new_update = Update(update.update_id, callback_query=query)
        return await work_callback(new_update, context)
    
    if data.startswith('box_') or data.startswith('premium_box_') or data.startswith('daily_box_'):
        print(f"🔄 Передаем кнопку боксов в обработчик: {data}")
        new_update = Update(update.update_id, callback_query=query)
        return await box_button_handler(new_update, context)
    
    if (data.startswith('shop_') or data.startswith('consumables_') or 
        data.startswith('gift_') or data.startswith('token_buy_')):
        print(f"🔄 Передаем кнопку магазина в обработчик: {data}")
        new_update = Update(update.update_id, callback_query=query)
        return await shop_button_handler(new_update, context)
    
    if data.startswith('bank_') or data.startswith('invest_'):
        print(f"🔄 Передаем кнопку банка в обработчик: {data}")
        new_update = Update(update.update_id, callback_query=query)
        return await bank_button_handler(new_update, context)
    
    if data.startswith('trade_'):
        print(f"🔄 Передаем кнопку трейдов в обработчик: {data}")
        new_update = Update(update.update_id, callback_query=query)
        return await trade_button_handler(new_update, context)
    
    if data.startswith('gang_'):
        print(f"🔄 Передаем кнопку банд в обработчик: {data}")
        new_update = Update(update.update_id, callback_query=query)
        return await gang_button_handler(new_update, context)
    
    if data.startswith('bet:'):
        print(f"🔄 Передаем кнопку казино в обработчик: {data}")
        new_update = Update(update.update_id, callback_query=query)
        return await handle_bet_type(new_update, context)
    
    if data.startswith('pvp_'):
        print(f"🔄 Передаем кнопку PvP в обработчик: {data}")
        if data.startswith('pvp_accept_'):
            return await pvp_accept(update, context)
        elif data.startswith('pvp_decline_'):
            return await pvp_decline(update, context)
    
    # ===== ОСТАЛЬНОЙ КОД БИЗНЕСОВ =====
    
    # Инициализируем данные если их нет
    if 'business_count' not in user:
        user['business_count'] = 0
    
    if 'last_business_income' not in user or user['last_business_income'] is None:
        user['last_business_income'] = datetime.now().isoformat()
    elif not isinstance(user['last_business_income'], str):
        try:
            user['last_business_income'] = user['last_business_income'].isoformat()
        except:
            user['last_business_income'] = datetime.now().isoformat()
    
    # ==================== ПОКАЗАТЬ СПИСОК БИЗНЕСОВ ====================
    if data == "business_list":
        business_count = user.get('business_count', 0)
        
        if business_count == 0:
            text = "❌ У вас пока нет бизнесов."
        else:
            text = "📊 <b>ВАШИ БИЗНЕСЫ:</b>\n═══════════════════\n\n"
            total_income = 0
            
            for i in range(1, business_count + 1):
                biz = BUSINESS_TYPES.get(i)
                if biz:
                    text += (
                        f"{i}. {biz['emoji']} <b>{biz['name']}</b>\n"
                        f"   💰 Доход: {biz['income']:,} ₽/час\n"
                        f"   📈 Категория: {biz['category']}\n\n"
                    )
                    total_income += biz['income']
            
            text += f"═══════════════════\n"
            text += f"💵 <b>ОБЩИЙ ДОХОД:</b> {total_income:,} ₽/час\n"
            text += f"💰 В день: {total_income * 24:,} ₽"
        
        keyboard = [
            [InlineKeyboardButton("🛒 КУПИТЬ БИЗНЕС", callback_data="business_show_buy")],
            [InlineKeyboardButton("🔙 НАЗАД", callback_data="business_back")]
        ]
        
        await query.edit_message_text(
            text=text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
        return BUY_BUSINESS
    
    # ==================== ПОКАЗАТЬ ДОСТУПНЫЕ ДЛЯ ПОКУПКИ ====================
    elif data == "business_show_buy":
        keyboard = []
        business_count = user.get('business_count', 0)
        
        for biz_id, biz_info in BUSINESS_TYPES.items():
            if biz_id > business_count:
                if biz_id == business_count + 1:
                    status = "✅ ДОСТУПНО"
                    callback_data = f"business_buy_{biz_id}"
                else:
                    status = "🔒 ТРЕБУЕТСЯ ПРЕДЫДУЩИЙ"
                    callback_data = f"business_locked_{biz_id}"
                
                button_text = f"{biz_info['emoji']} {biz_info['name']} - {biz_info['price']:,}₽ ({status})"
                keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
        
        if not keyboard:
            await query.answer("🎉 У вас уже все бизнесы куплены!", show_alert=True)
            return await businesses_menu(update, context)
        
        keyboard.append([InlineKeyboardButton("🔙 НАЗАД", callback_data="business_back")])
        
        await query.edit_message_text(
            "🛒 <b>ДОСТУПНЫЕ БИЗНЕСЫ:</b>\n═══════════════════\n\n"
            "✅ - можно купить сейчас\n"
            "🔒 - требуется купить предыдущий",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
        return BUY_BUSINESS
    
    # ==================== ЗАБЛОКИРОВАННЫЙ БИЗНЕС ====================
    elif data.startswith("business_locked_"):
        await query.answer("❌ Сначала купите предыдущий бизнес!", show_alert=True)
        return BUY_BUSINESS
    
    # ==================== НАЧАТЬ ПОКУПКУ БИЗНЕСА ====================
    elif data.startswith("business_buy_"):
        try:
            business_type = int(data.split('_')[2])
        except:
            await query.answer("❌ Ошибка формата!", show_alert=True)
            return await businesses_menu(update, context)
            
        biz_info = BUSINESS_TYPES.get(business_type)
        
        if not biz_info:
            await query.answer("❌ Ошибка: тип бизнеса не найден", show_alert=True)
            return await businesses_menu(update, context)
        
        business_count = user.get('business_count', 0)
        
        if business_type <= business_count:
            await query.answer("❌ Этот бизнес уже куплен!", show_alert=True)
            return await businesses_menu(update, context)
        
        if business_type > business_count + 1:
            next_to_buy = business_count + 1
            next_biz = BUSINESS_TYPES.get(next_to_buy)
            await query.answer(
                f"❌ Сначала купите {next_biz['emoji']} {next_biz['name']}!", 
                show_alert=True
            )
            return await businesses_menu(update, context)
        
        if user['balance'] < biz_info['price']:
            await query.answer(
                f"❌ Недостаточно средств! Нужно {biz_info['price']:,} ₽", 
                show_alert=True
            )
            return await businesses_menu(update, context)
        
        payback_hours = biz_info['price'] // biz_info['income']
        payback_days = payback_hours // 24
        payback_hours_remain = payback_hours % 24
        
        text = (
            f"🛒 <b>ПОДТВЕРДИТЕ ПОКУПКУ</b>\n"
            f"═══════════════════\n\n"
            f"{biz_info['emoji']} <b>{biz_info['name']}</b>\n"
            f"📋 Категория: {biz_info['category']}\n"
            f"📊 Уровень: {biz_info['level']}\n\n"
            f"💵 Стоимость: {biz_info['price']:,} ₽\n"
            f"💰 Доход/час: {biz_info['income']:,} ₽\n"
            f"⏱️ Окупаемость: {payback_days}д {payback_hours_remain}ч\n\n"
            f"💳 Ваш баланс: {user['balance']:,} ₽\n"
            f"💳 После покупки: {user['balance'] - biz_info['price']:,} ₽"
        )
        
        keyboard = [
            [InlineKeyboardButton("✅ ПОДТВЕРДИТЬ", callback_data=f"business_confirm_{business_type}")],
            [InlineKeyboardButton("❌ ОТМЕНА", callback_data="business_show_buy")]
        ]
        
        await query.edit_message_text(
            text=text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
        return BUY_BUSINESS
    
    # ==================== ПОДТВЕРДИТЬ ПОКУПКУ ====================
    elif data.startswith("business_confirm_"):
        try:
            business_type = int(data.split('_')[2])
        except:
            await query.answer("❌ Ошибка формата!", show_alert=True)
            return await businesses_menu(update, context)
            
        biz_info = BUSINESS_TYPES.get(business_type)
        
        if not biz_info:
            await query.answer("❌ Ошибка!", show_alert=True)
            return await businesses_menu(update, context)
        
        if user['balance'] < biz_info['price']:
            await query.answer("❌ Недостаточно средств!", show_alert=True)
            return await businesses_menu(update, context)
        
        user['balance'] -= biz_info['price']
        user['business_count'] = business_type
        
        if business_type == 1:
            user['last_business_income'] = datetime.now().isoformat()
        
        save_data()
        
        text = (
            f"✅ <b>ПОЗДРАВЛЯЕМ С ПОКУПКОЙ!</b>\n"
            f"═══════════════════\n\n"
            f"{biz_info['emoji']} <b>{biz_info['name']}</b>\n"
            f"💰 Доход/час: {biz_info['income']:,} ₽\n"
            f"💳 Новый баланс: {user['balance']:,} ₽\n\n"
            f"🏢 Всего бизнесов: {user['business_count']}/{len(BUSINESS_TYPES)}"
        )
        
        await query.edit_message_text(
            text=text,
            parse_mode='HTML'
        )
        
        await asyncio.sleep(3)
        return await businesses_menu(update, context)
    
    # ==================== ТАБЛИЦА ДОХОДОВ ====================
    elif data == "business_income_table":
        text = "📈 <b>ТАБЛИЦА ДОХОДОВ</b>\n═══════════════════\n\n"
        
        levels = {}
        for biz_id, biz in BUSINESS_TYPES.items():
            level = biz['level']
            if level not in levels:
                levels[level] = []
            levels[level].append((biz_id, biz))
        
        for level in sorted(levels.keys()):
            text += f"\n<b>📊 УРОВЕНЬ {level}</b>\n"
            text += "┌─────────────────────\n"
            
            for biz_id, biz in sorted(levels[level], key=lambda x: x[0]):
                payback = biz['price'] // biz['income']
                text += (
                    f"│ {biz['emoji']} <b>{biz['name']}</b>\n"
                    f"│ 💰 {biz['price']:,} ₽ → {biz['income']:,} ₽/ч\n"
                    f"│ ⏱️ Окупаемость: {payback} ч\n"
                )
            text += "└─────────────────────\n"
        
        keyboard = [[InlineKeyboardButton("🔙 НАЗАД", callback_data="business_back")]]
        
        await query.edit_message_text(
            text=text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
        return BUY_BUSINESS
    
    # ==================== НАЗАД ====================
    elif data == "business_back":
        return await businesses_menu(update, context)
    
    # Если ни одно условие не подошло
    print(f"⚠️ Неизвестная кнопка в бизнесах: {data}")
    return await businesses_menu(update, context);
    
async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать баланс пользователя"""
    user_id = update.effective_user.id
    if str(user_id) in banned_users:
        await update.message.reply_text("⛔ Вы заблокированы и не можете использовать бота.")
        return
        
    user = get_user_data(user_id)
    user['last_active'] = time.time()
    
    # Получаем количество бизнесов
    business_count = user.get('business_count', 0)
    
    # Рассчитываем доход с бизнесов
    business_income = 0
    for i in range(1, business_count + 1):
        biz = BUSINESS_TYPES.get(i)
        if biz:
            business_income += biz['income']
    
    # Получаем статистику казино
    casino_stat = casino_stats.get(str(user_id), {'lost': 0, 'won': 0, 'net': 0})
    
    # Формируем красивое сообщение
    text = (
        f"💰 <b>ВАШ БАЛАНС</b>\n"
        f"═══════════════════\n\n"
        
        f"💳 <b>Основной счет:</b>\n"
        f"└ {user['balance']:,} ₽\n\n"
        
        f"🪙 <b>Койны:</b>\n"
        f"└ {user.get('coins', 0)}\n\n"
        
        f"🏢 <b>Бизнесы:</b>\n"
        f"├ Количество: {business_count}\n"
        f"└ Доход/час: {business_income:,} ₽\n\n"
        
        f"🎰 <b>Казино:</b>\n"
        f"├ Выиграно: {casino_stat['won']:,} ₽\n"
        f"├ Проиграно: {casino_stat['lost']:,} ₽\n"
        f"└ Чистый результат: {casino_stat['net']:+,} ₽"
    )
    
    await update.message.reply_text(text, parse_mode='HTML')    

async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать профиль пользователя с достижениями"""
    user_id = str(update.effective_user.id)
    if user_id in banned_users:
        await update.message.reply_text("⛔ Вы заблокированы и не можете использовать бота.")
        return
    
    user = get_user_data(user_id)
    user['last_active'] = time.time()
    
    # Проверяем новые достижения
    new_achs, reward = check_achievements(user_id, user)
    if new_achs:
        await update.message.reply_text(
            f"🎉 <b>НОВЫЕ ДОСТИЖЕНИЯ!</b>\n\n"
            f"{chr(10).join(['• ' + ach for ach in new_achs])}\n\n"
            f"💰 Получено: {reward:,} ₽",
            parse_mode='HTML'
        )
    
    username = user.get('username') or update.message.from_user.username or update.message.from_user.full_name
    
    if 'referral_code' not in user:
        user['referral_code'] = secrets.token_hex(4)
        save_data()
    
    total_income = sum(BUSINESS_TYPES.get(i, {}).get('income', 0) for i in range(1, user.get('business_count', 0) + 1))
    
    # Статистика достижений
    total_achs = len(user.get('achievements', {}))
    secret_achs = sum(1 for a in user.get('achievements', {}) if a in SECRET_ACHIEVEMENTS)
    all_achs = len(ACHIEVEMENTS)
    
    # Формируем текст профиля
    profile_text = (
        f"📊 <b>ПРОФИЛЬ @{username}</b>\n"
        f"═══════════════════\n\n"
        
        f"💰 <b>Баланс:</b> {user['balance']:,} ₽\n"
        f"🪙 <b>Койны:</b> {user.get('coins', 0)}\n"
        f"🏢 <b>Бизнесы:</b> {user.get('business_count', 0)} (Доход: {total_income:,} ₽/час)\n"
        f"📨 <b>Рефералов:</b> {len(user.get('referrals', []))}\n"
        f"🏆 <b>Достижения:</b> {total_achs}/{all_achs} (🔮 {secret_achs} секретных)\n\n"
        
        f"🔗 <b>Реферальная ссылка:</b>\n"
        f"https://t.me/{(await context.bot.get_me()).username}?start=ref_{user['referral_code']}\n"
    )
    
    # Клавиатура с кнопкой достижений
    keyboard = [
        [InlineKeyboardButton("🏆 МОИ ДОСТИЖЕНИЯ", callback_data="profile_achievements")],
        [InlineKeyboardButton("🔙 НАЗАД", callback_data="profile_back")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Отправляем фото профиля
    photo_info = get_user_photo_info(user_id)
    photo_path = photo_info["path"]
    
    try:
        if os.path.exists(photo_path):
            with open(photo_path, 'rb') as photo_file:
                await context.bot.send_photo(
                    chat_id=update.message.chat_id,
                    photo=photo_file,
                    caption=profile_text,
                    reply_markup=reply_markup,
                    parse_mode='HTML'
                )
        else:
            await update.message.reply_text(
                profile_text,
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
    except Exception as e:
        logging.error(f"Ошибка отправки фото профиля: {e}")
        await update.message.reply_text(
            profile_text,
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    
    save_data()
    
async def show_achievements(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать список достижений пользователя"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    user = get_user_data(user_id)
    
    if 'achievements' not in user:
        user['achievements'] = {}
    
    # Счетчики
    total_achievements = len(ACHIEVEMENTS)
    unlocked_achievements = len(user['achievements'])
    secret_total = sum(1 for a in ACHIEVEMENTS if a in SECRET_ACHIEVEMENTS)
    secret_unlocked = sum(1 for a in user['achievements'] if a in SECRET_ACHIEVEMENTS)
    
    text = (
        "🏆 <b>МОИ ДОСТИЖЕНИЯ</b>\n"
        f"══════════════════════════\n"
        f"📊 Прогресс: {unlocked_achievements}/{total_achievements}\n"
        f"🔮 Секретных: {secret_unlocked}/{secret_total}\n"
        f"══════════════════════════\n\n"
    )
    
    # Группируем достижения по категориям
    categories = {
        '💰 БАЛАНС': ['millionaire', 'billionaire', 'trillionaire'],
        '🏢 БИЗНЕС': ['business_beginner', 'business_master', 'business_tycoon'],
        '🎰 КАЗИНО': ['casino_winner', 'casino_addict', 'casino_lucky'],
        '💼 РАБОТА': ['hard_worker', 'workaholic'],
        '👥 ДРУЗЬЯ': ['friend_1', 'friend_10', 'friend_50'],
        '🎁 БОКСЫ': ['box_opener', 'box_master'],
        '📈 ИНВЕСТИЦИИ': ['investor', 'gambler'],
    }
    
    for category, ach_list in categories.items():
        category_text = f"\n<b>{category}</b>\n"
        category_count = 0
        category_total = len(ach_list)
        
        for ach_id in ach_list:
            ach = ACHIEVEMENTS.get(ach_id)
            if not ach:
                continue
            
            unlocked = ach_id in user['achievements']
            
            if unlocked:
                category_count += 1
                emoji = "✅"
                name = ach['name']
                desc = ach['description']
                
                # Для секретных показываем описание только после получения
                if ach_id in SECRET_ACHIEVEMENTS:
                    desc = ach['description']
                
                category_text += f"{emoji} <b>{name}</b>\n"
                category_text += f"   └ {desc}\n"
            else:
                if ach_id in SECRET_ACHIEVEMENTS:
                    # Секретные достижения скрыты до получения
                    category_text += f"❓ <b>Секретное достижение</b>\n"
                    category_text += f"   └ ???\n"
                else:
                    category_text += f"❌ <b>{ach['name']}</b>\n"
                    category_text += f"   └ {ach['description']}\n"
        
        # Добавляем прогресс по категории
        category_text = category_text.replace(
            f"\n<b>{category}</b>\n", 
            f"\n<b>{category}</b> [{category_count}/{category_total}]\n"
        )
        text += category_text
    
    # Добавляем подсказку о секретных достижениях
    if secret_unlocked < secret_total:
        text += f"\n💡 <i>Подсказка: секретные достижения открываются за особые действия</i>"
    
    keyboard = [[InlineKeyboardButton("🔙 НАЗАД", callback_data="profile_back")]]
    
    # Проверяем, что есть что редактировать
    try:
        await query.edit_message_text(
            text=text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
    except Exception as e:
        # Если не получилось отредактировать, отправляем новое сообщение
        await query.message.reply_text(
            text=text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
  
async def profile_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопок в профиле"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data == "profile_achievements":
        return await show_achievements(update, context)
    elif data == "profile_back":
        await query.edit_message_text("📊 Профиль")
        return        

def update_casino_stats(user_id, bet_amount, win_amount):
    """Обновляет статистику казино для топа по сливу"""
    user_id = str(user_id)
    
    if user_id not in casino_stats:
        casino_stats[user_id] = {'lost': 0, 'won': 0, 'net': 0}
    
    if win_amount > 0:
        # Выигрыш (чистая прибыль = выигрыш - ставка)
        profit = win_amount - bet_amount
        casino_stats[user_id]['won'] += win_amount
        casino_stats[user_id]['net'] += profit
    else:
        # Проигрыш
        casino_stats[user_id]['lost'] += bet_amount
        casino_stats[user_id]['net'] -= bet_amount
    
    # Сохраняем статистику
    save_casino_stats()

def save_casino_stats():
    """Сохраняет статистику казино"""
    try:
        with open('casino_stats.json', 'w', encoding='utf-8') as f:
            json.dump(casino_stats, f, ensure_ascii=False, indent=4)
    except Exception as e:
        logging.error(f"Ошибка сохранения статистики казино: {e}")

def load_casino_stats():
    """Загружает статистику казино"""
    global casino_stats
    try:
        if os.path.exists('casino_stats.json'):
            with open('casino_stats.json', 'r', encoding='utf-8') as f:
                casino_stats = json.load(f)
    except Exception as e:
        logging.error(f"Ошибка загрузки статистики казино: {e}")
        casino_stats = {}

async def top_losses(update: Update, context: ContextTypes.DEFAULT_TYPE, is_callback=False, page=0):
    """Топ по сливу денег в казино"""
    user_id = update.effective_user.id if is_callback else update.message.from_user.id
    
    if user_id in banned_users:
        if is_callback:
            await update.callback_query.message.reply_text("⛔ Вы заблокированы")
        else:
            await update.message.reply_text("⛔ Вы заблокированы")
        return
    
    # Сортируем пользователей по сумме проигрыша
    sorted_users = sorted(
        [(uid, stats) for uid, stats in casino_stats.items() if int(uid) not in banned_users],
        key=lambda x: x[1]['lost'],
        reverse=True
    )
    
    if not sorted_users:
        text = "📊 Статистика казино пока пуста. Сделайте первую ставку!"
    else:
        text = "💸 <b>ТОП ПО СЛИВУ В КАЗИНО</b>\n\n"
        
        for i, (uid, stats) in enumerate(sorted_users[:10], 1):
            username = user_data.get(uid, {}).get('username', uid)
            lost = stats['lost']
            won = stats['won']
            net = stats['net']
            
            # Эмодзи в зависимости от результата
            if net < 0:
                result_emoji = "🔴"  # В минусе
            elif net > 0:
                result_emoji = "🟢"  # В плюсе
            else:
                result_emoji = "⚪"  # Ноль
            
            text += (
                f"{i}. {result_emoji} @{username}\n"
                f"   💸 Слито: {lost:,} ₽\n"
                f"   💰 Выиграно: {won:,} ₽\n"
                f"   📊 Чистый результат: {net:+,} ₽\n\n"
            )
        
        # Добавляем информацию о текущем пользователе
        if str(user_id) in casino_stats:
            user_stats = casino_stats[str(user_id)]
            position = next((i for i, (uid, _) in enumerate(sorted_users, 1) if uid == str(user_id)), None)
            
            text += f"\n🎯 <b>Ваша статистика:</b>\n"
            text += f"📊 Место: #{position}\n"
            text += f"💸 Слито: {user_stats['lost']:,} ₽\n"
            text += f"💰 Выиграно: {user_stats['won']:,} ₽\n"
            text += f"📈 Чистый результат: {user_stats['net']:+,} ₽"
    
    if is_callback:
        await update.callback_query.edit_message_text(text, parse_mode='HTML')
    else:
        await update.message.reply_text(text, parse_mode='HTML')
        
async def bsk_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Игра БСК (баскетбол) для групп"""
    # Проверяем, что это группа
    if update.message.chat.type not in ('group', 'supergroup'):
        await update.message.reply_text("❌ Эта команда доступна только в группах!")
        return
    
    user_id = update.message.from_user.id
    if user_id in banned_users:
        await update.message.reply_text("⛔ Вы заблокированы")
        return
    
    # Получаем текст сообщения
    text = update.message.text.lower()
    parts = text.split()
    
    if len(parts) != 2:
        await update.message.reply_text(
            "❌ Неверный формат. Используйте: бск [сумма]\n"
            "Пример: бск 100к\n\n"
            "Правила:\n"
            "🏀 x6 при попадании в кольцо\n"
            "🎯 Шанс победы: 40%\n"
            f"💰 Мин. ставка: {BSK_CONFIG['min_bet']:,} ₽\n"
            f"💰 Макс. ставка: {BSK_CONFIG['max_bet']:,} ₽"
        )
        return
    
    # Парсим сумму ставки
    bet_amount_str = parts[1]
    bet_amount = parse_bet_amount(bet_amount_str)
    
    if not bet_amount or bet_amount <= 0:
        await update.message.reply_text("❌ Неверная сумма ставки!")
        return
    
    # Проверяем лимиты
    if bet_amount < BSK_CONFIG['min_bet']:
        await update.message.reply_text(f"❌ Минимальная ставка: {BSK_CONFIG['min_bet']:,} ₽")
        return
    
    if bet_amount > BSK_CONFIG['max_bet']:
        await update.message.reply_text(f"❌ Максимальная ставка: {BSK_CONFIG['max_bet']:,} ₽")
        return
    
    # Получаем данные пользователя
    user = get_user_data(user_id)
    username = user.get('username') or update.message.from_user.username or update.message.from_user.full_name
    
    if bet_amount > user['balance']:
        await update.message.reply_text(f"❌ Недостаточно средств! Ваш баланс: {user['balance']:,} ₽")
        return
    
    # Начинаем игру
    await update.message.reply_text(
        f"🏀 <b>БАСКЕТБОЛ</b>\n\n"
        f"👤 Игрок: @{username}\n"
        f"💰 Ставка: {bet_amount:,} ₽\n"
        f"🎯 Множитель: x{BSK_CONFIG['win_multiplier']}\n\n"
        f"Бросок...",
        parse_mode='HTML'
    )
    
    # Небольшая пауза для эффекта
    await asyncio.sleep(1.5)
    
    # Определяем результат
    win = random.random() < BSK_CONFIG['win_chance']
    
    if win:
        # ПОПАДАНИЕ!
        win_amount = bet_amount * BSK_CONFIG['win_multiplier']
        user['balance'] += win_amount - bet_amount  # Добавляем чистый выигрыш
        
        result_text = (
            f"🏀 <b>БАСКЕТБОЛ - ПОПАДАНИЕ! 🔥</b>\n\n"
            f"👤 Игрок: @{username}\n"
            f"💰 Ставка: {bet_amount:,} ₽\n"
            f"🎯 Множитель: x{BSK_CONFIG['win_multiplier']}\n"
            f"💵 ВЫИГРЫШ: {win_amount:,} ₽\n"
            f"📈 Чистая прибыль: {win_amount - bet_amount:,} ₽\n\n"
            f"🎉 ПОЗДРАВЛЯЕМ! Мяч в кольце!"
        )
        
        # Отправляем стикер успеха (или эмодзи)
        await update.message.reply_sticker(sticker=BSK_STICKERS['success'])
        
    else:
        # ПРОМАХ!
        user['balance'] -= bet_amount
        
        result_text = (
            f"🏀 <b>БАСКЕТБОЛ - ПРОМАХ</b>\n\n"
            f"👤 Игрок: @{username}\n"
            f"💰 Ставка: {bet_amount:,} ₽\n"
            f"❌ Проигрыш: {bet_amount:,} ₽\n"
            f"💔 Мяч не попал в кольцо...\n\n"
            f"😢 Повезет в следующий раз!"
        )
        
        # Отправляем стикер промаха
        await update.message.reply_sticker(sticker=BSK_STICKERS['fail'])
    
    # Отправляем результат
    await update.message.reply_text(
        result_text + f"\n\n💰 Новый баланс: {user['balance']:,} ₽",
        parse_mode='HTML'
    )
    
    # Обновляем статистику казино (для топа по сливу)
    if win:
        update_casino_stats(user_id, bet_amount, win_amount)
    else:
        update_casino_stats(user_id, bet_amount, 0)
    
    save_data()
    
async def bsk_rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает правила игры БСК"""
    await update.message.reply_text(
        "🏀 <b>ПРАВИЛА ИГРЫ БСК (БАСКЕТБОЛ)</b>\n\n"
        "🎯 <b>Как играть:</b>\n"
        "Введите в группе: бск [сумма]\n"
        "Пример: бск 100к\n\n"
        
        "📊 <b>Механика:</b>\n"
        "• Вы делаете ставку\n"
        "• Бот имитирует бросок баскетбольного мяча\n"
        "• Если мяч попадает в кольцо - вы выигрываете x6\n"
        "• Если промах - теряете ставку\n\n"
        
        f"💰 <b>Лимиты:</b>\n"
        f"• Минимальная ставка: {BSK_CONFIG['min_bet']:,} ₽\n"
        f"• Максимальная ставка: {BSK_CONFIG['max_bet']:,} ₽\n"
        f"• Множитель: x{BSK_CONFIG['win_multiplier']}\n"
        f"• Шанс победы: {BSK_CONFIG['win_chance']*100}%\n\n"
        
        "🏆 <b>Удачи в игре!</b>",
        parse_mode='HTML'
    )                    

async def top_balance(update: Update, context: ContextTypes.DEFAULT_TYPE, is_callback=False, page=0):
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
        message_text = "❌ Нет данных для топа."
        if is_callback:
            await update.callback_query.edit_message_text(message_text)
        else:
            await update.message.reply_text(message_text)
        return
    
    # Пагинация
    items_per_page = 10
    total_pages = (len(all_users) + items_per_page - 1) // items_per_page
    current_page = min(page, total_pages - 1)
    
    start_idx = current_page * items_per_page
    end_idx = min(start_idx + items_per_page, len(all_users))
    
    message_text = f"🏆 Топ по балансу (страница {current_page + 1}/{total_pages}):\n\n"
    
    for i, (uid, user) in enumerate(all_users[start_idx:end_idx], start=start_idx + 1):
        username = user.get('username', uid)
        message_text += f"{i}. @{username} - {user['balance']:,} ₽\n"
    
    # Позиция пользователя
    user_position = None
    user_balance = None
    for i, (uid, data) in enumerate(all_users, 1):
        if int(uid) == user_id:
            user_position = i
            user_balance = data['balance']
            break
    
    if user_position is not None:
        if user_position <= 10:
            message_text += f"\n🎯 Вы на {user_position} месте!"
        else:
            message_text += (
                f"\n🎯 Ваша позиция: {user_position}\n"
                f"💰 Ваш баланс: {user_balance:,} ₽\n"
                f"📊 Отставание от этой страницы: {all_users[start_idx][1]['balance'] - user_balance:,} ₽"
            )
    else:
        message_text += "\n❌ Ваш баланс не найден в статистике"
    
    # Клавиатура для листания
    keyboard = []
    
    if total_pages > 1:
        row = []
        if current_page > 0:
            row.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"top_balance_page_{current_page - 1}"))
        
        if current_page < total_pages - 1:
            row.append(InlineKeyboardButton("Вперед ➡️", callback_data=f"top_balance_page_{current_page + 1}"))
        
        if row:
            keyboard.append(row)
    
    keyboard.append([InlineKeyboardButton("🔙 Назад к топам", callback_data="top_back")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if is_callback:
        try:
            await update.callback_query.edit_message_text(
                text=message_text,
                reply_markup=reply_markup
            )
        except:
            pass
    else:
        await update.message.reply_text(
            text=message_text,
            reply_markup=reply_markup
        )
        
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

async def shop_normal_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обычный магазин за игровую валюту"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    user = get_user_data(user_id)
    
    user_item_data = user_items.get(user_id, {})
    active_item = user_item_data.get('active_item', None)
    items_owned = user_item_data.get('items_owned', [])
    
    text = (
        "🛒 <b>ОБЫЧНЫЙ МАГАЗИН</b>\n"
        "═══════════════════\n\n"
    )
    
    keyboard = []
    
    # Отображаем доступные предметы
    for item_id, item in SHOP_ITEMS.items():
        owned = item_id in items_owned
        status = "✅ КУПЛЕНО" if owned else "❌ НЕ КУПЛЕНО"
        
        text += (
            f"{item['name']}\n"
            f"💰 Цена: {item['price']:,} ₽\n"
            f"📝 {item['description']}\n"
            f"📊 Статус: {status}\n\n"
        )
        
        # Кнопка покупки если не куплено
        if not owned:
            keyboard.append([InlineKeyboardButton(
                f"🛒 Купить {item['name']} за {item['price']:,} ₽",
                callback_data=f"shop_buy_{item_id}"
            )])
    
    # Кнопки для управления огнетушителем
    if active_item == 'fire_extinguisher':
        keyboard.append([InlineKeyboardButton(
            "❌ Снять огнетушитель",
            callback_data="shop_remove_fire_extinguisher"
        )])
    elif 'fire_extinguisher' in items_owned:
        keyboard.append([InlineKeyboardButton(
            "✅ Надеть огнетушитель",
            callback_data="shop_equip_fire_extinguisher"
        )])
    
    # Отображаем активный предмет
    if active_item:
        active_item_name = SHOP_ITEMS.get(active_item, {}).get('name', 'Неизвестный предмет')
        text += f"🎯 Активный предмет: {active_item_name}\n"
    
    text += f"\n💰 Ваш баланс: {user['balance']:,} ₽"
    
    keyboard.append([InlineKeyboardButton("🔙 НАЗАД", callback_data="shop_back_main")])
    
    await query.edit_message_text(
        text=text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )
    
    return SHOP_MENU

async def shop_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ПОЛНЫЙ обработчик кнопок магазина"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_id = str(query.from_user.id)
    user = get_user_data(user_id)
    
    print(f"shop_button_handler: {data}")
    
    # ===== ПОДТВЕРЖДЕНИЕ ПЕРЕВОДОВ =====
    if data.startswith('confirm_transfer_'):
        print(f"🔄 Передаем кнопку подтверждения перевода: {data}")
        return await confirm_transfer_callback(update, context)
    
    # ===== ПЕРЕДАЧА КНОПОК ТОПОВ =====
    if data.startswith('top_'):
        print(f"🔄 Передаем кнопку топа в обработчик: {data}")
        new_update = Update(update.update_id, callback_query=query)
        return await top_button_handler(new_update, context)
    
    # ... остальной код ...
    
    print(f"shop_button_handler: {data}")
    
    # ===== ПЕРЕДАЧА КНОПОК ТОПОВ =====
    if data.startswith('top_'):
        print(f"🔄 Передаем кнопку топа в обработчик: {data}")
        new_update = Update(update.update_id, callback_query=query)
        return await top_button_handler(new_update, context)
    
    # ===== ПЕРЕДАЧА КНОПОК РАБОТ =====
    if data.startswith('work_') or data.startswith('start_work_'):
        print(f"🔄 Передаем кнопку работы в обработчик: {data}")
        new_update = Update(update.update_id, callback_query=query)
        return await work_callback(new_update, context)
    
    # ===== ПЕРЕДАЧА КНОПОК БИЗНЕСОВ =====
    if data.startswith('business_'):
        print(f"🔄 Передаем кнопку бизнеса в обработчик: {data}")
        new_update = Update(update.update_id, callback_query=query)
        return await business_button_handler(new_update, context)
    
    # ===== ПЕРЕДАЧА КНОПОК БАНКА =====
    if data.startswith('bank_') or data.startswith('invest_'):
        print(f"🔄 Передаем кнопку банка в обработчик: {data}")
        new_update = Update(update.update_id, callback_query=query)
        return await bank_button_handler(new_update, context)
    
    # ===== ПЕРЕДАЧА КНОПОК БОКСОВ =====
    if data.startswith('box_') or data.startswith('premium_box_') or data.startswith('daily_box_'):
        print(f"🔄 Передаем кнопку боксов в обработчик: {data}")
        new_update = Update(update.update_id, callback_query=query)
        return await box_button_handler(new_update, context)
    
    # ===== ПЕРЕДАЧА КНОПОК ТРЕЙДОВ =====
    if data.startswith('trade_'):
        print(f"🔄 Передаем кнопку трейдов в обработчик: {data}")
        new_update = Update(update.update_id, callback_query=query)
        return await trade_button_handler(new_update, context)
    
    # ===== ПЕРЕДАЧА КНОПОК БАНД =====
    if data.startswith('gang_'):
        print(f"🔄 Передаем кнопку банд в обработчик: {data}")
        new_update = Update(update.update_id, callback_query=query)
        return await gang_button_handler(new_update, context)
    
    # ===== ПЕРЕДАЧА КНОПОК КАЗИНО =====
    if data.startswith('bet:'):
        print(f"🔄 Передаем кнопку казино в обработчик: {data}")
        new_update = Update(update.update_id, callback_query=query)
        return await handle_bet_type(new_update, context)
    
    # ===== ПЕРЕДАЧА КНОПОК PVP =====
    if data.startswith('pvp_'):
        print(f"🔄 Передаем кнопку PvP в обработчик: {data}")
        if data.startswith('pvp_accept_'):
            return await pvp_accept(update, context)
        elif data.startswith('pvp_decline_'):
            return await pvp_decline(update, context)
    
    # ===== ГЛАВНОЕ МЕНЮ =====
    if data == "shop_back_main":
        return await shop_menu(update, context)
    
    # ===== ОБЫЧНЫЙ МАГАЗИН =====
    if data == "shop_normal":
        return await shop_normal_menu(update, context)
    
    # ===== МАГАЗИН РАСХОДНИКОВ =====
    if data == "shop_consumables":
        return await shop_consumables_menu(update, context)
    
    # ===== ДОНАТ МАГАЗИН =====
    if data == "shop_token":
        return await shop_token_menu(update, context)
    
    # ===== ПОКУПКА ЗА ТОКЕНЫ =====
    if data.startswith("token_buy_"):
        return await token_buy_handler(update, context)
    
    # ===== ПОКУПКА РАСХОДНИКОВ =====
    if data.startswith("consumables_buy_"):
        return await consumables_buy(update, context)
    
    # ===== ИНВЕНТАРЬ РАСХОДНИКОВ =====
    if data == "consumables_inventory":
        return await consumables_inventory(update, context)
    
    # ===== ПРОДАЖА КОЙНА =====
    if data == "sell_coin":
        return await sell_coin_handler(update, context)
    
    # ===== ОБМЕН КОЙНА =====
    if data == "consumables_sell_coin":
        return await consumables_sell_coin(update, context)
    
    # ===== ПОДАРКИ =====
    if data.startswith("gift_select_"):
        return await gift_select_friend(update, context)
    
    if data.startswith("gift_send_"):
        return await gift_send(update, context)
    
    # ===== ПОКУПКА ОГНЕТУШИТЕЛЯ =====
    if data == "shop_buy_fire_extinguisher":
        item = SHOP_ITEMS['fire_extinguisher']
        if user['balance'] >= item['price']:
            user['balance'] -= item['price']
            
            if user_id not in user_items:
                user_items[user_id] = {'items_owned': [], 'active_item': None}
            
            if 'fire_extinguisher' not in user_items[user_id]['items_owned']:
                user_items[user_id]['items_owned'].append('fire_extinguisher')
            
            save_data()
            save_user_items()
            
            await query.answer(f"✅ Вы купили огнетушитель за {item['price']:,} ₽", show_alert=True)
        else:
            await query.answer(f"❌ Недостаточно средств! Нужно {item['price']:,} ₽", show_alert=True)
        
        return await shop_normal_menu(update, context)
    
    # ===== НАДЕТЬ ОГНЕТУШИТЕЛЬ =====
    if data == "shop_equip_fire_extinguisher":
        if user_id in user_items and 'fire_extinguisher' in user_items[user_id].get('items_owned', []):
            user_items[user_id]['active_item'] = 'fire_extinguisher'
            save_user_items()
            await query.answer("✅ Огнетушитель надет!", show_alert=True)
        else:
            await query.answer("❌ У вас нет этого предмета!", show_alert=True)
        
        return await shop_normal_menu(update, context)
    
    # ===== СНЯТЬ ОГНЕТУШИТЕЛЬ =====
    if data == "shop_remove_fire_extinguisher":
        if user_id in user_items:
            user_items[user_id]['active_item'] = None
            save_user_items()
            await query.answer("✅ Огнетушитель снят!", show_alert=True)
        
        return await shop_normal_menu(update, context)
    
    # ===== НАЗАД (ЗАПАСНОЙ) =====
    if data == "shop_back":
        return await shop_menu(update, context)
    
    print(f"⚠️ Неизвестная кнопка в магазине: {data}")
    return await shop_menu(update, context)
    
async def show_profile_with_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает профиль с фото (как функция profile, но без MessageHandler)"""
    user_id = str(update.effective_user.id)
    user = get_user_data(user_id)
    username = user.get('username') or update.effective_user.username or update.effective_user.full_name
    
    total_income = sum(BUSINESS_TYPES.get(i, {}).get('income', 0) for i in range(1, user.get('business_count', 0) + 1))
    
    first_seen = datetime.now()
    for action in ['last_taxi_time', 'last_business_income', 'last_accountant_date']:
        if user.get(action):
            action_time = datetime.fromisoformat(user[action]) if isinstance(user[action], str) else user[action]
            if action_time < first_seen:
                first_seen = action_time
    
    days_in_game = (datetime.now() - first_seen).days
    
    profile_text = (
        f"📊 Профиль @{username}\n\n"
        f"💰 Баланс: {user['balance']:,} ₽\n"
        f"🪙 Койны: {user.get('coins', 0)}\n"
        f"🏢 Бизнесы: {user.get('business_count', 0)} (Доход: {total_income:,} ₽/час)\n"
        f"📨 Рефералов: {len(user.get('referrals', []))}\n"
        f"📅 В игре: {days_in_game} дней\n\n"
        f"🔗 Реферальная ссылка:\n"
        f"https://t.me/{(await context.bot.get_me()).username}?start=ref_{user['referral_code']}"
    )
    
    # Проверяем активный предмет пользователя
    user_item_data = user_items.get(user_id, {})
    active_item = user_item_data.get('active_item')
    
    # URL фото в зависимости от предмета
    if active_item == 'fire_extinguisher':
        photo_url = "https://imgfoto.host/image/pn3rUk"  # Персонаж с огнетушителем
        profile_text += "\n\n🎯 Активный предмет: 🚒 Огнетушитель"
    else:
        # Стандартное фото профиля
        photo_url = "https://imgfoto.host/image/pisn1u"  # Обычный персонаж
    
    # Отправляем фото
    try:
        if update.callback_query:
            await update.callback_query.message.reply_photo(
                photo=photo_url,
                caption=profile_text,
                parse_mode='HTML'
            )
        else:
            await context.bot.send_photo(
                chat_id=user_id,
                photo=photo_url,
                caption=profile_text,
                parse_mode='HTML'
            )
    except Exception as e:
        logging.error(f"Ошибка отправки фото профиля: {e}")
        if update.callback_query:
            await update.callback_query.message.reply_text(profile_text, parse_mode='HTML')
        else:
            await context.bot.send_message(
                chat_id=user_id,
                text=profile_text,
                parse_mode='HTML'
            )
    
    # Возвращаемся в главное меню
    return ConversationHandler.END

async def buy_fire_extinguisher(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    user = get_user_data(user_id)
    
    item = SHOP_ITEMS['fire_extinguisher']
    
    # Проверяем, не куплен ли уже
    user_item_data = user_items.get(user_id, {})
    if 'fire_extinguisher' in user_item_data.get('items_owned', []):
        await query.answer("✅ Вы уже купили этот предмет!", show_alert=True)
        return await shop_menu(update, context)
    
    # Проверяем баланс
    if user['balance'] < item['price']:
        await query.answer(f"❌ Недостаточно средств! Нужно {item['price']:,} ₽", show_alert=True)
        return await shop_menu(update, context)
    
    # Покупка
    user['balance'] -= item['price']
    
    # Добавляем в инвентарь пользователя
    if user_id not in user_items:
        user_items[user_id] = {'items_owned': [], 'active_item': None}
    
    user_items[user_id]['items_owned'].append('fire_extinguisher')
    
    await query.edit_message_text(
        f"✅ Вы успешно купили {item['name']}!\n\n"
        f"💰 Списано: {item['price']:,} ₽\n"
        f"💳 Ваш баланс: {user['balance']:,} ₽\n\n"
        f"Теперь вы можете надеть его в магазине."
    )
    
    save_data()
    return await shop_menu(update, context)

async def equip_fire_extinguisher(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    
    user_item_data = user_items.get(user_id, {})
    
    # Проверяем, есть ли предмет
    if 'fire_extinguisher' not in user_item_data.get('items_owned', []):
        await query.answer("❌ У вас нет этого предмета!", show_alert=True)
        return await shop_menu(update, context)
    
    # Надеваем предмет
    user_items[user_id]['active_item'] = 'fire_extinguisher'
    
    await query.answer("✅ Огнетушитель надет!", show_alert=True)
    save_data()
    return await shop_menu(update, context)

async def remove_fire_extinguisher(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    
    # Снимаем предмет
    if user_id in user_items:
        user_items[user_id]['active_item'] = None
    
    await query.answer("✅ Огнетушитель снят!", show_alert=True)
    save_data()
    return await shop_menu(update, context)
    

    
async def shop_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Главное меню магазина"""
    user_id = str(update.effective_user.id)
    
    if user_id in banned_users:
        if update.callback_query:
            await update.callback_query.answer("⛔ Вы заблокированы", show_alert=True)
            return ConversationHandler.END
        else:
            await update.message.reply_text("⛔ Вы заблокированы")
            return ConversationHandler.END
    
    user = get_user_data(user_id)
    user['last_active'] = time.time()
    
    token_balance = get_token_balance(user_id)
    consumables = get_consumables(user_id)
    total_items = sum(consumables.values())
    
    text = (
        "🏪 <b>ГЛАВНЫЙ МАГАЗИН</b>\n"
        "═══════════════════\n\n"
        f"💰 Ваш баланс: {user['balance']:,} ₽\n"
        f"💎 Ваши токены: {token_balance}\n"
        f"📦 Расходников: {total_items} шт.\n\n"
        "Выберите раздел:"
    )
    
    keyboard = [
        [InlineKeyboardButton("🛒 ОБЫЧНЫЙ МАГАЗИН", callback_data="shop_normal")],
        [InlineKeyboardButton("📦 МАГАЗИН РАСХОДНИКОВ", callback_data="shop_consumables")],
        [InlineKeyboardButton("💎 ДОНАТ МАГАЗИН", callback_data="shop_token")],
        [InlineKeyboardButton("🔙 НАЗАД", callback_data="shop_back_main")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        await update.callback_query.edit_message_text(
            text=text,
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    else:
        await update.message.reply_text(
            text=text,
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    
    return SHOP_MENU
    
async def shop_consumables_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню магазина расходников"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    user = get_user_data(user_id)
    consumables = get_consumables(user_id)
    
    # Получаем количество койнов
    coins = user.get('coins', 0)
    
    text = (
        "📦 <b>МАГАЗИН РАСХОДНИКОВ</b>\n"
        "══════════════════════\n\n"
        f"💰 Ваш баланс: {user['balance']:,} ₽\n"
        f"📦 В инвентаре: {sum(consumables.values())} шт.\n"
        f"🪙 Ваши койны: {coins} шт.\n\n"
        "🎁 <b>ДОСТУПНЫЕ ТОВАРЫ:</b>\n\n"
    )
    
    for item_id, item in CONSUMABLES_SHOP.items():
        text += (
            f"{item['emoji']} <b>{item['name']}</b>\n"
            f"└ {item['description']}\n"
            f"└ 💰 Цена: {item['buy_price']:,} ₽\n\n"
        )
    
    keyboard = []
    
    # КНОПКА ПРОДАЖИ КОЙНА - ВСЕГДА ВИДНА, ЕСЛИ ЕСТЬ КОЙНЫ
    if coins > 0:
        keyboard.append([InlineKeyboardButton(
            f"💰 ПРОДАТЬ 1 КОЙН ЗА 100,000,000 ₽",
            callback_data="sell_coin"
        )])
    
    # Кнопки покупки
    for item_id, item in CONSUMABLES_SHOP.items():
        keyboard.append([InlineKeyboardButton(
            f"🛒 Купить {item['name']} за {item['buy_price']:,} ₽",
            callback_data=f"consumables_buy_{item_id}"
        )])
    
    keyboard.append([InlineKeyboardButton("📦 МОИ РАСХОДНИКИ", callback_data="consumables_inventory")])
    keyboard.append([InlineKeyboardButton("🔙 НАЗАД", callback_data="shop_back_main")])
    
    await query.edit_message_text(
        text=text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )
    
    return SHOP_MENU
    
async def sell_coin_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка нажатия кнопки продажи койна"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    user = get_user_data(user_id)
    
    if user.get('coins', 0) > 0:
        user['coins'] = user.get('coins', 0) - 1
        user['balance'] += 100_000_000
        save_data()
        await query.answer("✅ +100,000,000 ₽! Койн продан!", show_alert=True)
    else:
        await query.answer("❌ У вас нет койнов!", show_alert=True)
    
    # Возвращаемся в магазин
    return await shop_consumables_menu(update, context)    

async def consumables_buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Покупка расходника"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    item_id = query.data.replace("consumables_buy_", "")
    item = CONSUMABLES_SHOP.get(item_id)
    
    if not item:
        await query.answer("❌ Товар не найден!", show_alert=True)
        return SHOP_MENU
    
    user = get_user_data(user_id)
    
    if user['balance'] < item['buy_price']:
        await query.answer(f"❌ Недостаточно средств! Нужно {item['buy_price']:,} ₽", show_alert=True)
        return SHOP_MENU
    
    # Списываем деньги
    user['balance'] -= item['buy_price']
    
    # Добавляем расходник
    add_consumable(user_id, item_id)
    
    save_data()
    
    await query.answer(f"✅ Вы купили {item['name']}!", show_alert=True)
    return await shop_consumables_menu(update, context)

async def consumables_inventory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Инвентарь расходников"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    consumables = get_consumables(user_id)
    
    # ДЛЯ ОТЛАДКИ - посмотрим, что в инвентаре
    logging.info(f"📦 Инвентарь {user_id}: {consumables}")
    
    if not consumables:
        text = "📦 <b>ВАШ ИНВЕНТАРЬ ПУСТ</b>\n\nКупите расходники в магазине!"
        keyboard = [[InlineKeyboardButton("🔙 НАЗАД", callback_data="shop_consumables")]]
    else:
        text = "📦 <b>ВАШИ РАСХОДНИКИ</b>\n═══════════════════\n\n"
        keyboard = []
        
        for item_id, count in consumables.items():
            item = CONSUMABLES_SHOP.get(item_id, {})
            if item:
                text += f"{item['emoji']} <b>{item['name']}</b> — {count} шт.\n"
                text += f"└ {item['description']}\n\n"
                
                # ВАЖНО: Правильная проверка для койна!
                if item_id == 'coin':  # Точное название - 'coin'
                    keyboard.append([InlineKeyboardButton(
                        f"🔄 Обменять {item['name']} на 100,000,000 ₽",
                        callback_data="consumables_sell_coin"
                    )])
                elif item.get('type') == 'gift':
                    keyboard.append([InlineKeyboardButton(
                        f"🎁 Подарить {item['name']} другу",
                        callback_data=f"gift_select_{item_id}"
                    )])
                elif item.get('type') == 'boost':
                    keyboard.append([InlineKeyboardButton(
                        f"✨ Использовать {item['name']}",
                        callback_data=f"boost_use_{item_id}"
                    )])
                else:
                    # На всякий случай, для любых других предметов
                    keyboard.append([InlineKeyboardButton(
                        f"📦 Использовать {item['name']}",
                        callback_data=f"use_item_{item_id}"
                    )])
        
        keyboard.append([InlineKeyboardButton("🔙 НАЗАД", callback_data="shop_consumables")])
    
    try:
        await query.edit_message_text(
            text=text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
    except Exception as e:
        logging.error(f"Ошибка в consumables_inventory: {e}")
        await query.message.reply_text(
            text=text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
    
    return SHOP_MENU

async def consumables_sell_coin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обмен койна на деньги"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    
    if remove_consumable(user_id, 'coin'):
        user = get_user_data(user_id)
        user['balance'] += 100_000_000  # 100кк
        
        await query.edit_message_text(
            f"✅ <b>ОБМЕН УСПЕШЕН!</b>\n\n"
            f"🪙 Койн обменян на 100,000,000 ₽\n"
            f"💰 Новый баланс: {user['balance']:,} ₽",
            parse_mode='HTML'
        )
        
        # Кнопка возврата
        keyboard = [[InlineKeyboardButton("🔙 В ИНВЕНТАРЬ", callback_data="consumables_inventory")]]
        await asyncio.sleep(2)
        await query.message.reply_text(
            "Вернуться в инвентарь?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await query.answer("❌ У вас нет койнов!", show_alert=True)
    
    return SHOP_MENU
    
# Хранилище подарков для друзей
pending_gifts = {}  # {gift_id: {'from': user_id, 'to': user_id, 'item': item_id, 'time': timestamp}}

async def gift_select_friend(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выбор друга для подарка"""
    query = update.callback_query
    await query.answer()
    
    item_id = query.data.replace("gift_select_", "")
    context.user_data['gift_item'] = item_id
    
    user_id = str(query.from_user.id)
    user_friends = friends.get(user_id, [])
    
    if not user_friends:
        await query.edit_message_text(
            "❌ У вас нет друзей! Добавьте друзей командой /friend"
        )
        return SHOP_MENU
    
    text = f"🎁 <b>ВЫБЕРИТЕ ДРУГА ДЛЯ ПОДАРКА</b>\n\n"
    keyboard = []
    
    for friend_id in user_friends[:10]:  # Максимум 10 друзей
        friend_data = user_data.get(friend_id, {})
        friend_name = friend_data.get('username', friend_id[-4:])
        
        keyboard.append([InlineKeyboardButton(
            f"👤 @{friend_name}",
            callback_data=f"gift_send_{friend_id}"
        )])
    
    keyboard.append([InlineKeyboardButton("🔙 НАЗАД", callback_data="consumables_inventory")])
    
    await query.edit_message_text(
        text=text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
    return SHOP_MENU

async def gift_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправка подарка другу"""
    query = update.callback_query
    await query.answer()
    
    friend_id = query.data.replace("gift_send_", "")
    user_id = str(query.from_user.id)
    item_id = context.user_data.get('gift_item')
    
    if not item_id:
        await query.answer("❌ Ошибка!", show_alert=True)
        return SHOP_MENU
    
    # Проверяем, есть ли предмет
    if not remove_consumable(user_id, item_id):
        await query.answer("❌ У вас нет этого предмета!", show_alert=True)
        return SHOP_MENU
    
    # Создаем подарок
    gift_id = secrets.token_hex(4)
    pending_gifts[gift_id] = {
        'from': user_id,
        'to': friend_id,
        'item': item_id,
        'time': time.time()
    }
    
    item = CONSUMABLES_SHOP.get(item_id, {})
    
    # Уведомление другу
    keyboard = [
        [InlineKeyboardButton("🎁 ПРИНЯТЬ", callback_data=f"gift_accept_{gift_id}")],
        [InlineKeyboardButton("❌ ОТКАЗАТЬСЯ", callback_data=f"gift_decline_{gift_id}")]
    ]
    
    try:
        await context.bot.send_message(
            chat_id=int(friend_id),
            text=(
                f"🎁 <b>ВАМ ПОДАРОК!</b>\n\n"
                f"👤 От: @{user_data[user_id].get('username', 'Друг')}\n"
                f"🎁 Подарок: {item.get('emoji', '')} {item.get('name', 'Подарок')}\n\n"
                f"У вас есть 5 минут, чтобы принять!"
            ),
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
    except:
        # Если не получилось отправить, возвращаем предмет
        add_consumable(user_id, item_id)
        await query.edit_message_text("❌ Не удалось отправить подарок. Пользователь не доступен.")
        return SHOP_MENU
    
    await query.edit_message_text(
        f"✅ Подарок отправлен!\n\n"
        f"🎁 {item.get('emoji', '')} {item.get('name', '')}\n"
        f"👤 Друг: @{user_data[friend_id].get('username', friend_id[-4:])}"
    )
    
    # Таймер на 5 минут
    context.job_queue.run_once(
        gift_timeout,
        300,
        data={'gift_id': gift_id},
        name=f"gift_{gift_id}"
    )
    
    return SHOP_MENU

async def gift_accept(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Принять подарок"""
    query = update.callback_query
    await query.answer()
    
    gift_id = query.data.replace("gift_accept_", "")
    
    if gift_id not in pending_gifts:
        await query.edit_message_text("❌ Подарок не найден или истек!")
        return
    
    gift = pending_gifts[gift_id]
    user_id = str(query.from_user.id)
    
    if user_id != gift['to']:
        await query.answer("❌ Это не ваш подарок!", show_alert=True)
        return
    
    # Добавляем предмет получателю
    item_id = gift['item']
    item = CONSUMABLES_SHOP.get(item_id, {})
    
    # Инициализируем инвентарь если нужно
    if user_id not in user_consumables:
        user_consumables[user_id] = {}
    
    # Добавляем предмет
    user_consumables[user_id][item_id] = user_consumables[user_id].get(item_id, 0) + 1
    
    # Сохраняем
    save_consumables()
    
    # Для отладки
    print(f"✅ Подарок принят: {user_id} получил {item_id}")
    print(f"📦 Теперь в инвентаре: {user_consumables[user_id]}")
    
    await query.edit_message_text(
        f"✅ <b>ПОДАРОК ПРИНЯТ!</b>\n\n"
        f"🎁 Вы получили: {item.get('emoji', '')} {item.get('name', 'Подарок')}\n"
        f"📦 Проверьте инвентарь: /consumables",
        parse_mode='HTML'
    )
    
    # Уведомляем отправителя
    try:
        from_name = user_data.get(gift['from'], {}).get('username', 'Пользователь')
        await context.bot.send_message(
            chat_id=int(gift['from']),
            text=f"✅ @{user_data[user_id].get('username', 'Пользователь')} принял ваш подарок!"
        )
    except Exception as e:
        print(f"Ошибка уведомления отправителя: {e}")
    
    del pending_gifts[gift_id]

async def gift_decline(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отказаться от подарка"""
    query = update.callback_query
    await query.answer()
    
    gift_id = query.data.replace("gift_decline_", "")
    
    if gift_id not in pending_gifts:
        await query.edit_message_text("❌ Подарок не найден!")
        return
    
    gift = pending_gifts[gift_id]
    user_id = str(query.from_user.id)
    
    if user_id != gift['to']:
        await query.answer("❌ Это не ваш подарок!", show_alert=True)
        return
    
    # Возвращаем предмет отправителю
    add_consumable(gift['from'], gift['item'])
    
    await query.edit_message_text("❌ Вы отказались от подарка.")
    
    # Уведомляем отправителя
    try:
        await context.bot.send_message(
            chat_id=int(gift['from']),
            text=f"❌ @{user_data[user_id].get('username')} отказался от вашего подарка."
        )
    except:
        pass
    
    del pending_gifts[gift_id]

async def gift_timeout(context: ContextTypes.DEFAULT_TYPE):
    """Таймаут подарка"""
    job = context.job
    gift_id = job.data['gift_id']
    
    if gift_id in pending_gifts:
        gift = pending_gifts[gift_id]
        
        # Возвращаем предмет отправителю
        add_consumable(gift['from'], gift['item'])
        
        # Уведомляем
        try:
            await context.bot.send_message(
                chat_id=int(gift['from']),
                text="⏳ Время вышло. Подарок не был принят и возвращен вам."
            )
        except:
            pass
        
        del pending_gifts[gift_id]
        
async def my_gifts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Просмотр подарков"""
    user_id = str(update.effective_user.id)
    consumables = get_consumables(user_id)
    
    gifts = {k: v for k, v in consumables.items() 
             if k in CONSUMABLES_SHOP and CONSUMABLES_SHOP[k]['type'] == 'gift'}
    
    if not gifts:
        await update.message.reply_text("🎁 У вас нет подарков для отправки.")
        return
    
    text = "🎁 <b>ВАШИ ПОДАРКИ</b>\n═══════════════\n\n"
    for item_id, count in gifts.items():
        item = CONSUMABLES_SHOP[item_id]
        text += f"{item['emoji']} {item['name']} — {count} шт.\n"
        text += f"└ {item['description']}\n\n"
    
    await update.message.reply_text(text, parse_mode='HTML')                                
    
async def shop_token_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Донат магазин за токены"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    token_balance = get_token_balance(user_id)
    
    text = (
        "💎 <b>ДОНАТ МАГАЗИН</b>\n"
        "═══════════════════\n\n"
        f"💰 Ваши токены: {token_balance}\n\n"
        "🎁 <b>ДОСТУПНЫЕ ПОКУПКИ:</b>\n\n"
    )
    
    keyboard = []
    
    for item_id, item in TOKEN_SHOP_ITEMS.items():
        can_afford = "✅" if token_balance >= item['price'] else "❌"
        text += f"{can_afford} {item['name']} — {item['price']} токенов\n"
        
        if token_balance >= item['price']:
            keyboard.append([InlineKeyboardButton(
                f"💰 Купить {item['name']} за {item['price']} токенов",
                callback_data=f"token_buy_{item_id}"
            )])
    
    keyboard.append([InlineKeyboardButton("🔙 НАЗАД", callback_data="shop_back_main")])
    
    await query.edit_message_text(
        text=text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )
    
    return SHOP_MENU

async def buy_vip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Покупка VIP статуса"""
    query = update.callback_query
    user_id = str(query.from_user.id)
    
    token_balance = get_token_balance(user_id)
    
    if token_balance < VIP_PRICE:
        await query.answer(f"❌ Недостаточно токенов! Нужно {VIP_PRICE}", show_alert=True)
        return SHOP_MENU
    
    if remove_tokens(user_id, VIP_PRICE):
        expires = time.time() + 30 * 24 * 3600
        
        vip_users[user_id] = {
            'expires': expires,
            'purchased_at': time.time(),
            'last_daily_bonus': ''
        }
        
        # ВАЖНО: ВКЛЮЧАЕМ VIP БИЗНЕС!
        user = get_user_data(user_id)
        user['vip_business'] = True  # ЭТА СТРОКА КЛЮЧЕВАЯ!
        
        save_vip()
        save_data()
        
        expiry_date = datetime.fromtimestamp(expires).strftime('%d.%m.%Y')
        
        await query.edit_message_text(
            f"👑 <b>VIP СТАТУС АКТИВИРОВАН!</b>\n\n"
            f"💰 Ежедневный бонус: 5,000,000 ₽\n"
            f"🏢 VIP бизнес: +30,000,000 ₽/час\n"
            f"📈 Бонус к доходу: +15%\n"
            f"⏳ Действует до: {expiry_date}",
            parse_mode='HTML'
        )
    else:
        await query.answer("❌ Ошибка при покупке!", show_alert=True)
    
    return SHOP_MENU

async def vip_extend(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Продление VIP статуса"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    token_balance = get_token_balance(user_id)
    
    if token_balance < VIP_PRICE:
        await query.answer(f"❌ Недостаточно токенов! Нужно {VIP_PRICE}", show_alert=True)
        return SHOP_MENU
    
    if remove_tokens(user_id, VIP_PRICE):
        # Продлеваем на 30 дней
        if user_id in vip_users:
            vip_users[user_id]['expires'] += 30 * 24 * 3600
        else:
            vip_users[user_id] = {
                'expires': time.time() + 30 * 24 * 3600,
                'premium_business': True,
                'purchased_at': time.time()
            }
        
        save_vip()
        
        expiry_date = datetime.fromtimestamp(vip_users[user_id]['expires']).strftime('%d.%m.%Y')
        
        await query.edit_message_text(
            f"✅ <b>VIP СТАТУС ПРОДЛЕН!</b>\n\n"
            f"📅 Новый срок действия: {expiry_date}\n"
            f"💎 Осталось токенов: {get_token_balance(user_id)}",
            parse_mode='HTML'
        )
    else:
        await query.answer("❌ Ошибка!", show_alert=True)
    
    return SHOP_MENU
    
async def vip_daily_bonus(context: ContextTypes.DEFAULT_TYPE):
    """Начисляет ежедневный бонус VIP пользователям"""
    current_time = time.time()
    today = datetime.now().strftime('%Y-%m-%d')
    
    for user_id, vip_data in list(vip_users.items()):
        if vip_data['expires'] > current_time:
            # Проверяем, получал ли уже сегодня
            last_bonus = vip_data.get('last_daily_bonus', '')
            
            if last_bonus != today:
                user = get_user_data(user_id)
                user['balance'] += VIP_DAILY_BONUS
                
                vip_data['last_daily_bonus'] = today
                
                try:
                    await context.bot.send_message(
                        chat_id=int(user_id),
                        text=(
                            f"👑 <b>ЕЖЕДНЕВНЫЙ VIP БОНУС</b>\n\n"
                            f"💰 Начислено: {VIP_DAILY_BONUS:,} ₽\n"
                            f"💳 Новый баланс: {user['balance']:,} ₽"
                        ),
                        parse_mode='HTML'
                    )
                except:
                    pass
    
    save_vip()
    save_data()    

async def token_buy_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка покупки за токены"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    item_id = query.data.replace("token_buy_", "")
    
    # Проверяем, если это VIP
    if item_id == 'vip':
        return await buy_vip(update, context)
    
    item = TOKEN_SHOP_ITEMS.get(item_id)
    # ... остальной код для обычных товаров ...
    
    if not item:
        await query.answer("❌ Товар не найден!", show_alert=True)
        return SHOP_MENU
    
    token_balance = get_token_balance(user_id)
    
    if token_balance < item['price']:
        await query.answer(f"❌ Недостаточно токенов! Нужно {item['price']}", show_alert=True)
        return SHOP_MENU
    
    # Списываем токены и начисляем деньги
    if remove_tokens(user_id, item['price']):
        user = get_user_data(user_id)
        user['balance'] += item['amount']
        save_data()
        
        await query.edit_message_text(
            f"✅ <b>ПОКУПКА УСПЕШНА!</b>\n\n"
            f"🎁 Товар: {item['name']}\n"
            f"💸 Потрачено: {item['price']} токенов\n"
            f"💰 Получено: {item['amount']:,} ₽\n"
            f"💳 Новый баланс: {user['balance']:,} ₽\n"
            f"💎 Осталось токенов: {get_token_balance(user_id)}",
            parse_mode='HTML'
        )
        
        # Кнопка возврата
        keyboard = [[InlineKeyboardButton("🔙 В МАГАЗИН", callback_data="shop_back_main")]]
        await asyncio.sleep(3)
        await query.message.reply_text(
            "Вернуться в магазин?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await query.answer("❌ Ошибка при списании токенов!", show_alert=True)
    
    return SHOP_MENU

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

async def dice_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Игра в кости (только для групп)"""
    # Проверяем, что это группа
    if update.message.chat.type not in ('group', 'supergroup'):
        await update.message.reply_text("❌ Эта игра доступна только в группах!")
        return
    
    user_id = update.message.from_user.id
    if user_id in banned_users:
        return
    
    # Получаем текст сообщения
    text = update.message.text.lower()
    parts = text.split()
    
    if len(parts) != 2:
        await update.message.reply_text(
            "🎲 <b>ИГРА В КОСТИ</b>\n\n"
            "Использование:\n"
            "• /dice [сумма] - бросить кости\n"
            "• кости [сумма] - тоже самое\n\n"
            "Пример: /dice 100к\n\n"
            "Правила:\n"
            "• Кидаются 2 кубика (1-6)\n"
            "• Если сумма > 7 - выигрыш x2\n"
            "• Если сумма = 7 - возврат ставки\n"
            "• Если сумма < 7 - проигрыш",
            parse_mode='HTML'
        )
        return
    
    # Парсим сумму
    bet_amount_str = parts[1]
    bet_amount = parse_bet_amount(bet_amount_str)
    
    if not bet_amount or bet_amount <= 0:
        await update.message.reply_text("❌ Неверная сумма!")
        return
    
    if bet_amount < 1000:
        await update.message.reply_text("❌ Минимальная ставка: 1,000 ₽")
        return
    
    # Получаем данные пользователя
    user = get_user_data(user_id)
    username = user.get('username') or update.message.from_user.username or update.message.from_user.full_name
    
    if bet_amount > user['balance']:
        await update.message.reply_text(f"❌ Недостаточно средств! Баланс: {user['balance']:,} ₽")
        return
    
    # Списываем ставку
    user['balance'] -= bet_amount
    old_balance = user['balance']
    
    # Бросаем кости
    dice1 = random.randint(1, 6)
    dice2 = random.randint(1, 6)
    total = dice1 + dice2
    
    # Отправляем результат
    result_text = (
        f"🎲 <b>ИГРА В КОСТИ</b>\n\n"
        f"👤 Игрок: @{username}\n"
        f"💰 Ставка: {bet_amount:,} ₽\n\n"
        f"🎲 Первый кубик: {dice1}\n"
        f"🎲 Второй кубик: {dice2}\n"
        f"📊 Сумма: {total}\n\n"
    )
    
    # Определяем результат
    if total > 7:
        win_amount = bet_amount * 2
        user['balance'] += win_amount
        result_text += (
            f"🎉 <b>ВЫИГРЫШ!</b>\n"
            f"💰 Получено: {win_amount:,} ₽ (x2)\n"
            f"📈 Чистая прибыль: {win_amount - bet_amount:,} ₽"
        )
    elif total == 7:
        user['balance'] += bet_amount
        result_text += (
            f"🤝 <b>НИЧЬЯ</b>\n"
            f"💰 Ставка возвращена"
        )
    else:
        result_text += (
            f"😢 <b>ПРОИГРЫШ</b>\n"
            f"❌ Потеряно: {bet_amount:,} ₽"
        )
    
    result_text += f"\n\n💰 Баланс: {user['balance']:,} ₽"
    
    await update.message.reply_text(result_text, parse_mode='HTML')
    save_data()

async def handle_group_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик сообщений в группах"""
    # Проверяем, что это сообщение, а не callback query
    if not update.message:
        return
    
    # Проверяем, что это группа
    if update.message.chat.type not in ('group', 'supergroup'):
        return
    
    user_id = update.message.from_user.id
    user_id_str = str(user_id)
    
    # Проверяем бан
    if user_id_str in banned_users:
        return
    
    text = update.message.text.strip()
    
    print(f"📱 Групповое сообщение: '{text}' от {user_id}")
    
    # ==================== КРАШ-ИГРА ====================
    if text.lower().startswith('краш ') or text.lower().startswith('/crash '):
        try:
            user = get_user_data(user_id)
            
            if not user.get('username'):
                await update.message.reply_text(
                    "❌ У вас не установлен никнейм!\n"
                    "Напишите боту в ЛС: /set_nick [ваш ник]"
                )
                return
            
            parts = text.split()
            if len(parts) != 2:
                await update.message.reply_text(
                    "💥 <b>КРАШ-ИГРА</b>\n\n"
                    "Использование:\n"
                    "• /crash [сумма] - начать игру\n"
                    "• краш [сумма] - тоже самое\n\n"
                    "Пример: /crash 100к\n\n"
                    "Правила:\n"
                    "• Множитель растет каждый шаг\n"
                    "• Забери деньги ДО краша\n"
                    "• Если краш - теряешь всё!\n\n"
                    f"💰 Мин. ставка: 1,000 ₽\n"
                    f"💰 Макс. ставка: 100,000,000 ₽",
                    parse_mode='HTML'
                )
                return
            
            # Парсим сумму
            bet_amount_str = parts[1]
            bet_amount = parse_bet_amount(bet_amount_str)
            
            if not bet_amount or bet_amount <= 0:
                await update.message.reply_text("❌ Неверная сумма!")
                return
            
            if bet_amount < 1000:
                await update.message.reply_text("❌ Минимальная ставка: 1,000 ₽")
                return
            
            if bet_amount > 100_000_000:
                await update.message.reply_text("❌ Максимальная ставка: 100,000,000 ₽")
                return
            
            if bet_amount > user['balance']:
                await update.message.reply_text(f"❌ Недостаточно средств! Баланс: {user['balance']:,} ₽")
                return
            
            username = user['username']
            
            # Списываем ставку
            user['balance'] -= bet_amount
            save_data()
            
            # Создаем игру
            game_id = f"crash_{user_id}_{int(time.time())}"
            
            if 'crash_games' not in context.bot_data:
                context.bot_data['crash_games'] = {}
            
            context.bot_data['crash_games'][game_id] = {
                'user_id': user_id,
                'username': username,
                'bet': bet_amount,
                'multiplier': 1.0,
                'active': True,
                'cashed_out': False,
                'message_id': None,
                'chat_id': update.message.chat_id
            }
            
            # Отправляем стартовое сообщение
            message = await update.message.reply_text(
                f"💥 <b>КРАШ-ИГРА</b>\n\n"
                f"👤 Игрок: @{username}\n"
                f"💰 Ставка: {bet_amount:,} ₽\n"
                f"📈 Множитель: <b>1.00x</b>\n\n"
                f"🔄 Игра началась! Множитель растет...\n"
                f"👇 Нажмите кнопку, чтобы забрать деньги",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("💰 ЗАБРАТЬ", callback_data=f"crash_cashout_{game_id}")
                ]]),
                parse_mode='HTML'
            )
            
            context.bot_data['crash_games'][game_id]['message_id'] = message.message_id
            
            # Запускаем игровой цикл
            # Запускаем игровой цикл с chat_id
            asyncio.create_task(crash_game_loop(context, game_id, update.message.chat_id))
            
            return
            
        except Exception as e:
            logging.error(f"Ошибка в краш-игре: {e}")
            await update.message.reply_text("⚠️ Произошла ошибка")
            return
    
    # ==================== БСК (БАСКЕТБОЛ) ====================
    if text.lower().startswith('бск '):
        try:
            user = get_user_data(user_id)
            
            if not user.get('username'):
                await update.message.reply_text(
                    "❌ У вас не установлен никнейм!\n"
                    "Напишите боту в ЛС: /set_nick [ваш ник]"
                )
                return
            
            parts = text.split()
            if len(parts) != 2:
                await update.message.reply_text(
                    "❌ Используйте: бск [сумма]\n"
                    "Пример: бск 100к\n"
                    "• бск все - поставить весь баланс"
                )
                return
            
            bet_amount_str = parts[1].lower()
            
            if bet_amount_str in ['все', 'алл', 'вб', 'весь', 'весь баланс', 'all', 'вабанк']:
                bet_amount = user['balance']
                if bet_amount <= 0:
                    await update.message.reply_text("❌ У вас нет денег для ставки!")
                    return
            else:
                bet_amount = parse_bet_amount(bet_amount_str)
                if not bet_amount or bet_amount <= 0:
                    await update.message.reply_text("❌ Неверная сумма!")
                    return
            
            if bet_amount < 1000:
                await update.message.reply_text("❌ Минимальная ставка: 1,000 ₽")
                return
            
            if bet_amount > 100_000_000:
                await update.message.reply_text("❌ Максимальная ставка: 100,000,000 ₽")
                return
            
            if bet_amount > user['balance']:
                await update.message.reply_text(
                    f"❌ Недостаточно средств!\n"
                    f"Ваш баланс: {user['balance']:,} ₽"
                )
                return
            
            username = user['username']
            old_balance = user['balance']
            
            # Списываем ставку
            user['balance'] -= bet_amount
            
            await update.message.reply_text(
                f"🏀 <b>БАСКЕТБОЛ</b>\n\n"
                f"👤 Игрок: @{username}\n"
                f"💰 Ставка: {bet_amount:,} ₽\n"
                f"🎯 Множитель: x6\n\n"
                f"Бросок... 🏀",
                parse_mode='HTML'
            )
            
            await asyncio.sleep(2)
            
            win = random.random() < 0.4
            
            if win:
                win_amount = bet_amount * 6
                user['balance'] += win_amount
                
                await update.message.reply_text(
                    f"🏀 <b>ПОПАДАНИЕ! 🔥</b>\n\n"
                    f"👤 Игрок: @{username}\n"
                    f"💰 Ставка: {bet_amount:,} ₽\n"
                    f"💵 ВЫИГРЫШ: {win_amount:,} ₽ (x6)\n"
                    f"📈 Чистая прибыль: {win_amount - bet_amount:,} ₽\n\n"
                    f"💰 Было: {old_balance:,} ₽\n"
                    f"💰 Стало: {user['balance']:,} ₽\n\n"
                    f"🎉 МЯЧ В КОЛЬЦЕ!",
                    parse_mode='HTML'
                )
                
                update_casino_stats(user_id, bet_amount, win_amount)
            else:
                await update.message.reply_text(
                    f"🏀 <b>ПРОМАХ</b>\n\n"
                    f"👤 Игрок: @{username}\n"
                    f"💰 Ставка: {bet_amount:,} ₽\n"
                    f"❌ Проигрыш: {bet_amount:,} ₽\n\n"
                    f"💰 Было: {old_balance:,} ₽\n"
                    f"💰 Стало: {user['balance']:,} ₽\n\n"
                    f"😢 Мяч не попал...",
                    parse_mode='HTML'
                )
                
                update_casino_stats(user_id, bet_amount, 0)
            
            save_data()
            return
            
        except Exception as e:
            logging.error(f"Ошибка в БСК: {e}")
            await update.message.reply_text("⚠️ Произошла ошибка в игре")
            return
    
    # ==================== РУЛЕТКА ====================
    if text.lower().startswith('рул '):
        try:
            user = get_user_data(user_id)
            
            if not user.get('username'):
                await update.message.reply_text(
                    "❌ У вас не установлен никнейм!\n"
                    "Напишите боту в ЛС: /set_nick [ваш ник]"
                )
                return
            
            parts = text.split()
            if len(parts) < 3:
                await update.message.reply_text(
                    "❌ Используйте: рул [тип] [сумма/половина]\n\n"
                    "🎯 <b>ВСЕ ТИПЫ СТАВОК:</b>\n\n"
                    
                    "🎨 <b>ЦВЕТА (x2):</b>\n"
                    "• красное, крас\n"
                    "• черное, чер\n\n"
                    
                    "🔢 <b>ЧЕТ/НЕЧЕТ (x2):</b>\n"
                    "• четное, чет\n"
                    "• нечетное, нечет, неч\n\n"
                    
                    "📊 <b>ДЮЖИНЫ (x3):</b>\n"
                    "• 1-12, 1_12\n"
                    "• 13-24, 13_24\n"
                    "• 25-36, 25_36\n\n"
                    
                    "📏 <b>РЯДЫ (x3):</b>\n"
                    "• 1ряд, ряд1\n"
                    "• 2ряд, ряд2\n"
                    "• 3ряд, ряд3\n\n"
                    
                    "🎯 <b>ЧИСЛА (x36):</b>\n"
                    "• 0, 1, 2, 3... 36\n\n"
                    
                    "💰 <b>СУММА:</b>\n"
                    "• 100к, 1м, 500кк\n"
                    "• все, алл, вб - весь баланс\n"
                    "• половина, пол - 50% от баланса",
                    parse_mode='HTML'
                )
                return
            
            bet_type = parts[1].lower()
            bet_amount_str = ' '.join(parts[2:]).lower()
            
            # Поддержка разных форматов
            if bet_type in ['1-12', '1_12']:
                bet_type = 'dozen1'
            elif bet_type in ['13-24', '13_24']:
                bet_type = 'dozen2'
            elif bet_type in ['25-36', '25_36']:
                bet_type = 'dozen3'
            elif bet_type in ['1ряд', 'ряд1']:
                bet_type = 'row1'
            elif bet_type in ['2ряд', 'ряд2']:
                bet_type = 'row2'
            elif bet_type in ['3ряд', 'ряд3']:
                bet_type = 'row3'
            
            # Маппинг типов ставок
            bet_types = {
                'красное': 'red', 'крас': 'red', 'кра': 'red',
                'черное': 'black', 'чёрное': 'black', 'чер': 'black',
                'четное': 'even', 'чётное': 'even', 'чет': 'even',
                'нечетное': 'odd', 'нечётное': 'odd', 'нечет': 'odd', 'неч': 'odd',
                'зеро': 'zero', 'zero': 'zero', '0': 'zero',
                'row1': 'row1', 'row2': 'row2', 'row3': 'row3',
                'dozen1': 'dozen1', 'dozen2': 'dozen2', 'dozen3': 'dozen3',
            }
            
            # Проверка на число
            is_number = False
            number_bet = 0
            if bet_type.isdigit():
                number = int(bet_type)
                if 0 <= number <= 36:
                    is_number = True
                    number_bet = number
                    bet_type = 'number'
            elif bet_type not in bet_types:
                await update.message.reply_text(
                    "❌ Неверный тип ставки!\n"
                    "Доступно: красное, черное, чет, неч, 1ряд, 2ряд, 3ряд, 1-12, 13-24, 25-36, число (0-36)"
                )
                return
            
            if not is_number:
                bet_type = bet_types[bet_type]
            
            # Определяем сумму ставки
            if bet_amount_str in ['половина', 'пол']:
                bet_amount = user['balance'] // 2
                if bet_amount <= 0:
                    await update.message.reply_text("❌ У вас нет денег для ставки!")
                    return
                half_text = f" (50% от {user['balance']:,} ₽)"
            elif bet_amount_str in ['все', 'алл', 'вб', 'весь', 'весь баланс', 'all', 'вабанк']:
                bet_amount = user['balance']
                if bet_amount <= 0:
                    await update.message.reply_text("❌ У вас нет денег для ставки!")
                    return
                half_text = ""
            else:
                bet_amount = parse_bet_amount(bet_amount_str)
                if not bet_amount or bet_amount <= 0:
                    await update.message.reply_text("❌ Неверная сумма!")
                    return
                half_text = ""
            
            if bet_amount < 1000:
                await update.message.reply_text("❌ Минимальная ставка: 1,000 ₽")
                return
            
            if bet_amount > user['balance']:
                await update.message.reply_text(
                    f"❌ Недостаточно средств!\n"
                    f"Баланс: {user['balance']:,} ₽"
                )
                return
            
            username = user['username']
            old_balance = user['balance']
            
            # СПИСЫВАЕМ СТАВКУ
            user['balance'] -= bet_amount
            
            # Генерируем число
            win_number = random.randint(0, 36)
            
            # Определяем цвета
            red_numbers = {1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36}
            black_numbers = {2,4,6,8,10,11,13,15,17,20,22,24,26,28,29,31,33,35}
            
            # Ряды
            row1_numbers = {1,4,7,10,13,16,19,22,25,28,31,34}
            row2_numbers = {2,5,8,11,14,17,20,23,26,29,32,35}
            row3_numbers = {3,6,9,12,15,18,21,24,27,30,33,36}
            
            # Дюжины
            dozen1_numbers = set(range(1, 13))
            dozen2_numbers = set(range(13, 25))
            dozen3_numbers = set(range(25, 37))
            
            is_red = win_number in red_numbers
            is_black = win_number in black_numbers
            is_even = win_number % 2 == 0 and win_number != 0
            is_odd = win_number % 2 == 1
            is_zero = win_number == 0
            is_row1 = win_number in row1_numbers
            is_row2 = win_number in row2_numbers
            is_row3 = win_number in row3_numbers
            is_dozen1 = win_number in dozen1_numbers
            is_dozen2 = win_number in dozen2_numbers
            is_dozen3 = win_number in dozen3_numbers
            
            # Определяем цвет
            if is_zero:
                color = "⚪ (зеро)"
            elif is_red:
                color = "🔴 (красное)"
            else:
                color = "⚫ (черное)"
            
            # Дополнительная информация
            extra_info = []
            if is_row1:
                extra_info.append("1-й ряд")
            elif is_row2:
                extra_info.append("2-й ряд")
            elif is_row3:
                extra_info.append("3-й ряд")
            
            if is_dozen1:
                extra_info.append("1-12")
            elif is_dozen2:
                extra_info.append("13-24")
            elif is_dozen3:
                extra_info.append("25-36")
            
            extra_text = f" ({', '.join(extra_info)})" if extra_info else ""
            
            win = False
            multiplier = 1
            
            # Проверяем выигрыш
            if is_number and win_number == number_bet:
                win = True
                multiplier = 36
            elif bet_type == 'zero' and is_zero:
                win = True
                multiplier = 36
            elif bet_type == 'red' and is_red:
                win = True
                multiplier = 2
            elif bet_type == 'black' and is_black:
                win = True
                multiplier = 2
            elif bet_type == 'even' and is_even:
                win = True
                multiplier = 2
            elif bet_type == 'odd' and is_odd:
                win = True
                multiplier = 2
            elif bet_type == 'row1' and is_row1:
                win = True
                multiplier = 3
            elif bet_type == 'row2' and is_row2:
                win = True
                multiplier = 3
            elif bet_type == 'row3' and is_row3:
                win = True
                multiplier = 3
            elif bet_type == 'dozen1' and is_dozen1:
                win = True
                multiplier = 3
            elif bet_type == 'dozen2' and is_dozen2:
                win = True
                multiplier = 3
            elif bet_type == 'dozen3' and is_dozen3:
                win = True
                multiplier = 3
            
            # Формируем текст типа ставки
            if is_number:
                type_text = f"число {number_bet}"
            elif bet_type == 'red':
                type_text = "красное"
            elif bet_type == 'black':
                type_text = "черное"
            elif bet_type == 'even':
                type_text = "четное"
            elif bet_type == 'odd':
                type_text = "нечетное"
            elif bet_type == 'zero':
                type_text = "зеро"
            elif bet_type == 'row1':
                type_text = "1-й ряд"
            elif bet_type == 'row2':
                type_text = "2-й ряд"
            elif bet_type == 'row3':
                type_text = "3-й ряд"
            elif bet_type == 'dozen1':
                type_text = "1-12"
            elif bet_type == 'dozen2':
                type_text = "13-24"
            elif bet_type == 'dozen3':
                type_text = "25-36"
            else:
                type_text = bet_type
            
            if win:
                win_amount = bet_amount * multiplier
                user['balance'] += win_amount
                update_casino_stats(user_id, bet_amount, win_amount)
                
                result_text = (
                    f"🎲 <b>РУЛЕТКА - ВЫИГРЫШ!</b>\n\n"
                    f"👤 Игрок: @{username}\n"
                    f"🎰 Выпало: {win_number} {color}{extra_text}\n"
                    f"🎯 Ставка: {bet_amount:,} ₽ на {type_text}{half_text}\n"
                    f"💰 Множитель: x{multiplier}\n"
                    f"💵 ВЫИГРЫШ: {win_amount:,} ₽\n"
                    f"📈 Чистая прибыль: {win_amount - bet_amount:,} ₽\n\n"
                    f"💰 Было: {old_balance:,} ₽\n"
                    f"💰 Стало: {user['balance']:,} ₽\n\n"
                    f"🎉 ПОЗДРАВЛЯЕМ!"
                )
            else:
                update_casino_stats(user_id, bet_amount, 0)
                
                result_text = (
                    f"🎲 <b>РУЛЕТКА - ПРОИГРЫШ</b>\n\n"
                    f"👤 Игрок: @{username}\n"
                    f"🎰 Выпало: {win_number} {color}{extra_text}\n"
                    f"🎯 Ставка: {bet_amount:,} ₽ на {type_text}{half_text}\n"
                    f"❌ Проигрыш: {bet_amount:,} ₽\n\n"
                    f"💰 Было: {old_balance:,} ₽\n"
                    f"💰 Стало: {user['balance']:,} ₽\n\n"
                    f"😢 Повезет в следующий раз!"
                )
            
            await update.message.reply_text(
                result_text,
                parse_mode='HTML'
            )
            
            save_data()
            return
            
        except Exception as e:
            logging.error(f"Ошибка в рулетке: {e}")
            await update.message.reply_text("⚠️ Произошла ошибка в игре")
            return
    
    # ==================== КОМАНДА "Я" ====================
    if text.lower() == 'я':
        try:
            user = get_user_data(user_id)
            
            # Получаем username
            username = user.get('username')
            if not username:
                username = update.message.from_user.username
            if not username:
                username = update.message.from_user.full_name.replace(' ', '_')
            
            balance = user['balance']
            
            # Массив рандомных приветствий
            greetings = [
                f"здарова @{username}, на балансе у тебя {balance:,} ₽",
                f"ку @{username}, на бале у тя {balance:,} ₽",
                f"привет @{username}! баланс: {balance:,} ₽",
                f"здорово @{username}! у тебя {balance:,} на счету",
                f"йо @{username}, твой баланс: {balance:,} ₽",
                f"добро пожаловать @{username}! баланс: {balance:,} ₽",
                f"салам @{username}! на счету {balance:,} ₽",
                f"хеллоу @{username}! денег: {balance:,} ₽",
                f"о, @{username} зашел! баланс: {balance:,} ₽",
                f"приветствую, @{username}! на балансе {balance:,} ₽"
            ]
            
            # Выбираем случайное приветствие
            greeting = random.choice(greetings)
            
            # Получаем информацию о фото пользователя
            photo_info = get_user_photo_info(user_id_str)
            photo_path = photo_info["path"]
            
            # Отправляем фото с приветствием
            try:
                if os.path.exists(photo_path):
                    with open(photo_path, 'rb') as photo_file:
                        await context.bot.send_photo(
                            chat_id=update.message.chat_id,
                            photo=photo_file,
                            caption=greeting,
                            parse_mode='HTML'
                        )
                else:
                    # Если нет фото, отправляем только текст
                    await update.message.reply_text(greeting)
            except Exception as e:
                logging.error(f"Ошибка отправки фото в группе: {e}")
                await update.message.reply_text(greeting)
            
            return
            
        except Exception as e:
            logging.error(f"Ошибка в команде 'я': {e}")
            await update.message.reply_text("⚠️ Произошла ошибка")
            return
    
    # ==================== КОМАНДА "ТОП" ====================
    if text.lower() == 'топ':
        try:
            keyboard = [
                [InlineKeyboardButton("🏆 По балансу", callback_data="top_balance")],
                [InlineKeyboardButton("📨 По рефералам", callback_data="top_referrals")],
                [InlineKeyboardButton("🪙 По койнам", callback_data="top_coins")],
                [InlineKeyboardButton("🎰 По сливу", callback_data="top_losses")]
            ]
            
            await update.message.reply_text(
                "📊 <b>ВЫБЕРИТЕ ТОП</b>",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='HTML'
            )
            return
            
        except Exception as e:
            logging.error(f"Ошибка в команде 'топ': {e}")
            await update.message.reply_text("⚠️ Произошла ошибка")
            return

async def trade_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало трейда через команду /trade @username"""
    user_id = str(update.effective_user.id)
    
    if user_id in banned_users:
        await update.message.reply_text("⛔ Вы заблокированы и не можете использовать бота.")
        return
    
    if not context.args:
        await update.message.reply_text(
            "Использование: /trade @username\n\n"
            "Примеры:\n"
            "/trade @username - начать трейд с пользователем\n"
            "/trade my_offers - посмотреть мои предложения\n"
            "/trade incoming - входящие предложения"
        )
        return
    
    arg = context.args[0].lower()
    
    if arg == "my_offers":
        return await show_my_trade_offers_simple(update, context)
    elif arg == "incoming":
        return await show_incoming_offers_simple(update, context)
    elif arg.startswith('@'):
        target_username = arg[1:]  # Убираем @
        return await start_new_trade(update, context, target_username)
    else:
        # Возможно это username без @
        return await start_new_trade(update, context, arg)

async def start_new_trade(update: Update, context: ContextTypes.DEFAULT_TYPE, target_username: str):
    """Начать новый трейд с пользователем"""
    user_id = str(update.effective_user.id)
    user = get_user_data(user_id)
    
    # Ищем целевого пользователя
    target_user = None
    target_user_id = None
    
    for uid, u_data in user_data.items():
        if u_data.get('username', '').lower() == target_username.lower():
            target_user = u_data
            target_user_id = str(uid)
            break
    
    if not target_user:
        await update.message.reply_text(f"❌ Пользователь @{target_username} не найден!")
        return
    
    if target_user_id == user_id:
        await update.message.reply_text("❌ Нельзя обмениваться с самим собой!")
        return
    
    # Проверяем, нет ли уже активного трейда
    for trade_id, trade in active_trades.items():
        if (trade['user1'] == user_id and trade['user2'] == target_user_id) or \
           (trade['user1'] == target_user_id and trade['user2'] == user_id):
            if not trade.get('completed'):
                await update.message.reply_text("❌ У вас уже есть активный трейд с этим пользователем!")
                return
    
    # Создаем новый трейд
    trade_id = secrets.token_hex(8)
    active_trades[trade_id] = {
        'user1': user_id,
        'user2': target_user_id,
        'user1_name': user.get('username', user_id),
        'user2_name': target_user.get('username', target_user_id),
        'user1_items': {'money': 0, 'coins': 0},
        'user2_items': {'money': 0, 'coins': 0},
        'user1_confirmed': False,
        'user2_confirmed': False,
        'created_at': time.time(),
        'completed': False
    }
    
    save_data()
    
    # Отправляем уведомления
    await update.message.reply_text(
        f"✅ Трейд создан с @{target_username}!\n\n"
        f"ID трейда: {trade_id}\n"
        f"Теперь добавьте предметы командой:\n"
        f"/add_to_trade {trade_id} <сумма> <тип>\n\n"
        f"Примеры:\n"
        f"/add_to_trade {trade_id} 1000000 money\n"
        f"/add_to_trade {trade_id} 50 coins\n\n"
        f"После добавления предметов подтвердите трейд:"
        f"/confirm_trade {trade_id}"
    )
    
    try:
        await context.bot.send_message(
            chat_id=int(target_user_id),
            text=f"📥 @{user.get('username', user_id)} предложил вам трейд!\n\n"
                 f"ID трейда: {trade_id}\n"
                 f"Чтобы добавить предметы:\n"
                 f"/add_to_trade {trade_id} <сумма> <тип>\n\n"
                 f"Для принятия:\n"
                 f"/confirm_trade {trade_id}"
        )
    except:
        pass

async def add_to_trade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Добавить предмет в трейд"""
    user_id = str(update.effective_user.id)
    
    if len(context.args) != 3:
        await update.message.reply_text(
            "Использование: /add_to_trade <ID_трейда> <сумма> <тип>\n\n"
            "Типы: money (деньги), coins (койны)\n"
            "Примеры:\n"
            "/add_to_trade abc123 1000000 money\n"
            "/add_to_trade abc123 50 coins"
        )
        return
    
    trade_id, amount_str, item_type = context.args
    item_type = item_type.lower()
    
    if trade_id not in active_trades:
        await update.message.reply_text("❌ Трейд не найден!")
        return
    
    trade = active_trades[trade_id]
    
    # Проверяем, участник ли пользователь трейда
    if user_id not in [trade['user1'], trade['user2']]:
        await update.message.reply_text("❌ Вы не участник этого трейда!")
        return
    
    # Проверяем, не завершен ли уже трейд
    if trade.get('completed'):
        await update.message.reply_text("❌ Этот трейд уже завершен!")
        return
    
    # Парсим сумму
    try:
        if item_type == 'money':
            amount = parse_bet_amount(amount_str)
        elif item_type == 'coins':
            amount = int(amount_str)
        else:
            await update.message.reply_text("❌ Неверный тип! Используйте: money или coins")
            return
        
        if amount <= 0:
            await update.message.reply_text("❌ Сумма должна быть положительной!")
            return
    except:
        await update.message.reply_text("❌ Неверный формат суммы!")
        return
    
    # Проверяем баланс пользователя
    user = get_user_data(user_id)
    if item_type == 'money':
        if amount > user['balance']:
            await update.message.reply_text(f"❌ Недостаточно денег! У вас {user['balance']:,} ₽")
            return
    elif item_type == 'coins':
        if amount > user.get('coins', 0):
            await update.message.reply_text(f"❌ Недостаточно койнов! У вас {user.get('coins', 0)}")
            return
    
    # Добавляем предмет в трейд
    user_key = 'user1_items' if user_id == trade['user1'] else 'user2_items'
    
    if item_type == 'money':
        trade[user_key]['money'] = amount
    elif item_type == 'coins':
        trade[user_key]['coins'] = amount
    
    # Сбрасываем подтверждения при изменении предметов
    trade['user1_confirmed'] = False
    trade['user2_confirmed'] = False
    
    save_data()
    
    await update.message.reply_text(
        f"✅ Предмет добавлен в трейд {trade_id}!\n\n"
        f"Вы добавили: {amount:,} {'₽' if item_type == 'money' else 'койнов'}\n\n"
        f"Текущие предметы в трейде:\n"
        f"{get_trade_items_text(trade)}\n\n"
        f"Для подтверждения: /confirm_trade {trade_id}"
    )
    
    # Уведомляем другого участника
    other_user_id = trade['user2'] if user_id == trade['user1'] else trade['user1']
    try:
        await context.bot.send_message(
            chat_id=int(other_user_id),
            text=f"📝 @{user.get('username', user_id)} добавил предметы в трейд {trade_id}!\n\n"
                 f"{get_trade_items_text(trade)}\n\n"
                 f"Для подтверждения: /confirm_trade {trade_id}"
        )
    except:
        pass

async def confirm_trade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подтвердить трейд"""
    user_id = str(update.effective_user.id)
    
    if not context.args:
        await update.message.reply_text("Использование: /confirm_trade <ID_трейда>")
        return
    
    trade_id = context.args[0]
    
    if trade_id not in active_trades:
        await update.message.reply_text("❌ Трейд не найден!")
        return
    
    trade = active_trades[trade_id]
    
    # Проверяем, участник ли пользователь трейда
    if user_id not in [trade['user1'], trade['user2']]:
        await update.message.reply_text("❌ Вы не участник этого трейда!")
        return
    
    # Проверяем, не завершен ли уже трейд
    if trade.get('completed'):
        await update.message.reply_text("❌ Этот трейд уже завершен!")
        return
    
    # Проверяем, есть ли предметы в трейде
    if trade['user1_items']['money'] == 0 and trade['user1_items']['coins'] == 0:
        await update.message.reply_text("❌ Первый участник не добавил предметы!")
        return
    
    if trade['user2_items']['money'] == 0 and trade['user2_items']['coins'] == 0:
        await update.message.reply_text("❌ Второй участник не добавил предметы!")
        return
    
    # Подтверждаем от имени пользователя
    if user_id == trade['user1']:
        trade['user1_confirmed'] = True
    else:
        trade['user2_confirmed'] = True
    
    save_data()
    
    await update.message.reply_text(
        f"✅ Вы подтвердили трейд {trade_id}!\n\n"
        f"Текущий статус:\n"
        f"👤 {trade['user1_name']}: {'✅' if trade['user1_confirmed'] else '❌'}\n"
        f"👤 {trade['user2_name']}: {'✅' if trade['user2_confirmed'] else '❌'}\n\n"
        f"{get_trade_items_text(trade)}"
    )
    
    # Если оба подтвердили - выполняем обмен
    if trade['user1_confirmed'] and trade['user2_confirmed']:
        await execute_trade(update, context, trade_id)

async def execute_trade(update: Update, context: ContextTypes.DEFAULT_TYPE, trade_id: str):
    """Выполнить обмен при подтверждении обоих участников"""
    trade = active_trades[trade_id]
    
    # Получаем данные пользователей
    user1 = get_user_data(trade['user1'])
    user2 = get_user_data(trade['user2'])
    
    # Проверяем достаточно ли средств
    if trade['user1_items']['money'] > user1['balance']:
        await update.message.reply_text(f"❌ У {trade['user1_name']} недостаточно денег!")
        return
    
    if trade['user1_items']['coins'] > user1.get('coins', 0):
        await update.message.reply_text(f"❌ У {trade['user1_name']} недостаточно койнов!")
        return
    
    if trade['user2_items']['money'] > user2['balance']:
        await update.message.reply_text(f"❌ У {trade['user2_name']} недостаточно денег!")
        return
    
    if trade['user2_items']['coins'] > user2.get('coins', 0):
        await update.message.reply_text(f"❌ У {trade['user2_name']} недостаточно койнов!")
        return
    
    # Выполняем обмен
    # User1 отдает -> User2 получает
    user1['balance'] -= trade['user1_items']['money']
    user2['balance'] += trade['user1_items']['money']
    
    user1['coins'] = user1.get('coins', 0) - trade['user1_items']['coins']
    user2['coins'] = user2.get('coins', 0) + trade['user1_items']['coins']
    
    # User2 отдает -> User1 получает
    user2['balance'] -= trade['user2_items']['money']
    user1['balance'] += trade['user2_items']['money']
    
    user2['coins'] = user2.get('coins', 0) - trade['user2_items']['coins']
    user1['coins'] = user1.get('coins', 0) + trade['user2_items']['coins']
    
    # Помечаем трейд как завершенный
    trade['completed'] = True
    trade['completed_at'] = time.time()
    
    save_data()
    
    # Отправляем уведомления
    success_message = (
        f"✅ Трейд {trade_id} успешно завершен!\n\n"
        f"{get_trade_items_text(trade)}\n\n"
        f"📊 Итоги:\n"
        f"👤 {trade['user1_name']} получил:\n"
        f"   💰 {trade['user2_items']['money']:,} ₽\n"
        f"   🪙 {trade['user2_items']['coins']} койнов\n\n"
        f"👤 {trade['user2_name']} получил:\n"
        f"   💰 {trade['user1_items']['money']:,} ₽\n"
        f"   🪙 {trade['user1_items']['coins']} койнов"
    )
    
    await update.message.reply_text(success_message)
    
    # Уведомляем второго участника
    other_user_id = trade['user2'] if str(update.effective_user.id) == trade['user1'] else trade['user1']
    try:
        await context.bot.send_message(
            chat_id=int(other_user_id),
            text=success_message
        )
    except:
        pass

async def cancel_trade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отменить трейд"""
    user_id = str(update.effective_user.id)
    
    if not context.args:
        await update.message.reply_text("Использование: /cancel_trade <ID_трейда>")
        return
    
    trade_id = context.args[0]
    
    if trade_id not in active_trades:
        await update.message.reply_text("❌ Трейд не найден!")
        return
    
    trade = active_trades[trade_id]
    
    # Проверяем, участник ли пользователь трейда
    if user_id not in [trade['user1'], trade['user2']]:
        await update.message.reply_text("❌ Вы не участник этого трейда!")
        return
    
    # Проверяем, не завершен ли уже трейд
    if trade.get('completed'):
        await update.message.reply_text("❌ Этот трейд уже завершен!")
        return
    
    # Удаляем трейд
    del active_trades[trade_id]
    save_data()
    
    await update.message.reply_text(f"✅ Трейд {trade_id} отменен!")
    
    # Уведомляем другого участника
    other_user_id = trade['user2'] if user_id == trade['user1'] else trade['user1']
    try:
        await context.bot.send_message(
            chat_id=int(other_user_id),
            text=f"❌ @{user_data[user_id].get('username', user_id)} отменил трейд {trade_id}!"
        )
    except:
        pass

async def show_my_trade_offers_simple(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать мои трейды (упрощенная версия)"""
    user_id = str(update.effective_user.id)
    
    # Ищем активные трейды пользователя
    user_trades = []
    for trade_id, trade in active_trades.items():
        if user_id in [trade['user1'], trade['user2']] and not trade.get('completed'):
            user_trades.append((trade_id, trade))
    
    if not user_trades:
        await update.message.reply_text("📭 У вас нет активных трейдов.")
        return
    
    text = "📊 Ваши активные трейды:\n\n"
    
    for trade_id, trade in user_trades:
        other_user_name = trade['user2_name'] if user_id == trade['user1'] else trade['user1_name']
        status = "✅ Оба подтвердили" if trade['user1_confirmed'] and trade['user2_confirmed'] else "⏳ Ожидает"
        
        text += (
            f"🔹 ID: {trade_id}\n"
            f"👤 С: @{other_user_name}\n"
            f"📊 Статус: {status}\n"
            f"{get_trade_items_text(trade)}\n\n"
        )
    
    await update.message.reply_text(text)

async def show_incoming_offers_simple(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать входящие трейды (упрощенная версия)"""
    user_id = str(update.effective_user.id)
    
    # Ищем трейды где пользователь является участником
    incoming_trades = []
    for trade_id, trade in active_trades.items():
        if user_id in [trade['user1'], trade['user2']] and not trade.get('completed'):
            incoming_trades.append((trade_id, trade))
    
    if not incoming_trades:
        await update.message.reply_text("📭 У вас нет входящих трейдов.")
        return
    
    text = "📥 Ваши трейды:\n\n"
    
    for trade_id, trade in incoming_trades:
        other_user_name = trade['user2_name'] if user_id == trade['user1'] else trade['user1_name']
        my_confirmed = trade['user1_confirmed'] if user_id == trade['user1'] else trade['user2_confirmed']
        other_confirmed = trade['user2_confirmed'] if user_id == trade['user1'] else trade['user1_confirmed']
        
        text += (
            f"🔹 ID: {trade_id}\n"
            f"👤 С: @{other_user_name}\n"
            f"📊 Ваш статус: {'✅' if my_confirmed else '❌'}\n"
            f"📊 Статус оппонента: {'✅' if other_confirmed else '❌'}\n"
            f"{get_trade_items_text(trade)}\n\n"
            f"Команды:\n"
            f"/add_to_trade {trade_id} <сумма> <тип>\n"
            f"/confirm_trade {trade_id}\n"
            f"/cancel_trade {trade_id}\n\n"
        )
    
    await update.message.reply_text(text)

def get_trade_items_text(trade):
    """Получить текстовое представление предметов в трейде"""
    user1_items = trade['user1_items']
    user2_items = trade['user2_items']
    
    text = (
        f"👤 {trade['user1_name']} отдает:\n"
        f"   💰 {user1_items['money']:,} ₽\n"
        f"   🪙 {user1_items['coins']} койнов\n\n"
        f"👤 {trade['user2_name']} отдает:\n"
        f"   💰 {user2_items['money']:,} ₽\n"
        f"   🪙 {user2_items['coins']} койнов"
    )
    
    return text

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
    """Обработчик кнопки ТОПЫ"""
    user_id = update.message.from_user.id
    if user_id in banned_users:
        await update.message.reply_text("⛔ Вы заблокированы")
        return
    
    keyboard = [
        [InlineKeyboardButton("🏆 Топ по балансу", callback_data="top_balance")],
        [InlineKeyboardButton("📨 Топ по рефералам", callback_data="top_referrals")],
        [InlineKeyboardButton("🪙 Топ по койнам", callback_data="top_coins")],
        [InlineKeyboardButton("💸 Топ по сливу в казино", callback_data="top_losses")]  # НОВАЯ КНОПКА
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "📊 Выберите тип топа:",
        reply_markup=reply_markup
    )
async def crash_top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Топ игроков в краш"""
    # Сортируем по прибыли
    sorted_players = sorted(
        [(uid, stats) for uid, stats in crash_stats.items() if int(uid) not in banned_users],
        key=lambda x: x[1]['profit'],
        reverse=True
    )[:10]
    
    text = "💥 <b>ТОП КРАШ-ИГРОКОВ</b>\n═══════════════════\n\n"
    
    for i, (uid, stats) in enumerate(sorted_players, 1):
        username = user_data.get(uid, {}).get('username', uid)
        win_rate = (stats['wins'] / stats['games'] * 100) if stats['games'] > 0 else 0
        
        text += (
            f"{i}. @{username}\n"
            f"   💰 Прибыль: {stats['profit']:+,} ₽\n"
            f"   📊 Игр: {stats['games']} | Побед: {stats['wins']}\n"
            f"   📈 Винрейт: {win_rate:.1f}%\n\n"
        )
    
    await update.message.reply_text(text, parse_mode='HTML')
    
async def top_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопок топов"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    print(f"DEBUG: Нажата кнопка топа: {data}")  # Для отладки
    
    if data == "top_balance":
        await top_balance(update, context, is_callback=True, page=0)
    elif data == "top_referrals":
        await top_referrals(update, context, is_callback=True, page=0)
    elif data == "top_coins":
        await top_coins(update, context, is_callback=True, page=0)  # Добавлен page=0
    elif data == "top_losses":
        await top_losses(update, context, is_callback=True, page=0)
    elif data == "top_back":
        # Возврат к выбору типа топа
        keyboard = [
            [InlineKeyboardButton("🏆 Топ по балансу", callback_data="top_balance")],
            [InlineKeyboardButton("📨 Топ по рефералам", callback_data="top_referrals")],
            [InlineKeyboardButton("🪙 Топ по койнам", callback_data="top_coins")],
            [InlineKeyboardButton("🎰 Топ по сливу", callback_data="top_losses")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "📊 Выберите тип топа:",
            reply_markup=reply_markup
        )
    elif data.startswith("top_balance_page_"):
        page = int(data.split('_')[3])
        await top_balance(update, context, is_callback=True, page=page)
    elif data.startswith("top_losses"):
        page = int(data.split('_')[3])
        await top_lost(update, context, is_callback=True, page=page)
    elif data.startswith("top_referrals_page_"):
        page = int(data.split('_')[3])
        await top_referrals(update, context, is_callback=True, page=page)
    elif data.startswith("top_coins_page_"):
        page = int(data.split('_')[3])
        await top_coins(update, context, is_callback=True, page=page)  # Добавлен page

# ==================== ФУНКЦИИ ТРЕЙДОВ ====================
# ==================== ФУНКЦИИ ТРЕЙДОВ (ИСПРАВЛЕННЫЕ) ====================
async def trade_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
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
            'user_id': str(query.from_user.id),
            'offer': {'money': 0, 'coins': 0, 'items': []},
            'request': {'money': 0, 'coins': 0, 'items': []},
            'recipient': None
        }
        await show_trade_create_menu(update, context)
        return TRADE_CREATE
    
    elif query.data == "trade_my_offers":
        await show_my_trade_offers(update, context)
        return TRADE_MENU
    
    elif query.data == "trade_incoming":
        await show_incoming_trade_offers(update, context)
        return TRADE_MENU
    
    elif query.data == "trade_active":
        await show_active_trades(update, context)
        return TRADE_MENU
    
    return TRADE_MENU

async def show_trade_create_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query if hasattr(update, 'callback_query') else None
    
    trade_data = context.user_data.get('trade_data', {
        'user_id': str(update.effective_user.id),
        'offer': {'money': 0, 'coins': 0, 'items': []},
        'request': {'money': 0, 'coins': 0, 'items': []},
        'recipient': None
    })
    
    user = get_user_data(trade_data['user_id'])
    
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
            chat_id=int(trade_data['user_id']),
            text=message_text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    return TRADE_CREATE

async def trade_create_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
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
        recipient_input = trade_data['recipient'].lstrip('@')
        
        # Ищем получателя по username или ID
        for uid, u_data in user_data.items():
            username = u_data.get('username', '').lower()
            uid_str = str(uid)
            
            # Проверяем по username (без @) или ID
            if username == recipient_input.lower() or uid_str == recipient_input:
                recipient = {'id': uid_str, 'username': u_data.get('username', uid_str)}
                break
        
        if not recipient:
            await query.answer("❌ Пользователь не найден!", show_alert=True)
            return await show_trade_create_menu(update, context)
        
        if recipient['id'] == user_id:
            await query.answer("❌ Нельзя обмениваться с самим собой!", show_alert=True)
            return await show_trade_create_menu(update, context)
        
        # Проверяем достаточно ли средств у отправителя
        if trade_data['offer']['money'] > user['balance']:
            await query.answer("❌ У вас недостаточно денег для предложения!", show_alert=True)
            return await show_trade_create_menu(update, context)
        
        if trade_data['offer']['coins'] > user.get('coins', 0):
            await query.answer("❌ У вас недостаточно койнов для предложения!", show_alert=True)
            return await show_trade_create_menu(update, context)
        
        # Проверяем наличие предметов в инвентаре
        inventory_items = user.get('inventory', {'items': []})['items']
        for item in trade_data['offer']['items']:
            if item not in inventory_items:
                await query.answer(f"❌ У вас нет предмета {item}!", show_alert=True)
                return await show_trade_create_menu(update, context)
        
        # Создаем уникальный ID для предложения
        offer_id = secrets.token_hex(8)
        trade_offers[offer_id] = {
            'sender_id': user_id,
            'sender_name': user.get('username', user_id),
            'recipient_id': recipient['id'],
            'recipient_name': recipient['username'],
            'offer': trade_data['offer'],
            'request': trade_data['request'],
            'created_at': datetime.now().isoformat()
        }
        
        # Сообщаем отправителю об успешном создании
        await query.edit_message_text(
            f"✅ Предложение обмена создано!\n\n"
            f"👤 Для: @{recipient['username']}\n\n"
            f"📤 Вы предлагаете:\n"
            f"💰 {trade_data['offer']['money']:,} ₽\n"
            f"🪙 {trade_data['offer']['coins']} койнов\n"
            f"🎁 Предметы: {', '.join(trade_data['offer']['items']) or 'нет'}\n\n"
            f"📥 Вы запрашиваете:\n"
            f"💰 {trade_data['request']['money']:,} ₽\n"
            f"🪙 {trade_data['request']['coins']} койнов\n"
            f"🎁 Предметы: {', '.join(trade_data['request']['items']) or 'нет'}\n\n"
            f"ID предложения: <code>{offer_id}</code>",
            parse_mode='HTML'
        )
        
        # Отправка уведомления получателю
        try:
            await context.bot.send_message(
                chat_id=int(recipient['id']),
                text=
                    f"📥 У вас новое предложение обмена от @{user.get('username', user_id)}!\n\n"
                    f"📤 Вам предлагают:\n"
                    f"💰 {trade_data['offer']['money']:,} ₽\n"
                    f"🪙 {trade_data['offer']['coins']} койнов\n"
                    f"🎁 Предметы: {', '.join(trade_data['offer']['items']) or 'нет'}\n\n"
                    f"📥 Запрашивают у вас:\n"
                    f"💰 {trade_data['request']['money']:,} ₽\n"
                    f"🪙 {trade_data['request']['coins']} койнов\n"
                    f"🎁 Предметы: {', '.join(trade_data['request']['items']) or 'нет'}\n\n"
                    f"ID предложения: <code>{offer_id}</code>\n\n"
                    f"Чтобы принять предложение:\n"
                    f"1. Используйте команду /trade\n"
                    f"2. Нажмите '📥 Входящие предложения'\n"
                    f"3. Нажмите '✅ Принять предложение'\n"
                    f"4. Введите ID: <code>{offer_id}</code>",
                    parse_mode='HTML'
                
            )
            logging.info(f"Уведомление о трейде отправлено пользователю {recipient['id']}")
        except Exception as e:
            logging.error(f"Ошибка отправки уведомления пользователю {recipient['id']}: {e}")
            await query.edit_message_text(
                "✅ Предложение создано, но не удалось уведомить получателя. "
                "Возможно, он не запускал бота или заблокировал его.\n\n"
                f"ID предложения: <code>{offer_id}</code>\n"
                f"Попросите пользователя @{recipient['username']} проверить входящие предложения.",
                parse_mode='HTML'
            )
        
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
    user_id = str(query.from_user.id)
    
    # Ищем предложения, где пользователь - отправитель
    user_offers = [offer_id for offer_id, offer in trade_offers.items() if offer['sender_id'] == user_id]
    
    if not user_offers:
        await query.edit_message_text(
            "❌ У вас нет активных предложений обмена.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="trade_back")]])
        )
        return TRADE_MENU
    
    offers_text = "📨 Ваши предложения обмена:\n\n"
    for i, offer_id in enumerate(user_offers[:10], 1):  # Ограничиваем 10 предложениями
        offer = trade_offers[offer_id]
        offers_text += (
            f"{i}. ID: <code>{offer_id}</code>\n"
            f"👤 Для: @{offer['recipient_name']}\n"
            f"💰 Предлагаете: {offer['offer']['money']:,} ₽ + {offer['offer']['coins']} койнов\n"
            f"🎁 Предметы: {', '.join(offer['offer']['items']) or 'нет'}\n"
            f"🔄 Запрашиваете: {offer['request']['money']:,} ₽ + {offer['request']['coins']} койнов\n"
            f"🎁 Предметы: {', '.join(offer['request']['items']) or 'нет'}\n"
            f"🕒 Создано: {datetime.fromisoformat(offer['created_at']).strftime('%d.%m.%Y %H:%M')}\n\n"
        )
    
    keyboard = [
        [InlineKeyboardButton("❌ Отменить предложение", callback_data="trade_reject_offer")],
        [InlineKeyboardButton("🔙 Назад", callback_data="trade_back")]
    ]
    
    await query.edit_message_text(
        offers_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )
    return TRADE_MENU

async def show_incoming_trade_offers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    
    # Ищем предложения, где пользователь - получатель
    incoming_offers = [offer_id for offer_id, offer in trade_offers.items() if offer['recipient_id'] == user_id]
    
    if not incoming_offers:
        await query.edit_message_text(
            "❌ У вас нет входящих предложений обмена.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="trade_back")]])
        )
        return TRADE_MENU
    
    offers_text = "📥 Входящие предложения обмена:\n\n"
    for i, offer_id in enumerate(incoming_offers[:10], 1):
        offer = trade_offers[offer_id]
        offers_text += (
            f"{i}. ID: <code>{offer_id}</code>\n"
            f"👤 От: @{offer['sender_name']}\n"
            f"💰 Предлагает: {offer['offer']['money']:,} ₽ + {offer['offer']['coins']} койнов\n"
            f"🎁 Предметы: {', '.join(offer['offer']['items']) or 'нет'}\n"
            f"🔄 Запрашивает: {offer['request']['money']:,} ₽ + {offer['request']['coins']} койнов\n"
            f"🎁 Предметы: {', '.join(offer['request']['items']) or 'нет'}\n"
            f"🕒 Получено: {datetime.fromisoformat(offer['created_at']).strftime('%d.%m.%Y %H:%M')}\n\n"
        )
    
    keyboard = [
        [InlineKeyboardButton("✅ Принять предложение", callback_data="trade_accept_offer")],
        [InlineKeyboardButton("❌ Отклонить предложение", callback_data="trade_reject_offer")],
        [InlineKeyboardButton("🔙 Назад", callback_data="trade_back")]
    ]
    
    await query.edit_message_text(
        offers_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )
    return TRADE_MENU

async def show_active_trades(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    
    # Ищем активные трейды, где пользователь участник
    user_trades = [trade_id for trade_id, trade in active_trades.items() 
                  if str(trade['user1']) == user_id or str(trade['user2']) == user_id]
    
    if not user_trades:
        await query.edit_message_text(
            "❌ У вас нет активных трейдов.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="trade_back")]])
        )
        return TRADE_MENU
    
    trades_text = "📊 Ваши активные трейды:\n\n"
    for i, trade_id in enumerate(user_trades[:10], 1):
        trade = active_trades[trade_id]
        
        # Определяем, кто второй участник
        if str(trade['user1']) == user_id:
            other_user_id = str(trade['user2'])
            user_role = "отправитель"
        else:
            other_user_id = str(trade['user1'])
            user_role = "получатель"
        
        other_user = get_user_data(other_user_id)
        other_name = other_user.get('username', other_user_id)
        
        # Определяем статус подтверждения
        if user_role == "отправитель":
            confirmed_you = trade['confirmed_user1']
            confirmed_other = trade['confirmed_user2']
        else:
            confirmed_you = trade['confirmed_user2']
            confirmed_other = trade['confirmed_user1']
        
        status = "✅ Подтвержден" if trade['confirmed'] else (
            "⏳ Ожидает вашего подтверждения" if not confirmed_you else
            "⏳ Ожидает подтверждения второй стороны"
        )
        
        trades_text += (
            f"{i}. ID: <code>{trade_id}</code>\n"
            f"👤 С: @{other_name}\n"
            f"📊 Ваша роль: {user_role}\n"
            f"🔄 Статус: {status}\n\n"
        )
    
    keyboard = [
        [InlineKeyboardButton("✅ Подтвердить трейд", callback_data="trade_confirm_active")],
        [InlineKeyboardButton("❌ Отменить трейд", callback_data="trade_cancel_active")],
        [InlineKeyboardButton("🔙 Назад", callback_data="trade_back")]
    ]
    
    await query.edit_message_text(
        trades_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )
    return TRADE_MENU

async def premium_box_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню премиум бокса"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    user = get_user_data(user_id)
    
    # Проверяем, покупал ли уже сегодня
    last_premium = user.get('last_premium_box', '')
    today = datetime.now().strftime('%Y-%m-%d')
    
    can_buy = (last_premium != today)
    
    # Формируем текст с шансами
    text = (
        "💎 <b>ПРЕМИУМ БОКС</b>\n"
        "═══════════════════\n\n"
        f"💰 Цена: <b>1,000,000,000 ₽</b>\n"
        f"🪙 Ваши койны: {user.get('coins', 0)}\n"
        f"💰 Ваш баланс: {user['balance']:,} ₽\n\n"
        
        "🎁 <b>ВОЗМОЖНЫЕ НАГРАДЫ:</b>\n"
        "═══════════════════\n"
        "💎 <b>Золотой цветок</b> (10%)\n"
        "   • Меняет фото в профиле\n"
        "   • Уникальный эффект\n\n"
        
        "💰 <b>500M - 1B ₽</b> (20%)\n"
        "   • От 500 млн до 1 млрд\n\n"
        
        "💰 <b>100M - 500M ₽</b> (30%)\n"
        "   • От 100 млн до 500 млн\n\n"
        
        "🪙 <b>100 койнов</b> (15%)\n"
        "   • Для покупки обычных боксов\n\n"
        
        "🪙 <b>50 койнов</b> (15%)\n"
        "   • Для покупки обычных боксов\n\n"
        
        "🎁 <b>Сюрприз</b> (10%)\n"
        "   • Случайный бонус\n"
    )
    
    if can_buy:
        text += "\n✅ Доступно для покупки!"
        keyboard = [
            [InlineKeyboardButton("💎 КУПИТЬ ПРЕМИУМ БОКС (1,000,000,000 ₽)", callback_data="premium_box_buy")],
            [InlineKeyboardButton("🔙 НАЗАД", callback_data="box_back")]
        ]
    else:
        text += "\n❌ Уже куплен сегодня.\nЗавтра будет доступен снова!"
        keyboard = [[InlineKeyboardButton("🔙 НАЗАД", callback_data="box_back")]]
    
    await query.edit_message_text(
        text=text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )
    
    return PREMIUM_BOX_MENU
    
async def investment_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню инвестиций"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    user = get_user_data(user_id)
    
    text = (
        "📈 <b>ИНВЕСТИЦИОННЫЙ ПОРТФЕЛЬ</b>\n"
        "═══════════════════════\n\n"
        "Вкладывайте деньги в компании\n"
        "и получайте прибыль!\n\n"
        "📊 <b>Доступные компании:</b>\n\n"
    )
    
    keyboard = []
    for comp_id, comp in INVESTMENT_COMPANIES.items():
        risk = "Низкий" if comp['volatility'] < 0.3 else "Средний" if comp['volatility'] < 0.6 else "Высокий"
        text += (
            f"{comp['color']} <b>{comp['name']}</b> {comp['emoji']}\n"
            f"├ {comp['description']}\n"
            f"├ 💰 От {comp['min_invest']:,} ₽\n"
            f"├ 📈 Доход: +{int((comp['base_return']-1)*100)}%\n"
            f"└ ⚡ Риск: {risk}\n\n"
        )
        keyboard.append([InlineKeyboardButton(
            f"{comp['color']} {comp['name']} {comp['emoji']}",
            callback_data=f"invest_{comp_id}"
        )])
    
    keyboard.append([InlineKeyboardButton("📊 МОИ ИНВЕСТИЦИИ", callback_data="invest_my")])
    keyboard.append([InlineKeyboardButton("🔙 НАЗАД", callback_data="invest_back")])
    
    await query.edit_message_text(
        text=text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )
    
    return INVEST_MENU

async def invest_company(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Инвестировать в компанию"""
    query = update.callback_query
    await query.answer()
    
    company_id = query.data.replace("invest_", "")
    company = INVESTMENT_COMPANIES.get(company_id)
    
    if not company:
        await query.answer("❌ Компания не найдена!", show_alert=True)
        return await investment_menu(update, context)
    
    context.user_data['invest_company'] = company_id
    context.user_data['invest_company_name'] = company['name']
    
    text = (
        f"{company['color']} <b>{company['name']}</b> {company['emoji']}\n"
        f"═══════════════════════\n\n"
        f"📋 {company['description']}\n\n"
        f"💰 Минимальная сумма: {company['min_invest']:,} ₽\n"
        f"📈 Средняя доходность: +{int((company['base_return']-1)*100)}%\n"
        f"⚡ Волатильность: {int(company['volatility']*100)}%\n\n"
        f"⏳ Срок инвестиции: 7 дней\n\n"
        f"Введите сумму для инвестирования:"
    )
    
    await query.edit_message_text(
        text=text,
        parse_mode='HTML'
    )
    
    return INVEST_AMOUNT

async def process_invest_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка суммы инвестиций"""
    user_id = str(update.message.from_user.id)
    user = get_user_data(user_id)
    
    try:
        amount = parse_bet_amount(update.message.text)
        company_id = context.user_data.get('invest_company')
        company = INVESTMENT_COMPANIES.get(company_id)
        
        if not amount or amount < company['min_invest']:
            await update.message.reply_text(f"❌ Минимальная сумма: {company['min_invest']:,} ₽")
            return INVEST_AMOUNT
        
        if amount > user['balance']:
            await update.message.reply_text(f"❌ Недостаточно средств! Баланс: {user['balance']:,} ₽")
            return INVEST_AMOUNT
        
        # Списываем деньги
        user['balance'] -= amount
        
        # Сохраняем инвестицию
        if user_id not in user_investments:
            user_investments[user_id] = {}
        
        user_investments[user_id][company_id] = {
            'amount': amount,
            'start_time': time.time(),
            'days': 7,
            'company': company['name']
        }
        await check_all_achievements(update, user_id, user)
        save_investments()
        save_data()
        
        text = (
            f"✅ <b>ИНВЕСТИЦИЯ СОЗДАНА!</b>\n"
            f"═══════════════════════\n\n"
            f"{company['color']} {company['name']} {company['emoji']}\n"
            f"💰 Сумма: {amount:,} ₽\n"
            f"📅 Срок: 7 дней\n\n"
            f"📊 Через 7 дней вы получите:\n"
            f"├ От {int(amount * (company['base_return'] - company['volatility'])):,} ₽\n"
            f"└ До {int(amount * (company['base_return'] + company['volatility'])):,} ₽\n\n"
            f"⏳ Удачи! Прибыль зависит от рынка!"
        )
        
        await update.message.reply_text(text, parse_mode='HTML')
        
        # Очищаем контекст
        context.user_data.pop('invest_company', None)
        context.user_data.pop('invest_company_name', None)
        
        return ConversationHandler.END
        
    except Exception as e:
        await update.message.reply_text("❌ Ошибка! Введите корректную сумму.")
        return INVEST_AMOUNT

async def my_investments(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать мои инвестиции"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    investments = user_investments.get(user_id, {})
    
    if not investments:
        text = "📊 У вас пока нет активных инвестиций."
    else:
        text = "📊 <b>ВАШИ ИНВЕСТИЦИИ</b>\n═══════════════════\n\n"
        current_time = time.time()
        
        for comp_id, inv in investments.items():
            company = INVESTMENT_COMPANIES.get(comp_id, {})
            if not company:
                continue
            
            days_left = 7 - (current_time - inv['start_time']) // 86400
            if days_left < 0:
                days_left = 0
            
            # Расчет возможной прибыли
            min_return = company['base_return'] - company['volatility']
            max_return = company['base_return'] + company['volatility']
            
            text += (
                f"{company['color']} {company['name']} {company['emoji']}\n"
                f"├ 💰 {inv['amount']:,} ₽\n"
                f"├ 📈 Потенциал: {int((min_return-1)*100)}% - {int((max_return-1)*100)}%\n"
                f"└ ⏳ Осталось: {int(days_left)} д.\n\n"
            )
    
    keyboard = [[InlineKeyboardButton("🔙 НАЗАД", callback_data="invest_back")]]
    
    await query.edit_message_text(
        text=text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )
    
    return INVEST_MENU

async def trade_offer_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query if hasattr(update, 'callback_query') else None
    
    if query:
        await query.answer()
        user_id = str(query.from_user.id)
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
        user_id = str(update.message.from_user.id)
        text = update.message.text
        trade_data = context.user_data['trade_data']
        action = context.user_data.get('trade_action')
        
        if action == 'add_money':
            try:
                amount = parse_bet_amount(text)
                if not amount or amount <= 0:
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
            trade_data['recipient'] = text.lstrip('@')
            del context.user_data['trade_action']
            
            await update.message.reply_text(
                f"👤 Получатель: @{trade_data['recipient']}. Теперь настройте запрашиваемые ресурсы.\n"
                f"Нажмите '✅ Подтвердить трейд' для завершения создания."
            )
            return await show_trade_create_menu(update, context)
    
    return TRADE_OFFER

async def trade_accept_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    
    if query.data == "trade_accept_offer":
        context.user_data['trade_action'] = 'accept_offer'
        await query.edit_message_text(
            "Введите ID предложения, которое хотите принять:\n\n"
            "ID можно найти в уведомлении о предложении или в списке входящих предложений.\n"
            "Пример: <code>a1b2c3d4e5f6</code>",
            parse_mode='HTML'
        )
        return TRADE_ACCEPT
    
    elif query.data == "trade_reject_offer":
        context.user_data['trade_action'] = 'reject_offer'
        await query.edit_message_text(
            "Введите ID предложения, которое хотите отклонить:",
            parse_mode='HTML'
        )
        return TRADE_ACCEPT
    
    elif query.data == "trade_confirm_active":
        context.user_data['trade_action'] = 'confirm_active'
        await query.edit_message_text(
            "Введите ID трейда, который хотите подтвердить:",
            parse_mode='HTML'
        )
        return TRADE_ACCEPT
    
    elif query.data == "trade_cancel_active":
        context.user_data['trade_action'] = 'cancel_active'
        await query.edit_message_text(
            "Введите ID трейда, который хотите отменить:",
            parse_mode='HTML'
        )
        return TRADE_ACCEPT
    
    return TRADE_ACCEPT

async def process_trade_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    user = get_user_data(user_id)
    text = update.message.text.strip()
    
    action = context.user_data.get('trade_action')
    if not action:
        await update.message.reply_text("❌ Неизвестное действие. Начните заново.")
        return await trade_menu(update, context)
    
    try:
        if action == 'accept_offer':
            if text not in trade_offers:
                await update.message.reply_text("❌ Предложение не найдено!")
                return await trade_menu(update, context)
            
            offer = trade_offers[text]
            if offer['recipient_id'] != user_id:
                await update.message.reply_text("❌ Это предложение не для вас!")
                return await trade_menu(update, context)
            
            sender = get_user_data(offer['sender_id'])
            
            # Проверяем наличие средств у отправителя
            if offer['offer']['money'] > sender['balance']:
                await update.message.reply_text("❌ У отправителя недостаточно денег!")
                return await trade_menu(update, context)
            
            if offer['offer']['coins'] > sender.get('coins', 0):
                await update.message.reply_text("❌ У отправителя недостаточно койнов!")
                return await trade_menu(update, context)
            
            # Проверяем наличие средств у получателя (текущего пользователя)
            if offer['request']['money'] > user['balance']:
                await update.message.reply_text("❌ У вас недостаточно денег для обмена!")
                return await trade_menu(update, context)
            
            if offer['request']['coins'] > user.get('coins', 0):
                await update.message.reply_text("❌ У вас недостаточно койнов для обмена!")
                return await trade_menu(update, context)
            
            # Проверяем наличие предметов у отправителя
            sender_inventory = sender.get('inventory', {'items': []})
            for item in offer['offer']['items']:
                if item not in sender_inventory['items']:
                    await update.message.reply_text(f"❌ У отправителя нет предмета {item}!")
                    return await trade_menu(update, context)
            
            # Проверяем наличие предметов у получателя
            user_inventory = user.get('inventory', {'items': []})
            for item in offer['request']['items']:
                if item not in user_inventory['items']:
                    await update.message.reply_text(f"❌ У вас нет предмета {item}!")
                    return await trade_menu(update, context)
            
            # Создаем активный трейд
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
            
            # Удаляем предложение из списка
            del trade_offers[text]
            
            await update.message.reply_text(
                f"✅ Вы приняли предложение обмена!\n\n"
                f"🔄 Трейд создан (ID: <code>{trade_id}</code>)\n\n"
                f"Теперь обе стороны должны подтвердить трейд.\n"
                f"Для подтверждения:\n"
                f"1. Перейдите в '📊 Активные трейды'\n"
                f"2. Нажмите '✅ Подтвердить трейд'\n"
                f"3. Введите ID: <code>{trade_id}</code>",
                parse_mode='HTML'
            )
            
            # Уведомляем отправителя
            try:
                await context.bot.send_message(
                    chat_id=int(offer['sender_id']),
                    text=
                        f"✅ Пользователь @{user.get('username', user_id)} принял ваше предложение обмена!\n\n"
                        f"🔄 Трейд создан (ID: <code>{trade_id}</code>)\n\n"
                        f"Теперь подтвердите трейд:\n"
                        f"1. Используйте команду /trade\n"
                        f"2. Перейдите в '📊 Активные трейды'\n"
                        f"3. Нажмите '✅ Подтвердить трейд'\n"
                        f"4. Введите ID: <code>{trade_id}</code>",
                        parse_mode='HTML'
                    
                )
            except Exception as e:
                logging.error(f"Не удалось отправить уведомление о принятии трейда: {e}")
        
        elif action == 'reject_offer':
            if text not in trade_offers:
                await update.message.reply_text("❌ Предложение не найдено!")
                return await trade_menu(update, context)
            
            offer = trade_offers[text]
            if offer['recipient_id'] != user_id:
                await update.message.reply_text("❌ Это предложение не для вас!")
                return await trade_menu(update, context)
            
            # Удаляем предложение
            del trade_offers[text]
            
            await update.message.reply_text("❌ Вы отклонили предложение обмена.")
            
            # Уведомляем отправителя
            try:
                sender = get_user_data(offer['sender_id'])
                await context.bot.send_message(
                    chat_id=int(offer['sender_id']),
                    text=f"❌ Пользователь @{user.get('username', user_id)} отклонил ваше предложение обмена."
                )
            except Exception as e:
                logging.error(f"Не удалось отправить уведомление об отклонении трейда: {e}")
        
        elif action == 'confirm_active':
            if text not in active_trades:
                await update.message.reply_text("❌ Трейд не найден!")
                return await trade_menu(update, context)
            
            trade = active_trades[text]
            
            # Проверяем, является ли пользователь участником трейда
            if user_id not in [str(trade['user1']), str(trade['user2'])]:
                await update.message.reply_text("❌ Это не ваш трейд!")
                return await trade_menu(update, context)
            
            # Обновляем статус подтверждения
            if user_id == str(trade['user1']):
                trade['confirmed_user1'] = True
                other_user_id = str(trade['user2'])
            else:
                trade['confirmed_user2'] = True
                other_user_id = str(trade['user1'])
            
            # Проверяем, подтвердили ли обе стороны
            if trade['confirmed_user1'] and trade['confirmed_user2']:
                await execute_trade(update, context, text)
            else:
                await update.message.reply_text(
                    f"✅ Вы подтвердили трейд. Ожидаем подтверждения второй стороны."
                )
                
                # Уведомляем второго участника
                try:
                    other_user = get_user_data(other_user_id)
                    await context.bot.send_message(
                        chat_id=int(other_user_id),
                        text=
                            f"🔄 Пользователь @{user.get('username', user_id)} подтвердил трейд.\n\n"
                            f"ID трейда: <code>{text}</code>\n\n"
                            f"Для завершения обмена подтвердите трейд:\n"
                            f"1. Используйте команду /trade\n"
                            f"2. Перейдите в '📊 Активные трейды'\n"
                            f"3. Нажмите '✅ Подтвердить трейд'\n"
                            f"4. Введите ID: <code>{text}</code>",
                            parse_mode='HTML'
                        
                    )
                except Exception as e:
                    logging.error(f"Не удалось отправить уведомление о подтверждении трейда: {e}")
        
        elif action == 'cancel_active':
            if text not in active_trades:
                await update.message.reply_text("❌ Трейд не найдён!")
                return await trade_menu(update, context)
            
            trade = active_trades[text]
            
            if user_id not in [str(trade['user1']), str(trade['user2'])]:
                await update.message.reply_text("❌ Это не ваш трейд!")
                return await trade_menu(update, context)
            
            # Определяем второго участника
            other_user_id = str(trade['user1']) if user_id == str(trade['user2']) else str(trade['user2'])
            
            # Удаляем трейд
            del active_trades[text]
            await update.message.reply_text("❌ Вы отменили трейд.")
            
            # Уведомляем второго участника
            try:
                other_user = get_user_data(other_user_id)
                await context.bot.send_message(
                    chat_id=int(other_user_id),
                    text=f"❌ Пользователь @{user.get('username', user_id)} отменил трейд {text}."
                )
            except Exception as e:
                logging.error(f"Не удалось отправить уведомление об отмене трейда: {e}")
        
        save_data()
    
    except Exception as e:
        logging.error(f"Ошибка при обработке трейда: {e}", exc_info=True)
        await update.message.reply_text("⚠️ Произошла ошибка при обработке трейда. Попробуйте снова.")
    
    return await trade_menu(update, context)

async def execute_trade(update: Update, context: ContextTypes.DEFAULT_TYPE, trade_id):
    trade = active_trades.get(trade_id)
    if not trade:
        await update.message.reply_text("❌ Трейд не найден!")
        return await trade_menu(update, context)
    
    user1 = get_user_data(str(trade['user1']))
    user2 = get_user_data(str(trade['user2']))
    
    # Проверяем наличие средств у обоих пользователей
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
    
    # Проверяем наличие предметов у user1
    user1_inventory = user1.get('inventory', {'items': []})
    for item in trade['offer']['items']:
        if item not in user1_inventory['items']:
            await update.message.reply_text(f"❌ У отправителя нет предмета {item}!")
            return await trade_menu(update, context)
    
    # Проверяем наличие предметов у user2
    user2_inventory = user2.get('inventory', {'items': []})
    for item in trade['request']['items']:
        if item not in user2_inventory['items']:
            await update.message.reply_text(f"❌ У получателя нет предмета {item}!")
            return await trade_menu(update, context)
    
    # Выполняем обмен деньгами
    user1['balance'] -= trade['offer']['money']
    user2['balance'] += trade['offer']['money']
    
    user2['balance'] -= trade['request']['money']
    user1['balance'] += trade['request']['money']
    
    # Выполняем обмен койнами
    user1['coins'] = user1.get('coins', 0) - trade['offer']['coins']
    user2['coins'] = user2.get('coins', 0) + trade['offer']['coins']
    
    user2['coins'] = user2.get('coins', 0) - trade['request']['coins']
    user1['coins'] = user1.get('coins', 0) + trade['request']['coins']
    
    # Выполняем обмен предметами
    for item in trade['offer']['items']:
        if item in user1_inventory['items']:
            user1_inventory['items'].remove(item)
            user2_inventory.setdefault('items', []).append(item)
    
    for item in trade['request']['items']:
        if item in user2_inventory['items']:
            user2_inventory['items'].remove(item)
            user1_inventory.setdefault('items', []).append(item)
    
    # Удаляем завершенный трейд
    del active_trades[trade_id]
    
    # Формируем текст результата
    trade_result = (
        f"✅ Трейд {trade_id} успешно завершен!\n\n"
        f"📤 Вы получили:\n"
        f"💰 {trade['request']['money']:,} ₽\n"
        f"🪙 {trade['request']['coins']} койнов\n"
        f"🎁 {', '.join(trade['request']['items']) or 'нет'}\n\n"
        f"📥 Вы отдали:\n"
        f"💰 {trade['offer']['money']:,} ₽\n"
        f"🪙 {trade['offer']['coins']} койнов\n"
        f"🎁 {', '.join(trade['offer']['items']) or 'нет'}"
    )
    
    await update.message.reply_text(trade_result)
    
    # Отправляем результат второму участнику
    try:
        other_user_id = str(trade['user1']) if str(update.message.from_user.id) == str(trade['user2']) else str(trade['user2'])
        await context.bot.send_message(
            chat_id=int(other_user_id),
            text=trade_result
        )
    except Exception as e:
        logging.error(f"Не удалось отправить уведомление о завершении трейда: {e}")
    
    save_data()
    return await trade_menu(update, context)

# ==================== ФУНКЦИИ БОКСОВ ====================
async def box_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Главное меню боксов"""
    user_id = str(update.effective_user.id)
    
    if user_id in banned_users:
        if update.callback_query:
            await update.callback_query.answer("⛔ Вы заблокированы", show_alert=True)
            return ConversationHandler.END
        else:
            await update.message.reply_text("⛔ Вы заблокированы и не можете использовать бота.")
            return ConversationHandler.END
    
    user = get_user_data(user_id)
    user['last_active'] = time.time()
    
    # Инициализация инвентаря
    if 'inventory' not in user:
        user['inventory'] = {'boxes': 0, 'items': []}
    
    # Проверка ежедневного бокса
    today = datetime.now().strftime('%Y-%m-%d')
    last_daily = user.get('last_daily_box', '')
    daily_status = "✅ Доступен" if last_daily != today else "❌ Получен"
    
    # Клавиатура с типами боксов
    keyboard = [
        [InlineKeyboardButton("🎁 ОБЫЧНЫЙ БОКС", callback_data="normal_box_menu")],
        [InlineKeyboardButton("💎 ПРЕМИУМ БОКС", callback_data="premium_box_menu")],
        [InlineKeyboardButton(f"📅 ЕЖЕДНЕВНЫЙ БОКС {daily_status}", callback_data="daily_box_menu")],
    ]
    
    # Добавляем кнопку открытия если есть боксы
    if user['inventory'].get('boxes', 0) > 0:
        keyboard.append([InlineKeyboardButton(f"🎉 ОТКРЫТЬ БОКС ({user['inventory']['boxes']} шт.)", callback_data="box_open")])
    
    keyboard.extend([
        [InlineKeyboardButton("📦 МОЙ ИНВЕНТАРЬ", callback_data="box_inventory")],
        [InlineKeyboardButton("🔙 НАЗАД", callback_data="box_back")]
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = (
        "🎁 <b>МЕНЮ БОКСОВ</b>\n"
        "═══════════════════\n\n"
        f"🪙 <b>Койны:</b> {user.get('coins', 0)}\n"
        f"💰 <b>Баланс:</b> {user['balance']:,} ₽\n"
        f"📦 <b>Боксов:</b> {user['inventory'].get('boxes', 0)}\n\n"
        "Выберите тип бокса:"
    )
    
    try:
        if update.callback_query:
            try:
                await update.callback_query.edit_message_text(
                    text=text,
                    reply_markup=reply_markup,
                    parse_mode='HTML'
                )
            except Exception as e:
                await update.callback_query.message.reply_text(
                    text=text,
                    reply_markup=reply_markup,
                    parse_mode='HTML'
                )
        else:
            await update.message.reply_text(
                text=text,
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
    except Exception as e:
        logging.error(f"Ошибка в box_menu: {e}")
        if update.effective_message:
            await update.effective_message.reply_text(
                text=text,
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
    
    return BOX_MENU
    
async def normal_box_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню обычного бокса"""
    user_id = str(update.effective_user.id)
    user = get_user_data(user_id)
    
    if user_id in banned_users:
        if update.callback_query:
            await update.callback_query.answer("⛔ Вы заблокированы", show_alert=True)
            return ConversationHandler.END
        else:
            await update.message.reply_text("⛔ Вы заблокированы и не можете использовать бота.")
            return ConversationHandler.END
    
    text = (
        f"🎁 ОБЫЧНЫЙ БОКС\n\n"
        f"💰 Цена: {BOX_PRICE} койнов\n"
        f"🪙 Ваши койны: {user.get('coins', 0)}\n\n"
        f"🎁 Возможные награды:\n"
    )
    
    # Показываем награды обычного бокса
    for reward in BOX_REWARDS:
        emoji = reward['emoji']
        min_amount = reward['min']
        max_amount = reward['max']
        chance = reward['chance']
        
        if max_amount >= 1_000_000_000:  # 1ккк
            amount_text = f"{min_amount//1_000_000_000}-{max_amount//1_000_000_000}ккк"
        elif max_amount >= 1_000_000:  # 1кк
            amount_text = f"{min_amount//1_000_000}-{max_amount//1_000_000}кк"
        else:
            amount_text = f"{min_amount:,}-{max_amount:,} ₽"
            
        text += f"• {emoji} {amount_text} ({chance}%)\n"
    
    keyboard = [
        [InlineKeyboardButton(f"🎁 Купить обычный бокс ({BOX_PRICE} койнов)", callback_data="box_buy")],
        [InlineKeyboardButton("🔙 Назад к боксам", callback_data="box_back")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        if update.callback_query:
            try:
                await update.callback_query.edit_message_text(
                    text=text,
                    reply_markup=reply_markup
                )
            except:
                await update.callback_query.message.reply_text(
                    text=text,
                    reply_markup=reply_markup
                )
        else:
            await update.message.reply_text(
                text=text,
                reply_markup=reply_markup
            )
    except Exception as e:
        logging.error(f"Ошибка в normal_box_menu: {e}")
        if update.effective_message:
            await update.effective_message.reply_text(
                text=text,
                reply_markup=reply_markup
            )
    
    return BOX_MENU
    
async def bank_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Главное меню банка с инвестициями"""
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
    
    # Инициализация банковского счета
    if 'bank' not in user:
        user['bank'] = {'balance': 0, 'deposits': []}
    
    # Проверка завершенных депозитов
    current_time = time.time()
    completed_deposits = []
    
    for deposit in user['bank'].get('deposits', []):
        if deposit['end_time'] <= current_time and not deposit.get('withdrawn', False):
            amount = int(deposit['amount'] * deposit['multiplier'])
            user['bank']['balance'] += amount
            completed_deposits.append((deposit['amount'], amount, deposit['days']))
            deposit['withdrawn'] = True
    
    if completed_deposits:
        completed_text = "🎉 Завершены депозиты:\n"
        for initial, final, days in completed_deposits:
            completed_text += f"• {initial:,} ₽ за {days} дней → {final:,} ₽\n"
        completed_text += f"\n💰 На банковском счету: {user['bank']['balance']:,} ₽"
        
        if update.callback_query:
            await update.callback_query.message.reply_text(completed_text)
        else:
            await update.message.reply_text(completed_text)
        
        save_data()
    
    # Клавиатура меню с инвестициями
    keyboard = [
        [InlineKeyboardButton("💰 Положить депозит", callback_data="bank_deposit_menu")],
        [InlineKeyboardButton("💵 Снять деньги", callback_data="bank_withdraw")],
        [InlineKeyboardButton("📊 Мои депозиты", callback_data="bank_my_deposits")],
        [InlineKeyboardButton("📈 ИНВЕСТИЦИИ", callback_data="bank_investments")],  # НОВАЯ КНОПКА
        [InlineKeyboardButton("🔙 Назад", callback_data="bank_back")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Проверяем активные инвестиции
    user_id_str = str(user_id)
    active_investments = len(user_investments.get(user_id_str, {}))
    
    text = (
        "🏦 <b>БАНКОВСКАЯ СИСТЕМА</b>\n"
        "═══════════════════\n\n"
        f"💰 На счету: {user['bank'].get('balance', 0):,} ₽\n"
        f"💳 В кошельке: {user['balance']:,} ₽\n"
        f"📈 Активных инвестиций: {active_investments}\n\n"
        "Выберите действие:"
    )
    
    if update.callback_query:
        try:
            await update.callback_query.edit_message_text(
                text=text,
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
        except:
            await update.callback_query.message.reply_text(
                text=text,
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
    else:
        await update.message.reply_text(
            text=text,
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    
    return BANK_MENU
    
async def bank_deposit_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = []
    for days, deposit_info in DEPOSIT_TYPES.items():
        keyboard.append([InlineKeyboardButton(
            f"{deposit_info['name']} (x{deposit_info['multiplier']}) - от {deposit_info['min_amount']:,} ₽",
            callback_data=f"bank_deposit_{days}"
        )])
    
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="bank_back")])
    
    await query.edit_message_text(
        "💰 Выберите тип депозита:\n\n"
        "Срок | Множитель | Мин. сумма\n"
        "---------------------------",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return BANK_MENU

async def bank_deposit_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user_data(user_id)
    
    if 'deposit_days' not in context.user_data:
        return await bank_menu(update, context)
    
    days = context.user_data['deposit_days']
    deposit_type = DEPOSIT_TYPES.get(days)
    if not deposit_type:
        await update.message.reply_text("❌ Ошибка типа депозита")
        return await bank_menu(update, context)
    
    try:
        amount = parse_bet_amount(update.message.text)
        if not amount or amount <= 0:
            raise ValueError
        
        if amount < deposit_type['min_amount']:
            await update.message.reply_text(f"❌ Минимальная сумма депозита: {deposit_type['min_amount']:,} ₽")
            return BANK_DEPOSIT
        
        if amount > user['balance']:
            await update.message.reply_text(f"❌ Недостаточно средств. У вас {user['balance']:,} ₽")
            return BANK_DEPOSIT
        
        # Создание депозита
        deposit = {
            'amount': amount,
            'days': days,
            'multiplier': deposit_type['multiplier'],
            'start_time': time.time(),
            'end_time': time.time() + days * 86400,
            'withdrawn': False
        }
        
        user['balance'] -= amount
        user['bank'].setdefault('deposits', []).append(deposit)
        
        await update.message.reply_text(
            f"✅ Депозит создан!\n\n"
            f"💰 Сумма: {amount:,} ₽\n"
            f"📅 Срок: {deposit_type['name']}\n"
            f"📈 Множитель: x{deposit_type['multiplier']}\n"
            f"🕒 Завершится: {datetime.fromtimestamp(deposit['end_time']).strftime('%d.%m.%Y %H:%M')}\n\n"
            f"💵 К выплате: {int(amount * deposit_type['multiplier']):,} ₽"
        )
        
        save_data()
        return await bank_menu(update, context)
    
    except ValueError:
        await update.message.reply_text("❌ Введите корректную сумму!")
        return BANK_DEPOSIT

async def bank_deposit_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user_data(user_id)
    
    if 'deposit_days' not in context.user_data:
        return await bank_menu(update, context)
    
    days = context.user_data['deposit_days']
    deposit_type = DEPOSIT_TYPES[days]
    
    try:
        amount = parse_bet_amount(update.message.text)
        if not amount or amount <= 0:
            raise ValueError
        
        if amount < deposit_type['min_amount']:
            await update.message.reply_text(
                f"❌ Минимальная сумма депозита: {deposit_type['min_amount']:,} ₽"
            )
            return BANK_DEPOSIT
        
        if amount > user['balance']:
            await update.message.reply_text(
                f"❌ Недостаточно средств. У вас {user['balance']:,} ₽"
            )
            return BANK_DEPOSIT
        
        # Создаем депозит
        user['balance'] -= amount
        deposit = {
            'amount': amount,
            'days': days,
            'multiplier': deposit_type['multiplier'],
            'start_time': time.time(),
            'end_time': time.time() + days * 24 * 3600,
            'withdrawn': False
        }
        user['bank'].setdefault('deposits', []).append(deposit)
        
        await update.message.reply_text(
            f"✅ Вы успешно создали депозит!\n\n"
            f"💰 Сумма: {amount:,} ₽\n"
            f"📅 Срок: {deposit_type['name']}\n"
            f"📈 Множитель: x{deposit_type['multiplier']}\n"
            f"🕒 Дата завершения: {datetime.fromtimestamp(deposit['end_time']).strftime('%d.%m.%Y %H:%M')}\n\n"
            f"💵 Итоговая выплата: {int(amount * deposit_type['multiplier']):,} ₽"
        )
        save_data()
        
    except ValueError:
        await update.message.reply_text(
            "❌ Неверная сумма. Введите положительное число."
        )
        return BANK_DEPOSIT
    
    return await bank_menu(update, context)

async def handle_bank_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await bank_menu(update, context)


    
async def box_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопок боксов"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    print(f"box_button_handler: {data}")
    
    # ===== ПЕРЕДАЧА КНОПОК ДРУГИХ МЕНЮ =====
    
    # Кнопки топов
    if data.startswith('top_'):
        print(f"🔄 Передаем кнопку топа в обработчик: {data}")
        new_update = Update(update.update_id, callback_query=query)
        return await top_button_handler(new_update, context)
    
    # Кнопки работ
    if data.startswith('work_') or data.startswith('start_work_'):
        print(f"🔄 Передаем кнопку работы в обработчик: {data}")
        new_update = Update(update.update_id, callback_query=query)
        return await work_callback(new_update, context)
    
    # Кнопки бизнесов
    if data.startswith('business_'):
        print(f"🔄 Передаем кнопку бизнеса в обработчик: {data}")
        new_update = Update(update.update_id, callback_query=query)
        return await business_button_handler(new_update, context)
    
    # ===== НОВОЕ: КНОПКИ НАСТРОЕК =====
    if data.startswith('settings_'):
        print(f"🔄 Передаем кнопку настроек в обработчик: {data}")
        new_update = Update(update.update_id, callback_query=query)
        return await settings_callback(new_update, context)
    
    # Кнопки магазина
    if (data.startswith('shop_') or 
        data.startswith('consumables_') or 
        data.startswith('gift_') or 
        data.startswith('token_buy_')):
        print(f"🔄 Передаем кнопку магазина в обработчик: {data}")
        new_update = Update(update.update_id, callback_query=query)
        return await shop_button_handler(new_update, context)
    
    # Кнопки банка
    if data.startswith('bank_') or data.startswith('invest_'):
        print(f"🔄 Передаем кнопку банка в обработчик: {data}")
        new_update = Update(update.update_id, callback_query=query)
        return await bank_button_handler(new_update, context)
    
    # Кнопки трейдов
    if data.startswith('trade_'):
        print(f"🔄 Передаем кнопку трейдов в обработчик: {data}")
        new_update = Update(update.update_id, callback_query=query)
        return await trade_button_handler(new_update, context)
    
    # Кнопки банд
    if data.startswith('gang_'):
        print(f"🔄 Передаем кнопку банд в обработчик: {data}")
        new_update = Update(update.update_id, callback_query=query)
        return await gang_button_handler(new_update, context)
    
    # Кнопки казино
    if data.startswith('bet:'):
        print(f"🔄 Передаем кнопку казино в обработчик: {data}")
        new_update = Update(update.update_id, callback_query=query)
        return await handle_bet_type(new_update, context)
    
    # Кнопки PvP
    if data.startswith('pvp_'):
        print(f"🔄 Передаем кнопку PvP в обработчик: {data}")
        if data.startswith('pvp_accept_'):
            return await pvp_accept(update, context)
        elif data.startswith('pvp_decline_'):
            return await pvp_decline(update, context)
    
    # ОСТАЛЬНОЙ КОД БОКСОВ...
    user_id = str(query.from_user.id)
    user = get_user_data(user_id)
    
    # Инициализация инвентаря
    if 'inventory' not in user:
        user['inventory'] = {'boxes': 0, 'items': []}
    
    # ===== ЕЖЕДНЕВНЫЙ БОКС =====
    if data == "daily_box_menu":
        return await daily_box_menu(update, context)
    
    elif data == "daily_box_claim":
        return await daily_box_claim(update, context)
    
    # ===== ОБЫЧНЫЙ БОКС =====
    elif data == "normal_box_menu":
        return await normal_box_menu(update, context)
    
    elif data == "box_buy":
        if user.get('coins', 0) < BOX_PRICE:
            await query.answer(f"❌ Недостаточно койнов! Нужно {BOX_PRICE} койнов", show_alert=True)
            return await normal_box_menu(update, context)
        
        user['coins'] -= BOX_PRICE
        user['inventory']['boxes'] = user['inventory'].get('boxes', 0) + 1
        save_data()
        
        await query.answer(f"✅ Вы купили 1 обычный бокс за {BOX_PRICE} койнов!", show_alert=True)
        return await normal_box_menu(update, context)
        await check_all_achievements(update, user_id, user)
    elif data == "box_open":
        if user['inventory'].get('boxes', 0) < 1:
            await query.answer("❌ У вас нет боксов для открытия!", show_alert=True)
            return await box_menu(update, context)
        
        user['inventory']['boxes'] -= 1
        reward_amount, reward_emoji = calculate_box_reward()
        user['balance'] += reward_amount
        
        reward_message = (
            f"🎉 Вы открыли обычный бокс!\n\n"
            f"{reward_emoji} Награда: {reward_amount:,} ₽\n"
            f"💰 Ваш баланс: {user['balance']:,} ₽\n"
            f"🎁 Осталось боксов: {user['inventory'].get('boxes', 0)}"
        )
        
        await query.edit_message_text(reward_message)
        save_data()
        
        keyboard = [
            [InlineKeyboardButton("🎁 Открыть ещё бокс", callback_data="box_open")],
            [InlineKeyboardButton("🛒 Купить ещё боксов", callback_data="normal_box_menu")],
            [InlineKeyboardButton("🔙 Назад", callback_data="box_back")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text("Что дальше?", reply_markup=reply_markup)
        return BOX_MENU
    
    # ===== ПРЕМИУМ БОКС =====
    elif data == "premium_box_menu":
        return await premium_box_menu(update, context)
    
    elif data == "premium_box_buy":
        return await premium_box_button_handler(update, context)
    
    elif data == "premium_box_items":
        return await premium_box_button_handler(update, context)
    
    elif data == "premium_box_back":
        return await box_menu(update, context)
    
    # ===== ИНВЕНТАРЬ =====
    elif data == "box_inventory":
        items = user['inventory'].get('items', [])
        if not items:
            text = "📦 Ваш инвентарь пуст."
        else:
            text = "📦 Ваши предметы:\n" + "\n".join([f"• {item}" for item in items])
        
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="box_back")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return BOX_MENU
    
    # ===== НАЗАД =====
    elif data == "box_back" or data == "box_back_to_main":
        return await box_menu(update, context)
    
    # Если ни одно условие не подошло
    print(f"⚠️ Неизвестная кнопка в боксах: {data}")
    return await box_menu(update, context)
    
async def bank_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопок банка"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_id = query.from_user.id
    user = get_user_data(user_id)
    
    print(f"bank_button_handler: {data}")
    
    # ===== ПЕРЕДАЧА КНОПОК ДРУГИХ МЕНЮ =====
    if data.startswith('top_'):
        print(f"🔄 Передаем кнопку топа в обработчик: {data}")
        new_update = Update(update.update_id, callback_query=query)
        return await top_button_handler(new_update, context)
    
    if data.startswith('work_') or data.startswith('start_work_'):
        print(f"🔄 Передаем кнопку работы в обработчик: {data}")
        new_update = Update(update.update_id, callback_query=query)
        return await work_callback(new_update, context)
    
    if data.startswith('box_') or data.startswith('premium_box_') or data.startswith('daily_box_'):
        print(f"🔄 Передаем кнопку боксов в обработчик: {data}")
        new_update = Update(update.update_id, callback_query=query)
        return await box_button_handler(new_update, context)
    
    # ===== ИНВЕСТИЦИИ =====
    if data == "bank_investments":
        return await investment_menu(update, context)
    
    if data.startswith("invest_"):
        if data == "invest_my":
            return await my_investments(update, context)
        elif data == "invest_back":
            return await bank_menu(update, context)
        else:
            # Это invest_tech, invest_energy и т.д.
            return await invest_company(update, context)
    
    # ===== ОСТАЛЬНЫЕ КНОПКИ БАНКА =====
    if data == "bank_back":
        return await bank_menu(update, context)
    
    elif data == "bank_deposit_menu":
        keyboard = []
        for days, deposit_info in DEPOSIT_TYPES.items():
            keyboard.append([InlineKeyboardButton(
                f"{deposit_info['name']} (x{deposit_info['multiplier']}) - от {deposit_info['min_amount']:,} ₽",
                callback_data=f"bank_deposit_{days}"
            )])
        
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="bank_back")])
        
        await query.edit_message_text(
            "💰 Выберите тип депозита:\n\n"
            "Срок | Множитель | Мин. сумма\n"
            "---------------------------",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return BANK_MENU
    
    elif query.data.startswith("bank_deposit_"):
        days = int(query.data.split('_')[2])
        deposit_info = DEPOSIT_TYPES.get(days)
        if not deposit_info:
            await query.answer("❌ Неверный тип депозита", show_alert=True)
            return await bank_menu(update, context)
        
        context.user_data['deposit_days'] = days
        await query.edit_message_text(
            f"💰 Вы выбрали депозит: {deposit_info['name']} (x{deposit_info['multiplier']})\n\n"
            f"Минимальная сумма: {deposit_info['min_amount']:,} ₽\n"
            f"Ваш баланс: {user['balance']:,} ₽\n\n"
            f"Введите сумму депозита:"
        )
        return BANK_DEPOSIT
    
    elif query.data == "bank_withdraw":
        bank_balance = user.get('bank', {}).get('balance', 0)
        if bank_balance <= 0:
            await query.answer("❌ На вашем банковском счету нет средств", show_alert=True)
            return await bank_menu(update, context)
        
        user['balance'] += bank_balance
        amount = bank_balance
        user['bank']['balance'] = 0
        
        await query.edit_message_text(
            f"✅ Вы сняли {amount:,} ₽ с банковского счета.\n"
            f"💰 Ваш баланс: {user['balance']:,} ₽"
        )
        save_data()
        return await bank_menu(update, context)
    
    elif query.data == "bank_my_deposits":
        deposits = user.get('bank', {}).get('deposits', [])
        if not deposits:
            await query.answer("❌ У вас нет активных депозитов", show_alert=True)
            return await bank_menu(update, context)
        
        deposits_text = "📊 Ваши депозиты:\n\n"
        for i, deposit in enumerate(deposits, 1):
            end_time = datetime.fromtimestamp(deposit['end_time']).strftime('%d.%m.%Y %H:%M')
            if deposit.get('withdrawn', False):
                status = "✅ Завершен"
            elif deposit['end_time'] <= time.time():
                status = "🔄 Ожидает подтверждения"
            else:
                status = "⏳ Активен"
            
            deposits_text += (
                f"{i}. {deposit['amount']:,} ₽ на {deposit['days']} дней\n"
                f"   Множитель: x{deposit['multiplier']}\n"
                f"   Завершение: {end_time}\n"
                f"   Статус: {status}\n\n"
            )
        
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="bank_back")]]
        await query.edit_message_text(
            deposits_text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return BANK_MENU
    
    return await bank_menu(update, context)

async def work_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Единый обработчик для всех колбэков работ"""
    query = update.callback_query
    data = query.data
    
    print(f"work_callback: {data}")
    
    # ===== ОБРАБОТКА ТОПОВ =====
    if data.startswith("top_"):
        # Передаем в обработчик топов
        if data == "top_balance":
            return await top_balance(update, context, is_callback=True)
        elif data == "top_referrals":
            return await top_referrals(update, context, is_callback=True)
        elif data == "top_coins":
            return await top_coins(update, context, is_callback=True)
        elif data == "top_losses":
            return await top_losses(update, context, is_callback=True)
    
    # ===== ОБРАБОТКА КЛИКЕРА =====
    if data == "work_clicker":
        return await clicker_level_menu(update, context)
    
    if data.startswith("clicker_level_"):
        return await clicker_game_start(update, context)
    
    if data.startswith("clicker_click_"):
        return await clicker_click(update, context)
    
    if data == "clicker_exit":
        user_id = str(query.from_user.id)
        if user_id in clicker_games:
            del clicker_games[user_id]
        return await work_menu(update, context)
    
    # ===== ОБРАБОТКА РАБОТ =====
    if data == "work_back":
        return await work_menu(update, context)
    
    if data == "work_back_to_main":
        await query.answer()
        await query.edit_message_text(
            "Главное меню",
            reply_markup=get_main_keyboard()
        )
        return ConversationHandler.END
    
    if data.startswith("work_"):
        job_type = data.replace("work_", "")
        return await show_job_info(update, context, job_type)
    
    if data.startswith("start_work_"):
        job_type = data.replace("start_work_", "")
        await query.answer("⏳ Работа начата!")
        await start_work_job(update, context, job_type)
        return WORK_MENU
    
    await query.answer("❌ Неизвестная команда")
    return WORK_MENU
            
async def process_deposit_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Псевдоним для bank_deposit_handler"""
    return await bank_deposit_handler(update, context)

async def handle_trade_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await trade_start(update, context)
async def handle_casino_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await casino(update, context)

async def handle_box_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await box_menu(update, context)

async def error_handler(update: object, context: CallbackContext) -> None:
    logger.error("Exception while handling an update:", exc_info=context.error)

async def main():
    global ADMIN_GROUP_ID
    
    # Загружаем все данные
    load_data()  # Загружает user_data и banned_users
    load_user_items()
    load_casino_stats()
    load_checks()
    load_friends()
    load_investments()
    load_premium_items()
    load_token_balances()
    load_consumables()
    load_vip()
    load_user_settings()
    
    # ... остальной код ...
    
    # Правильное создание приложения
    application = Application.builder() \
        .token("8574924149:AAGVdijJMCv-qruSXIE5p9UsJcCzyYXLTnY") \
        .build()
    
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

    # Проверяем доступ к каналу для чеков
    try:
        chat = await application.bot.get_chat(CHECK_CHANNEL_ID)
        logging.info(f"Канал для чеков найден: {chat.title} (ID: {chat.id})")
    except Exception as e:
        logging.error(f"Ошибка доступа к каналу чеков: {e}")

    # ==================== НАСТРОЙКА ПЛАНИРОВЩИКОВ ====================
    job_queue = application.job_queue
    
    if job_queue:
        # Запускаем планировщик бизнесов
        
        job_queue.run_repeating(check_business_income, interval=60, first=10)
        logging.info("✅ Планировщик бизнесов запущен (проверка каждую минуту)")
        
        # Запускаем планировщик обновления username
        job_queue.run_repeating(update_usernames_job, interval=3600, first=10)
        logging.info("✅ Планировщик обновления username запущен (каждые 60 минут)")
        
        # Запускаем планировщик инвестиций
        # Проверка истекших VIP (раз в час)
        job_queue.run_repeating(check_expired_vip, interval=3600, first=60)
        job_queue.run_repeating(check_investments, interval=3600, first=60)
        logging.info("✅ Планировщик инвестиций запущен (каждые 60 минут)")
        
        # Ежедневный VIP бонус (в полночь)
        from datetime import time
        job_queue.run_daily(vip_daily_bonus, time=time(0, 0))
        logging.info("✅ Планировщик VIP бонусов запущен (каждый день в 00:00)")
    else:
        logging.warning("⚠️ JobQueue не доступен, планировщики не запущены")

    # ==================== СОЗДАЕМ ВСЕ CONVERSATION HANDLER ====================
    
    # Админский обработчик
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
            AWAITING_PROMO_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_promo_name)],
            AWAITING_PROMO_TYPE: [CallbackQueryHandler(process_promo_type, pattern=r"^promo_type_")],
            AWAITING_PROMO_VALUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_promo_value)],
            AWAITING_PROMO_USES: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_promo_uses)],
            AWAITING_PROMO_EXPIRE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_promo_expire),
                CallbackQueryHandler(process_promo_expire, pattern=r"^promo_")
            ],
            AWAITING_ADMIN_USERNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_admin_username)],
            AWAITING_ADMIN_LEVEL: [
                CallbackQueryHandler(process_admin_level, pattern=r"^(admin_level_|confirm_remove|cancel_remove)"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_admin_level)
            ],
            AWAITING_ADMIN_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_admin_password)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=False,
        name="admin_conversation"
    )
    
    # Казино
    casino_conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex(r"^(🎰 Казино|Казино)$"), casino),
            CommandHandler("casino", casino)
        ],
        states={
            BET_TYPE: [CallbackQueryHandler(handle_bet_type, pattern=r"^bet:")],
            BET_AMOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_bet_amount_with_donate),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=False,
        name="casino_conversation"
    )
    
    # Бизнесы
    business_conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex(r"^(🏢 Бизнесы|Бизнесы)$"), businesses_menu),
            CommandHandler("business", businesses_menu)
        ],
        states={
            BUY_BUSINESS: [CallbackQueryHandler(business_button_handler)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=False,
        name="business_conversation"
    )
    
    # Трейды
    trade_conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex(r"^(🔄 Трейды|Трейды)$"), trade_menu),
            CommandHandler("trade", trade_menu)
        ],
        states={
            TRADE_MENU: [CallbackQueryHandler(trade_button_handler, pattern=r"^trade_")],
            TRADE_CREATE: [CallbackQueryHandler(trade_create_handler, pattern=r"^trade_")],
            TRADE_OFFER: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, trade_offer_handler),
                CallbackQueryHandler(trade_offer_handler, pattern=r"^trade_")
            ],
            TRADE_ACCEPT: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_trade_action)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=False,
        name="trade_conversation"
    )

    # Боксы
    box_conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex(r"^(🎁 Боксы|Боксы)$"), box_menu),
            CommandHandler("boxes", box_menu)
        ],
        states={
            BOX_MENU: [CallbackQueryHandler(box_button_handler)],
            PREMIUM_BOX_MENU: [CallbackQueryHandler(box_button_handler)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=False,
        name="box_conversation"
    )
    
    # Банды
    gang_conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex(r"^(🏴 Банды|Банды)$"), gang_menu),
            CommandHandler("gang", gang_menu)
        ],
        states={
            GANG_MENU: [CallbackQueryHandler(gang_button_handler, pattern=r"^gang_")],
            GANG_CREATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, gang_create_process)],
            GANG_INVITE: [MessageHandler(filters.TEXT & ~filters.COMMAND, gang_invite_process)],
            GANG_DONATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, gang_donate_process)],
            GANG_WAR_TARGET: [CallbackQueryHandler(gang_button_handler, pattern=r"^gang_")],
            GANG_WAR_CONFIRM: [CallbackQueryHandler(gang_button_handler, pattern=r"^gang_")],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=False,
        name="gang_conversation"
    )
    
    # Магазин
    shop_conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex(r"^(🛒 Магазин|Магазин)$"), shop_menu),
            CommandHandler("shop", shop_menu)
        ],
        states={
            SHOP_MENU: [CallbackQueryHandler(shop_button_handler)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=False,
        name="shop_conversation"
    )
    
    # Банк
    bank_conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex(r"^(🏦 Банк|Банк)$"), bank_menu),
            CommandHandler("bank", bank_menu)
        ],
        states={
            BANK_MENU: [CallbackQueryHandler(bank_button_handler)],
            BANK_DEPOSIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, bank_deposit_handler)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=False,
        name="bank_conversation"
    )
    
    # Работы
    work_conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex(r"^(💼 Работа|💼РАБОТА|Работа)$"), work_menu),
            CommandHandler("work", work_menu)
        ],
        states={
            WORK_MENU: [
                CallbackQueryHandler(work_callback),
                MessageHandler(filters.Regex(r"^(💼 Работа|💼РАБОТА|Работа)$"), work_menu),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=False,
        name="work_conversation"
    )
    
    # Инвестиции
    invest_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(invest_company, pattern=r"^invest_(?!my$)(?!back$)")],
        states={
            INVEST_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_invest_amount)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        name="invest_conversation"
    )
    
    # ==================== ДОБАВЛЯЕМ ВСЕ ОБРАБОТЧИКИ ====================
    
    # 1. Сначала ConversationHandler-ы
    application.add_handler(admin_conv_handler)
    application.add_handler(casino_conv_handler)
    application.add_handler(business_conv_handler)
    application.add_handler(trade_conv_handler)
    application.add_handler(box_conv_handler)
    application.add_handler(gang_conv_handler)
    application.add_handler(shop_conv_handler)
    application.add_handler(bank_conv_handler)
    application.add_handler(work_conv_handler)
    application.add_handler(invest_conv_handler)
    
    # 2. Обработчик топов и настроек
    # Краш-игра
    application.add_handler(MessageHandler(
    filters.ChatType.GROUPS & filters.Regex(r"^(/crash|краш) "),
    crash_game
))
    application.add_handler(CallbackQueryHandler(crash_cashout, pattern=r"^crash_cashout_"))
    application.add_handler(CommandHandler("crashtop", crash_top))
    application.add_handler(CallbackQueryHandler(sell_coin_handler, pattern="^sell_coin$"))
    application.add_handler(MessageHandler(filters.Regex(r"^⚙️ Настройки$"), settings_menu))
    application.add_handler(CallbackQueryHandler(settings_callback, pattern=r"^settings_"))
    application.add_handler(CallbackQueryHandler(top_button_handler, pattern=r"^top_"))
    
    # 3. Команды для сброса
    # Добавьте после других команд
    application.add_handler(CommandHandler("rasil", broadcast_command))
    application.add_handler(CommandHandler("resetprog", reset_progress))
    application.add_handler(CallbackQueryHandler(reset_callback, pattern=r"^reset_"))
    
    # 4. Команды для чатов и групп
    application.add_handler(CommandHandler("chat", get_groups_command))
    
    # 5. Mines игра
    application.add_handler(CommandHandler("mines", open_mines))
    application.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, mines_webapp_data))
    application.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handle_mines_data))
    
    # 6. Магазин расходников
    application.add_handler(CallbackQueryHandler(shop_consumables_menu, pattern=r"^shop_consumables$"))
    application.add_handler(CallbackQueryHandler(consumables_buy, pattern=r"^consumables_buy_"))
    application.add_handler(CallbackQueryHandler(consumables_inventory, pattern=r"^consumables_inventory$"))
    application.add_handler(CallbackQueryHandler(consumables_sell_coin, pattern=r"^consumables_sell_coin$"))
    application.add_handler(CallbackQueryHandler(gift_select_friend, pattern=r"^gift_select_"))
    application.add_handler(CallbackQueryHandler(gift_send, pattern=r"^gift_send_"))
    application.add_handler(CallbackQueryHandler(gift_accept, pattern=r"^gift_accept_"))
    application.add_handler(CallbackQueryHandler(gift_decline, pattern=r"^gift_decline_"))
    application.add_handler(CommandHandler("gifts", my_gifts))
    
    # 7. PvP игры
    application.add_handler(MessageHandler(
        filters.ChatType.GROUPS & filters.Regex(r"^(/pvp|лот) "),
        pvp_dice
    ))
    application.add_handler(CallbackQueryHandler(pvp_accept, pattern=r"^pvp_accept_"))
    application.add_handler(CallbackQueryHandler(pvp_decline, pattern=r"^pvp_decline_"))
    application.add_handler(MessageHandler(
        filters.ChatType.GROUPS & filters.Regex(r"^(/dice|кости|Кости) "),
        dice_game
    ))
    
    # 8. Достижения
    application.add_handler(MessageHandler(
        filters.ALL & ~filters.COMMAND,
        auto_check_achievements
    ), group=-1)
    
    # 9. Основные команды
    application.add_handler(CommandHandler("token", give_tokens))
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("set_nick", set_nick))
    application.add_handler(CommandHandler("pay", pay))
    application.add_handler(CommandHandler("balance", balance))
    application.add_handler(CommandHandler("profile", profile))
    application.add_handler(CallbackQueryHandler(profile_callback, pattern=r"^profile_"))
    application.add_handler(CommandHandler("promo", promo))
    
    # 10. Подтверждение переводов
    application.add_handler(CallbackQueryHandler(confirm_transfer_callback, pattern=r"^confirm_transfer_"))
    
    # 11. Бан/разбан в группах
    application.add_handler(CommandHandler("ban", group_ban))
    application.add_handler(CommandHandler("unban", group_unban))
    
    # 12. Топы
    application.add_handler(CommandHandler("top_balance", top_balance))
    application.add_handler(CommandHandler("top_referrals", top_referrals))
    application.add_handler(CommandHandler("top_coins", top_coins))
    application.add_handler(CommandHandler("top_losses", top_losses))
    
    # 13. БСК
    application.add_handler(CommandHandler("bsk_rules", bsk_rules))
    
    # 14. Чеки
    application.add_handler(CommandHandler("check", create_check))
    application.add_handler(CommandHandler("check_stats", check_stats))
    application.add_handler(CommandHandler("cancel_check", cancel_check))
    
    # 15. Друзья
    application.add_handler(CommandHandler("friend", friend_command))
    application.add_handler(CommandHandler("friends", friend_list))
    application.add_handler(CommandHandler("friend_requests", friend_requests_list))
    application.add_handler(CommandHandler("friend_accept", friend_accept))
    application.add_handler(CommandHandler("friend_decline", friend_decline))
    
    # 16. Инвестиции
    application.add_handler(CommandHandler("invest_claim", claim_investment))
    
    # 17. Обработчики reply-кнопок
    application.add_handler(MessageHandler(filters.Regex(r"^🎰Казино$"), casino))
    application.add_handler(MessageHandler(filters.Regex(r"^🏦Банк$"), bank_menu))
    application.add_handler(MessageHandler(filters.Regex(r"^💼Работа$"), work_menu))
    application.add_handler(MessageHandler(filters.Regex(r"^🏢 Бизнесы$"), businesses_menu))
    application.add_handler(MessageHandler(filters.Regex(r"^🏴 Банды$"), gang_menu))
    application.add_handler(MessageHandler(filters.Regex(r"^📊 Профиль$"), profile))
    application.add_handler(MessageHandler(filters.Regex(r"^💰 Баланс$"), balance))
    application.add_handler(MessageHandler(filters.Regex(r"^🏆 Топы$"), handle_tops_button))
    application.add_handler(MessageHandler(filters.Regex(r"^🔄 Трейды$"), trade_menu))
    application.add_handler(MessageHandler(filters.Regex(r"^🎁 Боксы$"), box_menu))
    application.add_handler(MessageHandler(filters.Regex(r"^🛒 Магазин$"), shop_menu))
    
    # 18. Единый обработчик для групп
    application.add_handler(MessageHandler(
        filters.ChatType.GROUPS & filters.TEXT & ~filters.COMMAND,
        handle_group_message
    ))
    
    # 19. Обработчик для активации чеков
    application.add_handler(CallbackQueryHandler(activate_check_handler, pattern=r"^activate_check_"))
    
    # 20. Обработчик ошибок
    application.add_error_handler(error_handler)

    # Запускаем бота
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    
    logging.info("✅ Бот успешно запущен!")
    
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
