from aiogram import Bot, Dispatcher, types, executor
from config import TOKEN, ADMINS
from services import RentService
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from db import get_db
from aiogram.dispatcher.handler import CancelHandler
from aiogram.dispatcher.middlewares import BaseMiddleware
from aiogram.dispatcher import DEFAULT_RATE_LIMIT
from functools import lru_cache
import asyncio
import datetime

bot = Bot(token=TOKEN)
dp = Dispatcher(bot)
service = RentService()

BTN_CANCEL = '↩️ Скасувати оренду'
BTN_BACK = '🔙 Назад'
BTN_AVAILABLE = '🚲 Доступний транспорт'
BTN_MY_RENTALS = '📋 Мої оренди'
BTN_BIKES = '🚲 Електровелосипеди'
BTN_SCOOTERS = '🛴 Електросамокати'
BTN_DAY = "1 день - 300 грн"
BTN_WEEK = "1 тиждень - 1500 грн"

PRICES = {
    'day': {'price': 300, 'text': '1 день'},
    'week': {'price': 1500, 'text': '1 тиждень'}
}

async def on_startup(dp):
    await get_db()
    await bot.delete_webhook(drop_pending_updates=True)
    await asyncio.sleep(1)
    print('База даних готова')

user_return_mode = {}
user_data = {}
last_msg = {}

def make_main_kb() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton(BTN_AVAILABLE), KeyboardButton(BTN_MY_RENTALS))
    kb.add(KeyboardButton(BTN_CANCEL))
    return kb

def make_transport_kb() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton(BTN_BIKES), KeyboardButton(BTN_SCOOTERS))
    kb.add(KeyboardButton(BTN_BACK))
    return kb

def make_rental_period_reply_kb() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    kb.row(KeyboardButton(BTN_DAY), KeyboardButton(BTN_WEEK))
    kb.add(KeyboardButton(BTN_BACK))
    return kb

def make_start_date_kb() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    today = datetime.date.today()
    kb.add(*[KeyboardButton((today + datetime.timedelta(days=i)).strftime('%d.%m.%Y')) for i in range(7)])
    kb.add(KeyboardButton(BTN_BACK))
    return kb

async def send_menu(chat_id: int, text: str, kb: ReplyKeyboardMarkup):
    if chat_id in last_msg:
        try:
            await bot.edit_message_text(text, chat_id, last_msg[chat_id], reply_markup=kb)
            return
        except Exception:
            pass
    msg = await bot.send_message(chat_id, text, reply_markup=kb)
    last_msg[chat_id] = msg.message_id

@dp.message_handler(commands='start')
async def cmd_start(m: types.Message):
    await send_menu(m.chat.id, 'Вітаємо! Оберіть дію:', make_main_kb())

@dp.message_handler(lambda m: m.text == BTN_AVAILABLE)
async def show_types(m: types.Message):
    await send_menu(m.chat.id, 'Оберіть тип транспорту:', make_transport_kb())

@dp.message_handler(lambda m: m.text == BTN_BIKES)
async def bikes(m: types.Message):
    text = await build_vehicle_list('electric_bike')
    await send_menu(m.chat.id, text, make_transport_kb())

@dp.message_handler(lambda m: m.text == BTN_SCOOTERS)
async def scooters(m: types.Message):
    text = await build_vehicle_list('electric_scooter')
    await send_menu(m.chat.id, text, make_transport_kb())

@dp.message_handler(lambda m: m.text == BTN_BACK)
async def back(m: types.Message):
    await send_menu(m.chat.id, 'Оберіть дію:', make_main_kb())

@dp.message_handler(lambda m: m.text == BTN_CANCEL)
async def want_cancel(m: types.Message):
    orders = await service.get_user_orders(m.from_user.id)
    if not orders:
        await m.answer("У вас немає активних оренд.")
        return
    text = "Введіть ID транспорту для скасування оренди:\n"
    for o in orders:
        period = PRICES[o[4]]['text']
        price = f"{PRICES[o[4]]['price']} грн"
        start = o[5] if o[5] else "-"
        code = o[6] if len(o) > 6 else "-"
        text += f"{o[1]}. {o[2]} — {period}, {price}, початок: {start}, код: {code}\n"
    await m.answer(text)
    user_return_mode[m.from_user.id] = True

@dp.message_handler(lambda message: message.text.isdigit() and user_return_mode.get(message.from_user.id))
async def process_return_request(message: types.Message):
    vehicle_id = int(message.text)
    ok, resp = await service.return_vehicle(message.from_user.id, vehicle_id)
    await send_menu(message.chat.id, resp, make_main_kb())
    user_return_mode.pop(message.from_user.id, None)

