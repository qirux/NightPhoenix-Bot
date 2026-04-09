import os
import json
import asyncio
import random
from typing import Dict, List, Any

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton

from groq import Groq

# --- КОНФИГУРАЦИЯ ---
API_TOKEN = ''
GROQ_API_KEY = ''  # Получите на console.groq.com
ALLOWED_GROUP_ID = -1003604090033  # ЗАМЕНИТЕ НА ID ВАШЕЙ ГРУППЫ (отрицательное число)
ADMIN_IDS = [8250229875, 6125318955, 6143212313, 5268779581, 1110640838]

DATA_FILE = 'clan_data.json'

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {
        "rp_commands": {
            "обнять": "обнял(а)",
            "поцеловать": "поцеловал(а)",
            "ударить": "ударил(а)"
        },
        "user_emojis": {},
        "chat_history": {},  # Ключ - group_id (строка), значение - список сообщений
        "members": []
    }

def save_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

db = load_data()

# --- ИНИЦИАЛИЗАЦИЯ GROQ ---
client = Groq(api_key=GROQ_API_KEY)
MODEL_NAME = "llama-3.3-70b-versatile"

# --- БОТ ---
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
AI_MARKER = "\u200B[AI]"

def get_html_mention(user_id, name, username=None):
    url = f"https://t.me/{username}" if username else f"tg://user?id={user_id}"
    return f'<a href="{url}">{name}</a>'

def is_allowed_chat(chat_id: int) -> bool:
    return chat_id == ALLOWED_GROUP_ID

def is_ai_message(message: types.Message) -> bool:
    """Проверяет, было ли сообщение сгенерировано ИИ (по маркеру)"""
    return message.from_user.id == bot.id and message.text and AI_MARKER in message.text

# --- МЕНЮ (без изменений) ---
def get_main_menu(user_id):
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🎭 РП", callback_data=f"info:rp:{user_id}"))
    builder.row(InlineKeyboardButton(text="🧠 ИИ", callback_data=f"info:ai:{user_id}"))
    builder.row(InlineKeyboardButton(text="📢 Зазывала", callback_data=f"info:call:{user_id}"))
    builder.row(InlineKeyboardButton(text="❌ Закрыть", callback_data=f"menu:close:{user_id}"))
    return builder.as_markup()

@dp.message(Command("info_bot"))
async def cmd_info(message: types.Message):
    if not is_allowed_chat(message.chat.id):
        return
    await message.answer(
        "🛠 <b>Информационное меню бота</b>\nВыберите модуль для подробностей:",
        reply_markup=get_main_menu(message.from_user.id),
        parse_mode="HTML"
    )

@dp.callback_query(F.data.startswith("info:"))
async def handle_info_pages(callback: types.CallbackQuery):
    if not is_allowed_chat(callback.message.chat.id):
        await callback.answer("Бот работает только в разрешённой группе")
        return
    _, module, owner_id = callback.data.split(":")
    if callback.from_user.id != int(owner_id):
        return await callback.answer("Это меню не для вас!", show_alert=True)

    builder = InlineKeyboardBuilder()
    text = ""

    if module == "rp":
        cmds_list = ", ".join(db["rp_commands"].keys())
        text = (
            "🎭 <b>Модуль РП</b>\n\n"
            "Команды для взаимодействия\n"
            "<b>Как использовать:</b> <code>[команда] @юзер [текст](необязательно)</code>\n"
            f"<b>Список:</b> {cmds_list}\n\n"
            "<b>Доступ:</b> Всем участникам"
        )
        if callback.from_user.id in ADMIN_IDS:
            text += "\n\n<i>Вы админ: вы можете управлять списком команд в коде или через JSON</i>"

    elif module == "ai":
        text = (
            "🧠 <b>Модуль ИИ (Groq)</b>\n\n"
            "<b>Как использовать:</b>\n"
            "• Напишите 'ИИ [текст]'\n"
            "• Ответьте на предыдущий ответ ИИ\n"
            "<b>Сброс:</b> Кнопка ниже очищает общую историю чата"
        )
        builder.row(InlineKeyboardButton(text="♻️ Сбросить историю", callback_data=f"ai:reset:{owner_id}"))

    elif module == "call":
        text = (
            "📢 <b>Модуль Зазывала</b>\n\n"
            "<b>Как использовать:</b> Команда 'Калл [текст]'\n"
            "Бот тегает всех участников\n"
            "<b>Смайлы:</b> У каждого свой уникальный смайл"
        )
        builder.row(InlineKeyboardButton(text="🎲 Сменить мой смайл", callback_data=f"user:emoji:{owner_id}"))
        if callback.from_user.id in ADMIN_IDS:
            builder.row(InlineKeyboardButton(text="📋 Список смайлов", callback_data=f"admin:call_list:{owner_id}"))

    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"menu:main:{owner_id}"))
    builder.add(InlineKeyboardButton(text="❌ Закрыть", callback_data=f"menu:close:{owner_id}"))
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")

