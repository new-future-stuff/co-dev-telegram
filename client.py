from re import I
from typing import List
from aiogram import Bot, Dispatcher, executor
import json
import asyncio
from aiogram.types import (
    CallbackQuery, ChatType, InlineKeyboardMarkup, KeyboardButton, Message, InlineKeyboardButton, ReplyKeyboardMarkup
)
from sqlmodel import select
from config import Config
from sqlalchemy.ext.asyncio import AsyncSession
from models import Project, User, engine


config = Config(**json.load(open("config.json")))


bot = Bot(token=config.telegram_bot_token)
dp = Dispatcher(bot)


def make_an_inline_keyboard(rows):
    keyboard = InlineKeyboardMarkup()
    for row in rows:
        keyboard.add(
            *(
                InlineKeyboardButton(text, callback_data=data)
                for text, data in row
            )
        )
    return keyboard


waiting_for_messages = {}


async def wait_for_message(user_id) -> Message:
    waiting_for_messages[user_id] = None
    while waiting_for_messages[user_id] is None:
        await asyncio.sleep(0)
    return waiting_for_messages.pop(user_id)


async def send_menu(user_id: int):
    kb = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
    kb.add(KeyboardButton("Создать проект"))
    kb.add(KeyboardButton("Посмотреть список проектов"))
    kb.add(KeyboardButton("Лайки, которые я оставил"))
    kb.add(KeyboardButton("Лайки, которые поставили мне"))
    await bot.send_message(
        chat_id=user_id,
        text="Здравствуйте и бла-бла-бла. Тыкойте.",
        reply_markup=kb,
    )


@dp.callback_query_handler()
async def handle_button_callback(callback: CallbackQuery):
    await callback.answer()
    if callback.data.startswith("show"):
        try:
            project_id = int(callback.data[4:])
        except ValueError:
            pass
        else:
            await bot.edit_message_text(
                chat_id=callback.message.chat.id,
                message_id=callback.message.message_id,
                **await make_params_for_project_message(project_id),
            )


async def make_params_for_project_message(project_id: int):
    async with AsyncSession(engine) as session:
        projects: List[Project] = (
            await session.execute(select(Project).filter(Project.id.in_([project_id - 1, project_id, project_id + 1])))
        ).scalars().all()
    prev = None
    current = None
    next_ = None
    buttons = []
    for project in projects:
        if project.id == project_id - 1:
            prev = (("<", f"show{project.id}"))
        if project.id == project_id + 1:
            next_ = ((">", f"show{project.id}"))
        if project.id == project_id:
            current = project
    if current is None:
        return {
            "text": "Пока что проектов нет!",
            "reply_markup": make_an_inline_keyboard([[("Обновить", f"show{project_id}")]])
        }
    if prev is not None:
        buttons.append(prev)
    buttons.append(("Мне нравится", f"like{project_id}"))
    if next_ is not None:
        buttons.append(next_)
    return {
        "reply_markup": make_an_inline_keyboard([buttons]),
        "text": f"<b>{current.name}</b>\n{current.description}",
        "parse_mode": "HTML",
    }


@dp.message_handler()
async def handle_message(message: Message):
    if message.from_id in waiting_for_messages:
        waiting_for_messages[message.from_id] = message
        return
    if message.chat.type != ChatType.PRIVATE:
        await message.reply("Этот бот работает только в личных сообщениях!")
    async with AsyncSession(engine) as session:
        if (await session.execute(select(User).filter(User.telegram_id == message.from_id))).one_or_none() is None:
            session.add(User(telegram_id=message.from_id))
            await session.commit()
    if message.text == "/start":
        await send_menu(message.from_id)
    elif message.text == "Создать проект":
        await message.reply("Отправьте название проекта.")
        project_name_message = await wait_for_message(message.from_id)
        await project_name_message.reply("Отлично! Теперь отправьте описание проекта.")
        project_description_message = await wait_for_message(message.from_id)
        async with AsyncSession(engine) as session:
            session.add(Project(
                name=project_name_message.text,
                description=project_description_message.text,
                creator_id=message.from_id,
            ))
            await session.commit()
        await project_description_message.reply("Чудно! Проект создан.")
        await send_menu(message.from_id)
    elif message.text == "Посмотреть список проектов":
        await message.reply(**await make_params_for_project_message(project_id=1))


executor.start_polling(dp)