@dp.message_handler(lambda message: message.text == BTN_MY_RENTALS)
async def myorders(message: types.Message):
    orders = await service.get_user_orders(message.from_user.id)
    if not orders:
        await message.answer("У вас немає активних оренд.")
        return
    text = "Ваші активні оренди:\n\n"
    for o in orders:
        period = PRICES[o[4]]['text']
        price = f"{PRICES[o[4]]['price']} грн"
        start = o[5] if o[5] else "-"
        code = o[6] if len(o) > 6 else "-"
        text += f"ID: {o[1]}\nМодель: {o[2]}\nТермін: {period}\nЦіна: {price}\nПочаток: {start}\nКод оренди: {code}\n\n"
    await message.answer(text)

@dp.message_handler(lambda m: m.text.startswith("/cancel"))
async def admin_cancel_cmd(message: types.Message):
    if message.from_user.id not in ADMINS:
        await message.answer("Немає прав.")
        return
    try:
        vid = int(message.text.split()[1])
    except (IndexError, ValueError):
        await message.answer("Формат: /cancel <id>")
        return
    ok, resp = await service.admin_cancel(vid)
    await message.answer(resp)

@dp.message_handler(commands=['refresh'])
async def refresh_menu(message: types.Message):
    await send_menu(message.chat.id, 'Меню оновлено', make_main_kb())

@lru_cache(maxsize=1)
async def cached_available():
    return await service.get_available_vehicles_by_type('electric_bike')

@dp.message_handler(lambda m: m.text.isdigit() and not user_return_mode.get(m.from_user.id))
async def process_rent_request(message: types.Message):
    vehicle_id = int(message.text)
    vehicles = await service.get_available_vehicles_by_type('electric_bike') + await service.get_available_vehicles_by_type('electric_scooter')
    if not any(v[0] == vehicle_id for v in vehicles):
        await message.answer("Цей транспорт недоступний. Оберіть інший ID.")
        return
    user_data[message.from_user.id] = {'vehicle_id': vehicle_id}
    await message.answer("Оберіть термін оренди:", reply_markup=make_rental_period_reply_kb())

@dp.message_handler(lambda m: m.text in [BTN_DAY, BTN_WEEK] and user_data.get(m.from_user.id))
async def process_rental_period_reply(message: types.Message):
    user_id = message.from_user.id
    rental_period = 'day' if message.text == BTN_DAY else 'week'
    user_data[user_id]['rental_period'] = rental_period
    await message.answer("Оберіть дату початку оренди:", reply_markup=make_start_date_kb())

@dp.message_handler(lambda m: is_valid_date(m.text) and user_data.get(m.from_user.id) and 'rental_period' in user_data.get(m.from_user.id, {}))
async def process_start_date(message: types.Message):
    user_id = message.from_user.id
    start_date = message.text
    vehicle_id = user_data[user_id]['vehicle_id']
    rental_period = user_data[user_id]['rental_period']
    ok, order_code = await service.create_order(user_id, vehicle_id, message.from_user.username, rental_period, start_date)
    if ok:
        period_ua = PRICES[rental_period]['text']
        price = f"{PRICES[rental_period]['price']} грн"
        await message.answer(f"Оренду успішно оформлено!\nТермін: {period_ua}\nЦіна: {price}\nПочаток: {start_date}\nВаш код оренди: <code>{order_code}</code>", parse_mode='HTML', reply_markup=make_main_kb())
    else:
        await message.answer("Помилка при оформленні оренди. Спробуйте пізніше.", reply_markup=make_main_kb())
    del user_data[user_id]

def is_valid_date(text):
    try:
        datetime.datetime.strptime(text, '%d.%m.%Y')
        return True
    except Exception:
        return False

async def build_vehicle_list(v_type: str) -> str:
    vehicles = await service.get_available_vehicles_by_type(v_type)
    if not vehicles:
        return "Немає доступних моделей."
    name = "електровелосипеди" if v_type == 'electric_bike' else 'електросамокати'
    text = f"Доступні {name}:\n\n"
    for v in vehicles:
        text += (f"ID: {v[0]}\nМодель: {v[1]}\nПотужність: {v[2]} Вт\n"
                 f"Запас ходу: {v[3]} км\nЗалишилось: {v[5]} шт.\n\n")
    text += "\nДля оренди введіть ID бажаної моделі"
    return text

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)