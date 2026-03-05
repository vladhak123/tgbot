import os
import json
import logging
from collections import defaultdict, deque
from openai import OpenAI
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    filters, ContextTypes
)

# ──────────────────────────────────────────────
# НАСТРОЙКИ
# ──────────────────────────────────────────────
TELEGRAM_TOKEN = "8630509629:AAEgI-20rf8XJtO-1qdYuhmHe4-bJvH6Ysk"
DEEPSEEK_API_KEY = "sk-9561fb8381ba42e6aebe7a82e6cd6971"
BOT_NAME = "Братик"          # как бот представляется
MAX_HISTORY = 150             # сообщений в памяти на чат
# ──────────────────────────────────────────────

SYSTEM_PROMPT = f"""Ты — {BOT_NAME}, свой пацан в групповом чате который шарит за многое.
Пишешь как человек в телеграме — живо, без официоза.
Никаких скобок с действиями типа (смеясь) или (задумчиво) — просто текст.
Когда спрашивают что-то интересное или просят объяснить — отвечаешь развёрнуто, с деталями, это интересно.
Когда просто треплются — отвечаешь коротко и по-пацански.
Троллишь и подкалываешь, но с умом.
Если кто грузится — поддержишь без сюсюканья.
Материшься умеренно, только к месту.
Помнишь о чём говорили раньше, используешь это в разговоре.
Своё мнение имеешь и отстаиваешь его.
Зовут тебя {BOT_NAME}."""

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Клиент DeepSeek (совместим с OpenAI SDK)
client = OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com"
)

# Память: chat_id -> deque of {role, content}
memory: dict[int, deque] = defaultdict(lambda: deque(maxlen=MAX_HISTORY))


def ask_deepseek(chat_id: int, user_message: str, user_name: str) -> str:
    """Отправляет запрос в DeepSeek с историей чата."""
    history = memory[chat_id]
    history.append({"role": "user", "content": f"{user_name}: {user_message}"})

    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + list(history)

    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            max_tokens=500,
            temperature=0.85,
        )
        reply = response.choices[0].message.content.strip()
        history.append({"role": "assistant", "content": reply})
        return reply
    except Exception as e:
        logger.error(f"DeepSeek error: {e}")
        return "Братан, что-то у меня голова не варит щас, попробуй позже 🤷"


# ──────────────────────────────────────────────
# ХЕНДЛЕРЫ
# ──────────────────────────────────────────────

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"Здарова, я {BOT_NAME} 🤙 Пишите, отвечу."
    )


async def clear(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Очищает память для этого чата."""
    memory[update.effective_chat.id].clear()
    await update.message.reply_text("Память очищена, начинаем с чистого листа 🧹")


async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.text:
        return

    chat_id = update.effective_chat.id
    user_name = msg.from_user.first_name or "Аноним"
    text = msg.text.strip()
    bot_username = (await ctx.bot.get_me()).username

    is_private = update.effective_chat.type == "private"
    is_reply_to_bot = (
        msg.reply_to_message and
        msg.reply_to_message.from_user and
        msg.reply_to_message.from_user.username == bot_username
    )
    is_mentioned = bot_username and f"@{bot_username}" in text
    is_name_mentioned = BOT_NAME.lower() in text.lower()

    # В группе реагируем только если: упомянули / ответили на сообщение бота / назвали по имени
    if not is_private and not is_reply_to_bot and not is_mentioned and not is_name_mentioned:
        return

    # Убираем упоминание из текста
    clean_text = text.replace(f"@{bot_username}", "").strip() if bot_username else text

    logger.info(f"[{chat_id}] {user_name}: {clean_text}")

    await ctx.bot.send_chat_action(chat_id=chat_id, action="typing")
    reply = ask_deepseek(chat_id, clean_text, user_name)
    await msg.reply_text(reply)


# ──────────────────────────────────────────────
# ЗАПУСК
# ──────────────────────────────────────────────

def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("clear", clear))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info(f"Бот {BOT_NAME} запущен...")
    app.run_polling()


if __name__ == "__main__":
    main()
