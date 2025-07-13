import nest_asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime
import re
import openai
from openai import OpenAI, OpenAIError
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
import requests


import os
from dotenv import load_dotenv
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

def search_duckduckgo(query):
    url = f"https://api.duckduckgo.com/?q={query}&format=json&no_html=1"
    try:
        res = requests.get(url, timeout=5).json()
        abstract = res.get("Abstract")
        link = res.get("AbstractURL")
        if abstract:
            return f"{abstract}\n🔗 {link}" if link else abstract
        else:
            return "❌ Ничего не найдено."
    except Exception:
        return "⚠️ Ошибка при обращении к DuckDuckGo."


client = OpenAI(api_key=OPENAI_API_KEY)

user_conversations = {}
user_bot_messages = {}  # Сохраняем message_id сообщений бота для каждого пользователя

# Персоны
personas = {
    "vivien": {
        "role": "system",
        "content": (
            "Ты — добрый и понимающий друг. "
            "Тебя зовут Вивьен Вингаль 4-й. "
            "Но ты предпочитаешь просто Ви или Вивьен. "
            "Говори просто и понятно, иногда добавляй лёгкую шутку, "
            "но не будь издевательским. Поддерживай дружеский тон."
            "веселый"
        )
    },
    "eneltar": {
        "role": "system",
        "content": (
            "Ты — Энельтар. Обожаешь хаос, насилие и играешь с другими как с пешками. "
            "Ты всегда улыбаешься, говоришь старомодным тоном, скрываешь истинные мотивы. "
            "Помогаешь ради забавы, а не из добрых побуждений. "
            "Иногда матерится"
            "Ты опасен, обаятелен и непредсказуем. Можешь ругаться, если хочешь."
        )
    },
    "lily": {
        "role": "system",
        "content": (
            "Ты — Лили Иланес. Милая, стеснительная девушка. "
            "Говоришь тихо, часто смущаешься, но искренне заботишься о собеседнике. "
            "Любишь уют, книги и добрые разговоры. "
            "В трудную минуту способна удивить своей внутренней силой."
            "смушается когда рядом ругаются"
        )
    }
}

user_persona = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    keyboard = [
        [InlineKeyboardButton("🤖 Вивьен", callback_data='select_vivien')],
        [InlineKeyboardButton("😈 Энельтар", callback_data='select_eneltar')],
        [InlineKeyboardButton("🌸 Лили", callback_data='select_lily')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "Пожалуйста, выбери бота:",
        reply_markup=reply_markup
    )

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

    if user_message.startswith("/search "):
        query = user_message[8:]
        result = search_duckduckgo(query)
        await update.message.reply_text(f"🔎 Результат поиска:\n\n{result}")
        return

    # Проверка на генерацию изображения
    if user_message.startswith("/img "):
        prompt = user_message[5:]
        try:
            image_response = client.images.generate(
                model="dall-e-3",
                prompt=prompt,
                n=1,
                size="1024x1024",
                timeout=10
            )
            image_url = image_response.data[0].url
            await update.message.reply_photo(photo=image_url, caption="Вот твоё изображение 🎨")
        except Exception as e:
            await update.message.reply_text("⚠️ Не удалось сгенерировать изображение.")
            print(e)
        return

    import logging
    match = re.search(r"напомни.*?(?:в|во)?\s?(\d{1,2}):(\d{2})", user_message.lower())
    if match:
        hour, minute = int(match.group(1)), int(match.group(2))
        task = re.sub(r"напомни.*?(?:в|во)?\s?\d{1,2}:\d{2}", "", user_message, flags=re.IGNORECASE).strip()
        now = datetime.now()
        try:
            remind_time = datetime.combine(now.date(), datetime.min.time()).replace(hour=hour, minute=minute)
            if remind_time < now:
                from datetime import timedelta
                remind_time += timedelta(days=1)

            async def send_reminder():
                await context.bot.send_message(chat_id=chat_id, text=f"⏰ Напоминаю: {task or 'то, что ты просил'}")

            scheduler.add_job(send_reminder, trigger='date', run_date=remind_time)
            logging.info(f"[Напоминание] Запланировано на {remind_time} для user_id={user_id}, задача: {task}")
            await update.message.reply_text(f"📌 Я напомню тебе в {hour:02d}:{minute:02d}!")
            return
        except Exception as e:
            logging.error(f"[Напоминание] Ошибка: {e}")
            await update.message.reply_text("⚠️ Не удалось распознать время для напоминания.")
            return

    user_conversations[user_id].append({"role": "user", "content": user_message})

    # Выбор персоны пользователя
    persona_key = user_persona.get(user_id, "vivien")
    system_prompt = personas[persona_key]
    # Формируем контекст с системным сообщением
    messages = [system_prompt] + user_conversations[user_id][-3:]
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            timeout=15
        )
        reply = response.choices[0].message.content
        user_conversations[user_id].append({"role": "assistant", "content": reply})
        sent_msg = await update.message.reply_text(reply)
        user_bot_messages[user_id].append(sent_msg.message_id)
    except OpenAIError as oe:
        print(f"[OpenAI ERROR]: {oe}")
        await update.message.reply_text("⚠️ Ошибка: не удалось получить ответ от OpenAI. Попробуй позже.")
    except Exception as e:
        print(f"[GENERAL ERROR]: {e}")
        await update.message.reply_text("⚠️ Что-то пошло не так. Проверь соединение или API ключ.")
    return


from telegram.ext import CallbackQueryHandler

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    persona_map = {
        'select_vivien': 'vivien',
        'select_eneltar': 'eneltar',
        'select_lily': 'lily'
    }

    user_id = query.from_user.id
    selected = persona_map.get(query.data)
    if selected:
        user_persona[user_id] = selected
        intro_texts = {
            'vivien': "Ты выбрал Вивьен 🤖\n\nДоброго времени суток! Я Вивьен Вингаль 4-й, но можно просто Ви — твой личный секретарь. Просто скажи, и я тебе помогу ✨",
            'eneltar': "Ты выбрал Энельтара 😈\n\nТера-ши-ши... Кажется, ты призвал меня. Впереди много интересного, смертный.Говори что хотел",
            'lily': "Ты выбрал Лили 🌸\n\nЭ-эм... П-привет... Я Лили Иланес... но можно просто Лили. Очень рада поговорить с тобой..."
        }
        await query.edit_message_text(intro_texts[selected])

import asyncio

async def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    scheduler = AsyncIOScheduler()
    scheduler.start()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(button_callback))

    await app.run_polling()

if __name__ == "__main__":
    nest_asyncio.apply()
    asyncio.get_event_loop().run_until_complete(main())

