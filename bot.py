import os
import random
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
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "8630509629:AAEgI-20rf8XJtO-1qdYuhmHe4-bJvH6Ysk")
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "sk-9561fb8381ba42e6aebe7a82e6cd6971")
BOT_NAME = "Братик"
MAX_HISTORY = 30          # сколько сообщений помнит
MAX_USER_FACTS = 10       # сколько фактов помнит о каждом пацане
RANDOM_REPLY_CHANCE = 0.30  # шанс сам влезть в разговор (30%)
# ──────────────────────────────────────────────

SYSTEM_PROMPT = f"""
пацан в чате
пишешь как в телеге — коротко, строчными, без точек в конце
никогда не придумываешь то чего не было в переписке — только то что реально писали
если не понял о чём речь — спроси коротко, не додумывай
Ты — {BOT_NAME}, свой пацан в групповом чате который шарит за многое.
Пишешь как человек в телеграме — живо, без официоза.
Никаких скобок с действиями типа (смеясь) или (задумчиво) — просто текст.
Когда спрашивают что-то интересное или просят объяснить — отвечаешь развёрнуто, с деталями.
Когда просто треплются — отвечаешь коротко и по-пацански.
Троллишь и подкалываешь, но с умом.
Если кто грузится — поддержишь без сюсюканья.
Материшься умеренно, только к месту.
Помнишь о чём говорили раньше, используешь это в разговоре.
Знаешь пацанов в чате — их интересы, привычки, о чём они говорят.
Своё мнение имеешь и отстаиваешь его.
Зовут тебя {BOT_NAME}."""

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")

# Память чата — все сообщения подряд
chat_history: dict[int, deque] = defaultdict(lambda: deque(maxlen=MAX_HISTORY))

# Память о пацанах — что знаем о каждом
user_facts: dict[int, dict[str, deque]] = defaultdict(
    lambda: defaultdict(lambda: deque(maxlen=MAX_USER_FACTS))
)


def build_user_context(chat_id: int) -> str:
    """Собирает контекст о пацанах для промпта."""
    facts = user_facts[chat_id]
    if not facts:
        return ""
    lines = ["Что знаешь о пацанах в этом чате:"]
    for name, user_deque in facts.items():
        if user_deque:
            lines.append(f"- {name}: {', '.join(user_deque)}")
    return "\n".join(lines)


def extract_user_fact(name: str, message: str, chat_id: int):
    """Простое извлечение фактов о пользователе из сообщения."""
    keywords = [
        "люблю", "играю", "смотрю", "работаю",
        "занимаюсь", "хочу", "купил", "еду", "слушаю"
    ]
    msg_lower = message.lower()
    for kw in keywords:
        if kw in msg_lower:
            idx = msg_lower.index(kw)
            snippet = message[idx:idx+60].strip()
            user_facts[chat_id][name].append(snippet)
            break


def ask_deepseek(chat_id: int, prompt_override: str = None) -> str:
    """Запрос к DeepSeek с полной историей чата."""
    history = list(chat_history[chat_id])
    user_context = build_user_context(chat_id)

    system = SYSTEM_PROMPT
    if user_context:
        system += f"\n\n{user_context}"

    messages = [{"role": "system", "content": system}]

    if prompt_override:
        messages.append({"role": "user", "content": prompt_override})
    else:
        messages += history

    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            max_tokens=600,
            temperature=0.9,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"DeepSeek error: {e}")
        return None


async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Здарова, я {BOT_NAME} 🤙")


async def clear(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    chat_history[chat_id].clear()
    user_facts[chat_id].clear()
    await update.message.reply_text("Память очищена 🧹")


async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.text:
        return

    chat_id = update.effective_chat.id
    text = msg.text.strip()
    user_name = msg.from_user.first_name or "Аноним"
    bot_username = (await ctx.bot.get_me()).username
    is_private = update.effective_chat.type == "private"

    # Всегда пишем сообщение в историю (читаем весь чат)
    chat_history[chat_id].append({
        "role": "user",
        "content": f"{user_name}: {text}"
    })

    # Пробуем вытащить факт о пользователе
    extract_user_fact(user_name, text, chat_id)

    # Определяем надо ли отвечать
    is_reply_to_bot = (
        msg.reply_to_message and
        msg.reply_to_message.from_user and
        msg.reply_to_message.from_user.username == bot_username
    )
    is_mentioned = bot_username and f"@{bot_username}" in text
    is_name_mentioned = BOT_NAME.lower() in text.lower()
    should_reply = is_private or is_reply_to_bot or is_mentioned or is_name_mentioned

    # Случайно влезаем в разговор
    random_jump = not should_reply and random.random() < RANDOM_REPLY_CHANCE

    if not should_reply and not random_jump:
        return

    await ctx.bot.send_chat_action(chat_id=chat_id, action="typing")

    if random_jump:
        prompt = (
            f"Ты читал переписку в чате. Вот последнее сообщение от {user_name}: «{text}». "
            f"Влезь в разговор как свой пацан — коротко, к месту. "
            f"Можешь поддержать, подколоть или добавить что-то интересное."
        )
        reply = ask_deepseek(chat_id, prompt_override=prompt)
    else:
        reply = ask_deepseek(chat_id)

    if reply:
        chat_history[chat_id].append({
            "role": "assistant",
            "content": reply
        })
        await msg.reply_text(reply)


def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("clear", clear))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info(f"Бот {BOT_NAME} запущен...")
    app.run_polling()


if __name__ == "__main__":
    main()