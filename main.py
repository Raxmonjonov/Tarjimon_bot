"""
Tarjimon Bot — Production Ready
Google Translate orqali 10 tilda tarjima
"""

import asyncio
import html
import logging
import os
import time

import aiosqlite
from aiogram import Bot, Dispatcher, F, BaseMiddleware
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.exceptions import TelegramAPIError
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from deep_translator import GoogleTranslator
from dotenv import load_dotenv

# ─── Konfiguratsiya ─────────────────────────────────────────────────
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]
DB_PATH = os.getenv("DB_PATH", "tarjimon.db")
THROTTLE_RATE = float(os.getenv("THROTTLE_RATE", "0.5"))

# ─── Logging ────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler("bot.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("tarjimon-bot")

# ─── Til ro'yxati ──────────────────────────────────────────────────
LANGUAGES = {
    "uz": "🇺🇿 O'zbek",
    "en": "🇬🇧 Ingliz",
    "ru": "🇷🇺 Rus",
    "tr": "🇹🇷 Turk",
    "ar": "🇸🇦 Arab",
    "de": "🇩🇪 Nemis",
    "fr": "🇫🇷 Fransuz",
    "es": "🇪🇸 Ispan",
    "zh-CN": "🇨🇳 Xitoy",
    "ko": "🇰🇷 Koreys",
}

# ─── Database ───────────────────────────────────────────────────────
async def init_db():
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS translations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    source_text TEXT NOT NULL,
                    target_lang TEXT NOT NULL,
                    result TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    full_name TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.commit()
        logger.info("Database muvaffaqiyatli ishga tushirildi: %s", DB_PATH)
    except Exception as e:
        logger.error("Database xatosi: %s", e)
        raise


