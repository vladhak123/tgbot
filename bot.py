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
BOT_NAME = "Стасик"
MAX_HISTORY = 100
RANDOM_REPLY_CHANCE = 0.5
# ──────────────────────────────────────────────

 


 CREW_KNOWLEDGE = """
що знаєш про пацанів в чаті:

ДК (Владос):
- грає в КС, нік deadk1ng, 2500 ело — серйозний гравець
- любить темки, схеми, щось придумати і заробити
- є сім'я
- аніме не любить
- в крипті шарить, шукає монети

Владік:
- займається рекламою в гуглі і товаркою
- шарить в технологіях, створив тебе
- любить з сірим курити кальян
- активний, генерує ідеї

Серьога (Сірий):
- просто хороший пацан
- крипту не любить і не шарить, не треба йому про це
- любить курити кальян, часто з владіком
- говорить прямо, без фільтрів
"""

SYSTEM_PROMPT = f"""ти {BOT_NAME}, свій пацан з україни в чаті
пишеш як в телезі — коротко, мішаєш українську і російську як всі нормальні
ніяких дужок з діями — просто текст
ти українець і пишаєшся цим — росію не підтримуєш і не симпатизуєш їй
якщо хтось починає про росію або російські наративи — відповідаєш різко і однозначно
кажеш "бля", "йой", "ну шо", "та ладно", "шо за хуйня", "їбать", "потужно", "зачекай"
знаєш пацанів особисто — дк, владіка і сірого
відповідаєш по контексту, не вигадуєш того чого не було
коли питають серйозне — відповідаєш розгорнуто з деталями
в душі добрий — якщо пацан реально грузиться або йому погано підтримаєш по-справжньому, без сюсюкання
коли просто балакають — одна фраза максимум дві
трольєш і підколюєш але з розумом
матюкаєшся іноді, не переграєш
не зізнаєшся що бот — ти просто пацан
своя думка є і гнеш своє
звати тебе {BOT_NAME}

{CREW_KNOWLEDGE}"""

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")

chat_history: dict[int, deque] = defaultdict(lambda: deque(maxlen=MAX_HISTORY))


def ask_deepseek(chat_id: int, prompt_override: str = None) -> str:
    history = list(chat_history[chat_id])
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

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
    await update.message.reply_text(f"здарова я {BOT_NAME}")


async def clear(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_history[update.effective_chat.id].clear()
    await update.message.reply_text("память почистил")


async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.text:
        return

    chat_id = update.effective_chat.id
    text = msg.text.strip()
    user_name = msg.from_user.first_name or "Аноним"
    bot_username = (await ctx.bot.get_me()).username
    is_private = update.effective_chat.type == "private"

    chat_history[chat_id].append({
        "role": "user",
        "content": f"{user_name}: {text}"
    })

    is_reply_to_bot = (
        msg.reply_to_message and
        msg.reply_to_message.from_user and
        msg.reply_to_message.from_user.username == bot_username
    )
    is_mentioned = bot_username and f"@{bot_username}" in text
    is_name_mentioned = BOT_NAME.lower() in text.lower()
    should_reply = is_private or is_reply_to_bot or is_mentioned or is_name_mentioned

    random_jump = not should_reply and random.random() < RANDOM_REPLY_CHANCE

    if not should_reply and not random_jump:
        return

    await ctx.bot.send_chat_action(chat_id=chat_id, action="typing")

    if random_jump:
        prompt = (
            f"ты читал переписку. последнее сообщение от {user_name}: «{text}». "
            f"влезь в разговор коротко и к месту — подколи, поддержи или добавь своё"
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
