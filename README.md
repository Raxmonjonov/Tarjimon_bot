# 🌐 Tarjimon Bot

So'z va matnlarni boshqa tillarga tarjima qiluvchi Telegram bot.

## ✨ Imkoniyatlar
- Matnni avtomatik aniqlab, tanlangan tilga tarjima qilish
- 6 ta til: o'zbek, ingliz, rus, turk, arab, nemis
- Inline tugmalar orqali til tanlash

## 🛠 Texnologiyalar
- Python 3.11+
- [aiogram 3.x](https://docs.aiogram.dev/) (FSM)
- [deep-translator](https://pypi.org/project/deep-translator/) (Google Translate) — API kalit shart emas

## 🚀 O'rnatish

1. Kutubxonalarni o'rnating:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate      # Windows
   pip install -r requirements.txt
   ```

2. `.env.example` dan nusxa olib `.env` yarating:
   ```
   BOT_TOKEN=...
   ```
   `BOT_TOKEN` ni [@BotFather](https://t.me/BotFather) dan oling.

3. Ishga tushiring:
   ```bash
   python main.py
   ```

## 💬 Foydalanish
- `/start` — botni ishga tushirish
- Matn yuboring → tarjima tilini tanlang → natijani oling