async def add_user(user_id: int, username: str | None, full_name: str | None):
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                INSERT OR IGNORE INTO users (user_id, username, full_name)
                VALUES (?, ?, ?)
            """, (user_id, username, full_name))
            await db.execute("""
                UPDATE users SET username = ?, full_name = ?, last_active = CURRENT_TIMESTAMP
                WHERE user_id = ?
            """, (username, full_name, user_id))
            await db.commit()
    except Exception as e:
        logger.error("User qo'shishda xato: %s", e)


async def save_translation(user_id: int, source: str, lang: str, result: str):
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO translations (user_id, source_text, target_lang, result) VALUES (?, ?, ?, ?)",
                (user_id, source[:500], lang, result[:500]),
            )
            await db.commit()
    except Exception as e:
        logger.error("Tarjimani saqlashda xato: %s", e)


async def get_stats() -> dict:
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            row = await db.execute("SELECT COUNT(*) FROM users")
            users = (await row.fetchone())[0]
            row = await db.execute("SELECT COUNT(*) FROM translations")
            trans = (await row.fetchone())[0]
            row = await db.execute(
                "SELECT target_lang, COUNT(*) as cnt FROM translations GROUP BY target_lang ORDER BY cnt DESC LIMIT 5"
            )
            top_langs = await row.fetchall()
            return {"users": users, "translations": trans, "top_langs": top_langs}
    except Exception as e:
        logger.error("Statistika xatosi: %s", e)
        return {"users": 0, "translations": 0, "top_langs": []}


# ─── Middleware ──────────────────────────────────────────────────────
class ThrottlingMiddleware(BaseMiddleware):
    def __init__(self, rate: float = 0.5):
        self.rate = rate
        self.user_timestamps: dict[int, float] = {}
        super().__init__()

    async def __call__(self, handler, event, data):
        user_id = event.from_user.id
        now = time.time()
        last = self.user_timestamps.get(user_id, 0)
        if now - last < self.rate:
            return
        self.user_timestamps[user_id] = now
        return await handler(event, data)


class ErrorMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        try:
            return await handler(event, data)
        except TelegramAPIError as e:
            logger.error("Telegram API xatosi: %s", e)
        except Exception as e:
            logger.error("Kutilmagan xatolik: %s", e, exc_info=True)
            try:
                if isinstance(event, Message):
                    await event.answer("❌ Xatolik yuz berdi. Qayta urinib ko'ring.")
                elif isinstance(event, CallbackQuery):
                    await event.answer("Xatolik yuz berdi.", show_alert=True)
            except Exception:
                pass


# ─── Dispatcher ─────────────────────────────────────────────────────
dp = Dispatcher(storage=MemoryStorage())
dp.message.middleware(ThrottlingMiddleware(THROTTLE_RATE))
dp.message.middleware(ErrorMiddleware())
dp.callback_query.middleware(ThrottlingMiddleware(THROTTLE_RATE))
dp.callback_query.middleware(ErrorMiddleware())


# ─── FSM ────────────────────────────────────────────────────────────
class TranslateState(StatesGroup):
    waiting_language = State()


# ─── Keyboardlar ────────────────────────────────────────────────────
def language_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for code, name in LANGUAGES.items():
        builder.button(text=name, callback_data=f"lang:{code}")
    builder.adjust(2)
    return builder.as_markup()


# ─── Handlerlar ─────────────────────────────────────────────────────
@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    try:
        await state.clear()
        await add_user(message.from_user.id, message.from_user.username, message.from_user.full_name)
        logger.info("Start — user %d (@%s)", message.from_user.id, message.from_user.username)
        await message.answer(
            "🌐 <b>Tarjimon Bot</b>ga xush kelibsiz!\n\n"
            "Matn yuboring — men tarjima qilaman.\n\n"
            f"🌐 {len(LANGUAGES)} ta til qo'llab-quvvatlanadi."
        )
    except Exception as e:
        logger.error("Start handler xatosi: %s", e)


@dp.message(Command("help"))
async def cmd_help(message: Message):
    try:
        await message.answer(
            "🌐 <b>Tarjimon Bot</b> — Yordam\n\n"
            "📋 <b>Buyruqlar:</b>\n"
            "• /start — Botni qayta ishga tushirish\n"
            "• /help — Yordam\n"
            "• /stats — Statistika\n\n"
            "📝 <b>Foydalanish:</b>\n"
            "1. Matn yuboring\n"
            "2. Tilni tanlang\n"
            "3. Tarjimani oling\n\n"
            f"🌐 Qo'llab-quvvatlanadigan tillar: {len(LANGUAGES)}"
        )
    except Exception as e:
        logger.error("Help handler xatosi: %s", e)


@dp.message(Command("stats"))
async def cmd_stats(message: Message):
    try:
        if message.from_user.id not in ADMIN_IDS:
            await message.answer("⛔ Sizda ruxsat yo'q.")
            return
        stats = await get_stats()
        text = (
            "📊 <b>Bot Statistikasi</b>\n\n"
            f"👥 Foydalanuvchilar: {stats['users']}\n"
            f"🔄 Tarjimalar: {stats['translations']}\n\n"
            "🏅 <b>Eng ko'p tarjima qilingan tillar:</b>\n"
        )
        for lang, cnt in stats["top_langs"]:
            name = LANGUAGES.get(lang, lang)
            text += f"  • {name}: {cnt} marta\n"
        await message.answer(text)
    except Exception as e:
        logger.error("Stats handler xatosi: %s", e)


@dp.message(StateFilter(None), F.text)
async def receive_text(message: Message, state: FSMContext):
    try:
        if not message.text or len(message.text.strip()) == 0:
            await message.answer("❌ Matn yuboring.")
            return
        if len(message.text) > 4096:
            await message.answer("❌ Matn juda uzun. 4096 belgidan kam yozing.")
            return
        await state.update_data(text=message.text.strip())
        await state.set_state(TranslateState.waiting_language)
        logger.info("Matn qabul qilindi — user %d: %s...", message.from_user.id, message.text[:30])
        await message.answer("🌐 Qaysi tilga tarjima qilay?", reply_markup=language_keyboard())
    except Exception as e:
        logger.error("Matn qabul qilish xatosi: %s", e)


@dp.callback_query(F.data.startswith("lang:"), TranslateState.waiting_language)
async def do_translate(callback: CallbackQuery, state: FSMContext):
    try:
        target = callback.data.split(":", 1)[1]
        if target not in LANGUAGES:
            await callback.answer("❌ Noto'g'ri tanlandi.", show_alert=True)
            return

        data = await state.get_data()
        text = data.get("text")
        await callback.answer()
        await state.clear()

        if not text:
            await callback.message.answer("❌ Avval matn yuboring.")
            return

        await callback.message.bot.send_chat_action(callback.message.chat.id, "typing")
        try:
            translated = await asyncio.to_thread(
                GoogleTranslator(source="auto", target=target).translate, text
            )
        except Exception as e:
            logger.error("Tarjima xatosi: %s", e)
            await callback.message.answer("❌ Tarjimada xatolik. Qayta urinib ko'ring.")
            return

        if not translated:
            await callback.message.answer("❌ Tarjima natijasi bo'sh.")
            return

        result = translated
        if len(result) > 4096:
            result = result[:4090] + "..."

        await save_translation(callback.from_user.id, text, target, result)
        logger.info("Tarjama — user %d: %s → %s", callback.from_user.id, target, result[:30])

        await callback.message.answer(
            f"✅ <b>{LANGUAGES[target]}</b>:\n\n{html.escape(result)}",
            reply_markup=language_keyboard(),
        )
    except Exception as e:
        logger.error("Tarjima handler xatosi: %s", e)


# ─── Bot ishga tushirish ───────────────────────────────────────────
async def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN topilmadi. .env faylini to'ldiring.")
    await init_db()
    bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    me = await bot.get_me()
    logger.info("🤖 Tarjimon Bot ishga tushdi! (@%s)", me.username)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
