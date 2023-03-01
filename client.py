from typing import List
from aiogram import Bot, Dispatcher, executor
import json
import asyncio
from aiogram.types import (
    CallbackQuery, ChatType, InlineKeyboardMarkup, KeyboardButton, Message, InlineKeyboardButton, ReplyKeyboardMarkup
)
from sqlalchemy.exc import IntegrityError
from sqlmodel import select, update
from config import Config
from sqlalchemy.ext.asyncio import AsyncSession
from models import Project, ProjectLike, User, UserLike, engine


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


async def wait_for_message(telegram_id) -> Message:
    waiting_for_messages[telegram_id] = None
    while waiting_for_messages[telegram_id] is None:
        await asyncio.sleep(0)
    return waiting_for_messages.pop(telegram_id)


async def send_menu(user_id: int):
    kb = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
    kb.add(KeyboardButton("Создать проект"))
    kb.add(KeyboardButton("Посмотреть список проектов"))
    kb.add(KeyboardButton("Посмотреть список пользователей"))
    kb.add(KeyboardButton("Изменить имя"))
    kb.add(KeyboardButton("Изменить описание"))
    kb.add(KeyboardButton("Посмотреть свой профиль"))
    await bot.send_message(
        chat_id=user_id,
        text="Здравствуйте и бла-бла-бла. Тыкойте.",
        reply_markup=kb,
    )


@dp.callback_query_handler()
async def handle_button_callback(callback: CallbackQuery):
    await callback.answer()
    user = await get_user(callback.message.from_id)
    if callback.data.startswith("show_project"):
        try:
            user_id = int(callback.data[len("show_project"):])
        except ValueError:
            pass
        else:
            await bot.edit_message_text(
                chat_id=callback.message.chat.id,
                message_id=callback.message.message_id,
                **await make_params_for_project_message(user_id),
            )
    elif callback.data.startswith("show_user"):
        try:
            user_id = int(callback.data[len("show_user"):])
        except ValueError:
            pass
        else:
            await bot.edit_message_text(
                chat_id=callback.message.chat.id,
                message_id=callback.message.message_id,
                **await make_params_for_user_message(user_id),
            )
    elif callback.data.startswith("like_project"):
        try:
            project_id = int(callback.data[len("like_project"):])
        except ValueError:
            pass
        else:
            user_like = UserLike(sender_id=user.id, receiver_id=project_id)
            async with AsyncSession(engine) as session:
                session.add(user_like)
                await session.commit()
    elif callback.data.startswith("like_user"):
        try:
            user_id = int(callback.data[len("like_project"):])
        except ValueError:
            pass
        else:
            user_like = ProjectLike(receiver_id=user_id, sender_id=user.id)
            async with AsyncSession(engine) as session:
                other_user = (await session.execute(select(User).filter(User.id == user_id))).scalars().one()
                session.add(user_like)
                try:
                    await session.commit()
                except IntegrityError:
                    await bot.send_message(chat_id=other_user.telegram_id, text="Ваш профиль понравился пользователю \"{user.name}\"!")


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
            prev = (("<", f"show_project{project.id}"))
        if project.id == project_id + 1:
            next_ = ((">", f"show_project{project.id}"))
        if project.id == project_id:
            current = project
    if current is None:
        return {
            "text": "Пока что проектов нет!",
            "reply_markup": make_an_inline_keyboard([[("Обновить", f"show_project{project_id}")]])
        }
    if prev is not None:
        buttons.append(prev)
    buttons.append(("Мне нравится", f"like_project{project_id}"))
    if next_ is not None:
        buttons.append(next_)
    return {
        "reply_markup": make_an_inline_keyboard([buttons]),
        "text": f"<b>{current.name}</b>\n{current.description}",
        "parse_mode": "HTML",
    }


async def make_params_for_user_message(user_id: int):
    async with AsyncSession(engine) as session:
        users: List[User] = (
            await session.execute(select(User).filter(User.id.in_([user_id - 1, user_id, user_id + 1])))
        ).scalars().all()
    prev = None
    current = None
    next_ = None
    buttons = []
    for user in users:
        if user.id == user_id - 1:
            prev = (("<", f"show_user{user.id}"))
        if user.id == user_id + 1:
            next_ = ((">", f"show_user{user.id}"))
        if user.id == user_id:
            current = user
    if current is None:
        return {
            "text": "Пока что пользователей нет!",
            "reply_markup": make_an_inline_keyboard([[("Обновить", f"show_user{user_id}")]])
        }
    if prev is not None:
        buttons.append(prev)
    buttons.append(("Мне нравится", f"like_user{user_id}"))
    if next_ is not None:
        buttons.append(next_)
    return {
        "reply_markup": make_an_inline_keyboard([buttons]),
        "text": f"<b>{current.name}</b>\n{current.description}",
        "parse_mode": "HTML",
    }


async def get_user(telegram_id: int):
    async with AsyncSession(engine) as session:
        user = (await session.execute(select(User).filter(User.telegram_id == telegram_id))).scalars().one_or_none()
        if user is None:
            await bot.send_message(chat_id=telegram_id, text="Введите ваше имя, которое будет отображаться в сервисе. Вы можете изменить это в будущем.")
            name_message = await wait_for_message(telegram_id)
            await bot.send_message(chat_id=telegram_id, text="Введите описание своего профиля (кто вы, какие навыки имеются). Вы можете изменить это в будущем.")
            desc_message = await wait_for_message(telegram_id)
            user = User(telegram_id=telegram_id, name=name_message.text, description=desc_message.text)
            session.add(user)
            await session.commit()
            await session.refresh(user)
        return user


@dp.message_handler()
async def handle_message(message: Message):
    if message.from_id in waiting_for_messages:
        waiting_for_messages[message.from_id] = message
        return
    if message.chat.type != ChatType.PRIVATE:
        await message.reply("Этот бот работает только в личных сообщениях!")
    user = await get_user(message.from_id)
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
    elif message.text == "Посмотреть список пользователей":
        await message.reply(**await make_params_for_user_message(user_id=1))
    elif message.text == "Изменить имя":
        await message.reply("Введите новое имя.")
        name_message = await wait_for_message(message.from_id)
        async with AsyncSession(engine) as session:
            await session.execute(update(User).where(User.id == user.id).values(name=name_message.text))
            await session.commit()
        await send_menu(message.from_id)
    elif message.text == "Изменить описание":
        await message.reply("Введите новое описание.")
        desc_message = await wait_for_message(message.from_id)
        async with AsyncSession(engine) as session:
            await session.execute(update(User).where(User.id == user.id).values(description=desc_message.text))
            await session.commit()
        await send_menu(message.from_id)
    elif message.text == "Посмотреть свой профиль":
        await message.reply(f"Ваш профиль:\n\nИмя: {user.name}\nОписание: {user.description}")
    else:
        await message.reply("Я вас не понимаю.")


executor.start_polling(dp)