@dp.callback_query(F.data.startswith("menu:"))
async def handle_menu_nav(callback: types.CallbackQuery):
    if not is_allowed_chat(callback.message.chat.id):
        await callback.answer("Бот работает только в разрешённой группе")
        return
    _, action, owner_id = callback.data.split(":")
    if callback.from_user.id != int(owner_id): return

    if action == "main":
        await callback.message.edit_text("🛠 <b>Меню бота</b>",
                                         reply_markup=get_main_menu(owner_id), parse_mode="HTML")
    elif action == "close":
        await callback.message.delete()

# --- ЛОГИКА ИИ (единый диалог группы) ---
@dp.message(lambda m: m.text and is_allowed_chat(m.chat.id) and (
    m.text.lower().startswith("ии") or
    (m.reply_to_message and is_ai_message(m.reply_to_message))
))
async def ai_handler(message: types.Message):
    group_id = str(message.chat.id)

    # Извлекаем промпт
    prompt = message.text
    if prompt.lower().startswith("ии"):
        prompt = prompt[2:].strip()
    elif message.reply_to_message and is_ai_message(message.reply_to_message):
        prompt = message.text.strip()

    if not prompt:
        return

    # Инициализация общей истории для группы
    if group_id not in db["chat_history"]:
        db["chat_history"][group_id] = []

    # Формируем сообщения для Groq (система + общая история)
    messages = [{"role": "system", "content": "Ты полезный и дружелюбный ИИ-помощник. Ты общаешься с группой людей, они задают вопросы от лица всей группы. Отвечай естественно, как собеседник."}]
    for entry in db["chat_history"][group_id]:
        messages.append({"role": entry["role"], "content": entry["content"]})
    messages.append({"role": "user", "content": prompt})

    try:
        response = await asyncio.to_thread(
            client.chat.completions.create,
            model=MODEL_NAME,
            messages=messages,
            temperature=0.7,
            max_tokens=1000
        )
        reply_text = response.choices[0].message.content
        reply_text_with_marker = reply_text + AI_MARKER

        # Сохраняем в общую историю (последние 20 сообщений)
        db["chat_history"][group_id].append({"role": "user", "content": prompt})
        db["chat_history"][group_id].append({"role": "assistant", "content": reply_text})
        db["chat_history"][group_id] = db["chat_history"][group_id][-20:]
        save_data(db)

        # Отправляем ответ в чат (без упоминания конкретного пользователя, но можно добавить, например, "Пользователь X спросил:")
        await message.reply(reply_text_with_marker, parse_mode="HTML")
    except Exception as e:
        await message.reply(f"❌ Ошибка ИИ: {str(e)}")

