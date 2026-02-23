# Godzo Project

Majburiy obuna tekshiruvi bor Telegram bot (aiogram 3 + webhook).

## Features

- `/start` da obuna tekshiruvi.
- Obuna bolmagan user uchun kanal tugmalari va `Tekshirish` callback.
- Qattiq gate: obuna bolmagan user oddiy xabarda ham bloklanadi.
- `GET /health` endpoint.
- `POST /webhook/{WEBHOOK_SECRET}` endpoint.

## Requirements

- Python 3.10+
- Telegram bot token
- Bot required kanallarda admin bolishi tavsiya etiladi

## Install

```bash
pip install -r requirements.txt
```

## Environment

`.env.example` ni nusxa qilib `.env` yarating:

```env
BOT_TOKEN=123456:ABCDEF
WEBHOOK_BASE_URL=https://your-app.onrender.com
WEBHOOK_SECRET=replace-with-random-secret
REQUIRED_CHATS=@kanal1,@kanal2
PORT=8080
```

## Run

```bash
python main.py
```

## Railway/Render Deploy

1. Repo ni Railway yoki Render ga ulang.
2. Environment variables ni kiriting (`BOT_TOKEN`, `WEBHOOK_BASE_URL`, `WEBHOOK_SECRET`, `REQUIRED_CHATS`, `PORT`).
3. Start command: `python main.py`.
4. Deploydan keyin `https://your-domain/health` ni tekshiring.
5. Telegramda `/start` qilib obuna gate ishlashini tekshiring.

## Manual Verification

1. Obuna bolmagan account bilan `/start` bosing: kanal tugmalari chiqishi kerak.
2. Kanallarga obuna bolib `Tekshirish` ni bosing.
3. Tasdiqlangandan keyin `Obuna tasdiqlandi, xush kelibsiz!` chiqishi kerak.
