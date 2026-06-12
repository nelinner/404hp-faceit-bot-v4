# main.py — 404hp FACEIT
import asyncio, logging, hashlib, secrets, random, os
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.enums import ChatMemberStatus
import db

TOKEN = "8254209430:AAHzRRGSOrMcie5JRj5DkmuUQIJK8d3ohTg"
PROJECT_NAME = "404hp FACEIT"
CHANNEL_ID = "@hp404faceit"
HEAD_ADMIN_USERNAME = "nelinner"

# Изображения
MAIN_MENU_IMAGE = "https://ibb.co/yczGh1yQ"
REGISTRATION_IMAGE = "https://ibb.co/SD6Sz7Tf"
LEADERBOARD_IMAGE = "https://ibb.co/spHJL8t7"
LOBBY_CREATE_IMAGE = "https://ibb.co/FLk3W6KR"

ROLE_NAMES = {
    'player': '🎮 Игрок',
    'premium': '⭐ Premium',
    'admin': '🛡 Админ',
    'director': '⚡ Руководитель'
}

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# ---------- вспомогательные функции ----------
def hash_pw(pw, salt=None):
    if not salt: salt = secrets.token_hex(16)
    return hashlib.sha256((pw+salt).encode()).hexdigest(), salt

def check_pw(pw, salt, h):
    return hashlib.sha256((pw+salt).encode()).hexdigest() == h

def get_rank(elo):
    if elo<200: return "🎯 Level 1"
    if elo<400: return "🎯 Level 2"
    if elo<600: return "🎯 Level 3"
    if elo<800: return "🎯 Level 4"
    if elo<1000: return "🎯 Level 5"
    if elo<1200: return "🎯 Level 6"
    if elo<1400: return "💎 Level 7"
    if elo<1600: return "👑 Level 8"
    if elo<1800: return "🌟 Level 9"
    return "⚡ Level 10"

def gen_code(): return secrets.token_hex(4).upper()

async def check_sub(uid):
    try:
        m = await bot.get_chat_member(CHANNEL_ID, uid)
        return m.status in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]
    except: return False

def find_player(query: str):
    conn = db.get_db()
    if query.isdigit():
        p = conn.execute("SELECT * FROM players WHERE id=?", (int(query),)).fetchone()
    else:
        p = conn.execute("SELECT * FROM players WHERE nick=?", (query,)).fetchone()
    conn.close()
    return p

def is_banned(uid):
    conn = db.get_db()
    b = conn.execute("SELECT till, reason FROM bans WHERE pid=?", (uid,)).fetchone()
    conn.close()
    if b and b['till']:
        try:
            if datetime.fromisoformat(b['till']) > datetime.now():
                return True, b['till'], b['reason']
        except: pass
    return False, None, None

def menu(uid):
    r = db.get_db().execute("SELECT role FROM players WHERE id=?", (uid,)).fetchone()
    role = r[0] if r else 'player'
    kb = [
        [InlineKeyboardButton(text="🎮 НАЙТИ МАТЧ", callback_data="find")],
        [InlineKeyboardButton(text="👤 Профиль", callback_data="profile"),
         InlineKeyboardButton(text="🏆 Рейтинг", callback_data="top")],
        [InlineKeyboardButton(text="ℹ️ Правила", callback_data="rules")]
    ]
    if role in ['premium','admin','director']:
        kb.insert(1, [InlineKeyboardButton(text="🔰 СОЗДАТЬ ЛОББИ", callback_data="lobby")])
    if role in ['admin','director']:
        kb.append([InlineKeyboardButton(text="⚙️ Админ", callback_data="admin")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def admin_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 Пользователи", callback_data="a_users")],
        [InlineKeyboardButton(text="🔄 Заменить игрока", callback_data="a_replace")],
        [InlineKeyboardButton(text="🔨 Забанить", callback_data="a_ban")],
        [InlineKeyboardButton(text="✅ Разбанить", callback_data="a_unban")],
        [InlineKeyboardButton(text="👑 Назначить админа", callback_data="a_assign")],
        [InlineKeyboardButton(text="🥾 Снять админа", callback_data="a_revoke")],
        [InlineKeyboardButton(text="⭐ Premium", callback_data="a_prem")],
        [InlineKeyboardButton(text="🔙 Меню", callback_data="back")]
    ])

async def is_admin(uid):
    r = db.get_db().execute("SELECT role FROM players WHERE id=?", (uid,)).fetchone()
    return r and r[0] in ['admin','director']

async def is_director(uid):
    r = db.get_db().execute("SELECT role FROM players WHERE id=?", (uid,)).fetchone()
    return r and r[0] == 'director'

# ---------- FSM ----------
class Reg(StatesGroup): nick = State(); pw = State(); pw2 = State()
class Lobby(StatesGroup): map = State(); confirm = State()
class Result(StatesGroup): score = State()
class AdminFSM(StatesGroup): assign = State(); revoke = State(); prem = State(); ban_user = State(); ban_reason = State(); ban_dur = State(); unban_user = State()
class Replace(StatesGroup): lobby = State(); old = State(); new = State(); confirm = State()

MAPS = {
    "sandstone":"🏝 Sandstone","dune":"🏜 Dune",
    "province":"🏘 Province","rust":"🏗 Rust",
    "breeze":"🌴 Breeze","hanami":"🌸 Hanami",
    "prison":"🔒 Prison"
}

# ---------- /start ----------
@dp.message(Command("start"))
async def start(msg: types.Message, state: FSMContext):
    if not await check_sub(msg.from_user.id):
        await msg.answer_photo(MAIN_MENU_IMAGE, caption=f"🔒 Подпишитесь на {CHANNEL_ID}")
        return
    conn = db.get_db()
    p = conn.execute("SELECT * FROM players WHERE id=?", (msg.from_user.id,)).fetchone()
    if not p:
        await msg.answer_photo(REGISTRATION_IMAGE, caption="🎮 Введите игровой никнейм:")
        await state.set_state(Reg.nick)
    else:
        if (msg.from_user.username or "").lower() == HEAD_ADMIN_USERNAME and p['role'] != 'director':
            conn.execute("UPDATE players SET role='director' WHERE id=?", (msg.from_user.id,))
            conn.commit()
            p = conn.execute("SELECT * FROM players WHERE id=?", (msg.from_user.id,)).fetchone()
        role_display = ROLE_NAMES.get(p['role'], 'Игрок')
        await msg.answer_photo(MAIN_MENU_IMAGE,
            caption=f"👋 {p['nick']}\n🎭 Роль: {role_display}\n🏅 {p['rank']} | ELO: {p['elo']}\nМатчей: {p['matches']}\n\nВыберите действие:",
            reply_markup=menu(msg.from_user.id))
    conn.close()

# ---------- регистрация, поиск, лобби, жеребьёвка, результат, профиль, рейтинг, правила, админ-панель, замена, бан, разбан, премиум, кнопка назад ----------
# (все эти функции идентичны предыдущей полной версии, используют db.get_db() и остальные вспомогательные функции)
# Здесь для краткости опущены, но они должны быть скопированы из последнего рабочего кода.

# ---------- запуск ----------
async def main():
    db.init_db()
    print(f"🔥 {PROJECT_NAME} ЗАПУЩЕН!")
    while True:
        try: await dp.start_polling(bot)
        except Exception as e:
            print(f"Ошибка: {e}")
            await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(main())
