import asyncio
import os
from datetime import date, datetime, timedelta

from db import init_db, add_booking, get_busy_hours

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove

load_dotenv()
bot = Bot(token=os.getenv("BOT_TOKEN"))
dp = Dispatcher()
ADMIN_ID = int(os.getenv("ADMIN_ID"))

class Booking(StatesGroup):
    waiting_phone = State()

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

def phone_keyboard():
    button = KeyboardButton(text="📱 Отправить номер", request_contact=True)
    return ReplyKeyboardMarkup(keyboard=[[button]], resize_keyboard=True, one_time_keyboard=True)


@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
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
async def choose_time(callback: CallbackQuery, state: FSMContext):
    _, key, day, hour = callback.data.split(":")
    hour = int(hour)
    name, price = SERVICES[key]
    nice_day = date.fromisoformat(day).strftime("%d.%m")

    if hour in get_busy_hours(day):
        await callback.answer("Это время только что заняли, выбери другое", show_alert=True)
        await callback.message.edit_reply_markup(reply_markup=times_keyboard(key, day))
        return

    await state.update_data(key=key, day=day, hour=hour)
    await state.set_state(Booking.waiting_phone)
    await callback.message.edit_text(f"{name} — {price} ₸\n📅 {nice_day} в {hour}:00")
    await callback.message.answer(
        "Остался последний шаг: нажми кнопку ниже, чтобы отправить номер 👇",
        reply_markup=phone_keyboard(),
    )
    await callback.answer()

@dp.message(Booking.waiting_phone, F.contact)
async def get_phone(message: Message, state: FSMContext):
    data = await state.get_data()
    key, day, hour = data["key"], data["day"], data["hour"]
    name, price = SERVICES[key]
    nice_day = date.fromisoformat(day).strftime("%d.%m")
    phone = message.contact.phone_number
    client = message.from_user.full_name

    if hour in get_busy_hours(day):
        await state.clear()
        await message.answer(
            "Пока ты отправлял номер, это время заняли 😔\nНажми /start и выбери другое.",
            reply_markup=ReplyKeyboardRemove(),
        )
        return

    add_booking(message.from_user.id, client, phone, name, day, hour)
    await state.clear()

    await message.answer(
        f"✅ Готово, ты записан!\n\n{name} — {price} ₸\n📅 {nice_day} в {hour}:00\n\nДо встречи ✂️",
        reply_markup=ReplyKeyboardRemove(),
    )
    await bot.send_message(
        ADMIN_ID,
        f"🔔 Новая запись!\n\n👤 {client}\n📱 {phone}\n✂️ {name} — {price} ₸\n📅 {nice_day} в {hour}:00",
    )


@dp.message(Booking.waiting_phone)
async def phone_not_sent(message: Message):
    await message.answer("Нажми кнопку «📱 Отправить номер» внизу 👇")


@dp.message()
async def echo(message: Message):
    await message.answer(f"Ты написал: {message.text}")

async def main():
    init_db()
    print("Бот запущен")
    await dp.start_polling(bot)


asyncio.run(main())
