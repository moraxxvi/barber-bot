import asyncio
import os
from datetime import date, datetime, timedelta

from db import init_db, add_booking, get_busy_hours

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv

load_dotenv()
bot = Bot(token=os.getenv("BOT_TOKEN"))
dp = Dispatcher()
SERVICES = {
    "haircut": ("Мужская стрижка", 5000),
    "beard": ("Оформление бороды", 3000),
    "combo": ("Стрижка + борода", 7000),
    "junior": ("Детская стрижка", 4000),
}


def services_keyboard():
    buttons = []
    for key, (name, price) in SERVICES.items():
        button = InlineKeyboardButton(text=f"{name} — {price} ₸", callback_data=f"service:{key}")
        buttons.append([button])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

WEEKDAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


def days_keyboard(service_key):
    buttons = []
    today = date.today()
    for i in range(7):
        day = today + timedelta(days=i)
        text = f"{WEEKDAYS[day.weekday()]} {day.strftime('%d.%m')}"
        button = InlineKeyboardButton(text=text, callback_data=f"day:{service_key}:{day.isoformat()}")
        buttons.append([button])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def free_hours(day):
    busy = get_busy_hours(day)
    now = datetime.now()
    result = []
    for hour in range(10, 21):
        if hour in busy:
            continue
        if day == date.today().isoformat() and hour <= now.hour:
            continue
        result.append(hour)
    return result


def times_keyboard(service_key, day):
    buttons = []
    row = []
    for hour in free_hours(day):
        row.append(InlineKeyboardButton(text=f"{hour}:00", callback_data=f"time:{service_key}:{day}:{hour}"))
        if len(row) == 4:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@dp.message(CommandStart())
async def start(message: Message):
       await message.answer(
        f"Привет, {message.from_user.first_name}! Я бот барбершопа ✂️\nВыбери услугу:",
        reply_markup=services_keyboard(),
    )

@dp.callback_query(F.data.startswith("service:"))
async def choose_service(callback: CallbackQuery):
    key = callback.data.split(":")[1]
    name, price = SERVICES[key]
    await callback.message.edit_text(
        f"{name} — {price} ₸\n\nВыбери день:",
        reply_markup=days_keyboard(key),
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("day:"))
async def choose_day(callback: CallbackQuery):
    _, key, day = callback.data.split(":")
    name, price = SERVICES[key]
    nice_day = date.fromisoformat(day).strftime("%d.%m")

    if not free_hours(day):
        await callback.message.edit_text(
            f"На {nice_day} всё занято 😔\nВыбери другой день:",
            reply_markup=days_keyboard(key),
        )
        await callback.answer()
        return

    await callback.message.edit_text(
        f"{name} — {price} ₸\n📅 {nice_day}\n\nВыбери время:",
        reply_markup=times_keyboard(key, day),
    )
    await callback.answer()

    


@dp.callback_query(F.data.startswith("time:"))
async def choose_time(callback: CallbackQuery):
    _, key, day, hour = callback.data.split(":")
    hour = int(hour)
    name, price = SERVICES[key]
    nice_day = date.fromisoformat(day).strftime("%d.%m")

    if hour in get_busy_hours(day):
        await callback.answer("Это время только что заняли, выбери другое", show_alert=True)
        await callback.message.edit_reply_markup(reply_markup=times_keyboard(key, day))
        return

    add_booking(callback.from_user.id, callback.from_user.full_name, name, day, hour)
    await callback.message.edit_text(
        f"✅ Готово, ты записан!\n\n{name} — {price} ₸\n📅 {nice_day} в {hour}:00\n\nДо встречи ✂️"
    )
    await callback.answer()


@dp.message()
async def echo(message: Message):
    await message.answer(f"Ты написал: {message.text}")

async def main():
    init_db()
    print("Бот запущен")
    await dp.start_polling(bot)


asyncio.run(main())