@dp.callback_query(F.data.startswith("ai:reset:"))
async def ai_reset(callback: types.CallbackQuery):
    if not is_allowed_chat(callback.message.chat.id):
        await callback.answer("Бот работает только в разрешённой группе")
        return
    owner_id = callback.data.split(":")[2]
    if callback.from_user.id != int(owner_id): return
    group_id = str(callback.message.chat.id)
    db["chat_history"][group_id] = []
    save_data(db)
    await callback.answer("🧹 Общая история диалога группы сброшена", show_alert=True)

# --- ОСТАЛЬНЫЕ МОДУЛИ (РП, ЗАЗЫВАЛА, СМАЙЛЫ) с проверкой группы ---
@dp.message()
async def main_text_handler(message: types.Message):
    if not is_allowed_chat(message.chat.id):
        return
    if not message.text:
        return
    uid = message.from_user.id

    # Регистрация участника
    if uid not in db["members"]:
        db["members"].append(uid)
        if str(uid) not in db["user_emojis"]:
            db["user_emojis"][str(uid)] = random.choice(["🗡", "🛡", "🍗", "🍺", "💎", "🔮", "🧿", "🌀", "🔥"])
        save_data(db)

    text = message.text.strip()
    parts = text.split()
    cmd = parts[0].lower()

    # ЗАЗЫВАЛА
    if cmd == "калл" and uid in ADMIN_IDS:
        reason = " ".join(parts[1:])
        random.shuffle(db["members"])
        for i in range(0, len(db["members"]), 5):
            chunk = db["members"][i:i+5]
            mentions = [f'<a href="tg://user?id={m_id}">{db["user_emojis"].get(str(m_id), "👤")}</a>' for m_id in chunk]
            out = "".join(mentions)
            if reason:
                out += f"\n\n{reason}"
            await message.answer(out, parse_mode="HTML")
        return

    # РП МОДУЛЬ
    if cmd in db["rp_commands"]:
        action = db["rp_commands"][cmd]
        target = None
        comment = ""

        if message.reply_to_message:
            target = message.reply_to_message.from_user
            comment = " ".join(parts[1:])
        elif len(parts) > 1 and parts[1].startswith("@"):
            username = parts[1][1:]
            target_mention = f'<a href="https://t.me/{username}">@{username}</a>'
            comment = " ".join(parts[2:])
        else:
            return

        user_mention = get_html_mention(uid, message.from_user.full_name, message.from_user.username)
        if target:
            target_mention = get_html_mention(target.id, target.full_name, target.username)

        final_msg = f"[🐶] {user_mention} {action} {target_mention}"
        if comment.strip():
            final_msg += f" с сообщением: <i>{comment.strip()}</i>"

        await message.answer(final_msg, parse_mode="HTML")

@dp.callback_query(F.data.startswith("user:emoji:"))
async def change_emoji(callback: types.CallbackQuery):
    if not is_allowed_chat(callback.message.chat.id):
        await callback.answer("Бот работает только в разрешённой группе")
        return
    if callback.from_user.id != int(callback.data.split(":")[2]): return
    new_emo = random.choice(["🦁", "🐯", "🐝", "🦉", "🦒", "🦖", "🐙", "🦄", "🍀"])
    db["user_emojis"][str(callback.from_user.id)] = new_emo
    save_data(db)
    await callback.answer(f"Твой новый символ: {new_emo}", show_alert=True)

@dp.callback_query(F.data.startswith("admin:call_list:"))
async def admin_list(callback: types.CallbackQuery):
    if not is_allowed_chat(callback.message.chat.id):
        await callback.answer("Бот работает только в разрешённой группе")
        return
    if callback.from_user.id not in ADMIN_IDS: return
    lines = []
    for uid, emo in db["user_emojis"].items():
        lines.append(f"ID: <code>{uid}</code> — {emo}")
    text = "📋 <b>Список участников и их смайлов:</b>\n\n" + "\n".join(lines[:20])
    await callback.message.edit_text(text, reply_markup=callback.message.reply_markup, parse_mode="HTML")

async def main():
    print(f"Бот запущен. Разрешённая группа: {ALLOWED_GROUP_ID}")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
