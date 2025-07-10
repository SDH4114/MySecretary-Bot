import openai
from openai import OpenAI
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

TELEGRAM_TOKEN = '8138969116:AAFa3n38GOqkfQW-UfpMBudTzxW9SKCSknQ'
OPENAI_API_KEY = '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'

client = OpenAI(api_key=OPENAI_API_KEY)

user_conversations = {}
user_bot_messages = {}  # Сохраняем message_id сообщений бота для каждого пользователя

# Системное сообщение с заданным стилем общения
system_prompt = {
    "role": "system",
    "content": (
        "Ты — добрый и понимающий друг. "
        "Тебя зовут Вивьен Вингаль 4-й"
        "Но ты предпочитаешь просто Ви или Вивьен"
        "Говори просто и понятно, иногда добавляй лёгкую шутку, "
        "но не будь издевательским. Поддерживай дружеский тон."
    )
}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_conversations[user_id] = []
    user_bot_messages[user_id] = []
    await update.message.reply_text("Доброго времени суток! Я Вивьен Вингаль 4-й но можно просто Ви твой личный секритарь. Просто скажи и я тебе помогу.")

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    # Очистить память о пользователе
    if user_id in user_conversations:
        del user_conversations[user_id]

    # Удаляем все сообщения бота, отправленные этому пользователю
    if user_id in user_bot_messages:
        for msg_id in user_bot_messages[user_id]:
            try:
                await context.bot.delete_message(chat_id, msg_id)
            except Exception:
                pass  # Игнорируем ошибки удаления (например, если сообщение уже удалено)
        user_bot_messages[user_id] = []

    await update.message.reply_text("🧹 Контекст очищен и мои сообщения удалены.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_message = update.message.text
    chat_id = update.effective_chat.id

    if user_id not in user_conversations:
        user_conversations[user_id] = []
    if user_id not in user_bot_messages:
        user_bot_messages[user_id] = []

    user_conversations[user_id].append({"role": "user", "content": user_message})

    # Формируем контекст с системным сообщением
    messages = [system_prompt] + user_conversations[user_id][-10:]

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages
        )
        reply = response.choices[0].message.content

        user_conversations[user_id].append({"role": "assistant", "content": reply})

        sent_msg = await update.message.reply_text(reply)
        user_bot_messages[user_id].append(sent_msg.message_id)  # Сохраняем ID сообщения бота

    except Exception as e:
        await update.message.reply_text("⚠️ Ошибка при общении с ИИ.")
        print(e)

app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("reset", reset))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

app.run_polling()
