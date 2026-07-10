import asyncio
import html
import logging
import os

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from deep_translator import GoogleTranslator
from dotenv import load_dotenv

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

LANGUAGES = {
    "uz": "🇺🇿 O'zbekcha",
    "en": "🇬🇧 Inglizcha",
    "ru": "🇷🇺 Ruscha",
    "tr": "🇹🇷 Turkcha",
    "ar": "🇸🇦 Arabcha",
    "de": "🇩🇪 Nemischa",
}


class Translate(StatesGroup):
    waiting_language = State()


dp = Dispatcher(storage=MemoryStorage())


def language_keyboard():
    builder = InlineKeyboardBuilder()
    for code, name in LANGUAGES.items():
        builder.button(text=name, callback_data=f"lang:{code}")
    builder.adjust(2)
    return builder.as_markup()


@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "🌐 <b>Tarjimon Bot</b>ga xush kelibsiz!\n\n"
        "Tarjima qilish uchun so'z yoki matn yuboring."
    )


@dp.message(F.text)
async def receive_text(message: Message, state: FSMContext):
    await state.update_data(text=message.text)
    await state.set_state(Translate.waiting_language)
    await message.answer("Qaysi tilga tarjima qilay?", reply_markup=language_keyboard())


@dp.callback_query(F.data.startswith("lang:"))
async def do_translate(callback: CallbackQuery, state: FSMContext):
    target = callback.data.split(":", 1)[1]
    data = await state.get_data()
    text = data.get("text")
    await callback.answer()

    if not text:
        await callback.message.answer("Avval tarjima qilinadigan matnni yuboring.")
        return

    try:
        translated = await asyncio.to_thread(
            GoogleTranslator(source="auto", target=target).translate, text
        )
    except Exception:
        await callback.message.answer("❌ Tarjimada xatolik yuz berdi. Qayta urinib ko'ring.")
        return

    await callback.message.answer(
        f"✅ <b>{LANGUAGES[target]}</b>:\n\n{html.escape(translated or '')}"
    )
    await state.clear()


async def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN topilmadi. .env faylini to'ldiring.")
    bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
