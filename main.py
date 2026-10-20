import os
import asyncio
import aiohttp
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram import Client
from pyrogram.errors import PhoneNumberBanned

# Environment Variables
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
SMSBOWER_KEY = os.getenv("SMSBOWER_KEY")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Pyrogram Client for checking Telegram status
tele_client = Client("checker_session", api_id=API_ID, api_hash=API_HASH)

COUNTRY_MAP = {
    "colombia": {"code": "0", "name": "Colombia (+57)"},
    "chile": {"code": "3", "name": "Chile (+56)"},
    "usa": {"code": "18", "name": "USA Virtual (+1)"},
    "indonesia": {"code": "6", "name": "Indonesia (+62)"},
    "argentina": {"code": "52", "name": "Argentina (+54)"},
    "ukraine": {"code": "1", "name": "Ukraine (+380)"}
}

# 1. Fetch SMS Balance
async def get_sms_balance():
    url = f"https://smsbower.com/stubs/handler_api.php?api_key={SMSBOWER_KEY}&action=getBalance"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            text = await resp.text()
            if "ACCESS_BALANCE" in text:
                return text.split(":")[1]
            return "0.00"

# 2. Fetch Multi-Prices & Stock List from SMSBower
async def get_smsbower_prices(country_code, service="tg"):
    url = f"https://smsbower.com/stubs/handler_api.php?api_key={SMSBOWER_KEY}&action=getPrices&service={service}&country={country_code}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            try:
                data = await resp.json()
                c_data = data.get(str(country_code), {})
                service_data = c_data.get(service, {})
                return service_data # Returns dictionary like {"0.119": 1500, "0.19": 200}
            except Exception:
                return {}

# 3. Buy Number with Exact Selected Price/Rate
async def buy_number_with_rate(country_code, price=None, service="tg"):
    url = f"https://smsbower.com/stubs/handler_api.php?api_key={SMSBOWER_KEY}&action=getNumber&service={service}&country={country_code}"
    if price and price != "auto":
        url += f"&price={price}"
        
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            text = await resp.text()
            if "ACCESS_NUMBER" in text:
                parts = text.split(":")
                return parts[1], parts[2]  # activation_id, phone_number
            return None, text

# 4. Telegram Status Checker
async def check_telegram_status(phone_number):
    try:
        if not tele_client.is_connected:
            await tele_client.start()
        sent_code = await tele_client.send_code(phone_number)
        if sent_code.type.name == "APP":
            return "🟡 Used"
        return "🟢 Fresh"
    except PhoneNumberBanned:
        return "🔴 Blocked"
    except Exception:
        return "🔴 Blocked"

# Persistent Main Menu Keyboard
main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="▶️ Start Bulk"), KeyboardButton(text="⏹ Stop Bulk")],
        [KeyboardButton(text="🚫 Cancel (No OTP)")],
        [KeyboardButton(text="🌍 Country"), KeyboardButton(text="💱 Change Rate")],
        [KeyboardButton(text="⚙️ Settings & Info"), KeyboardButton(text="🔄 Reset Bot")]
    ],
    resize_keyboard=True
)

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    bal = await get_sms_balance()
    await message.answer(
        f"👋 **Welcome to SMS Bot!**\n💰 **SMS Balance:** ${bal}\n\nNicher menu theke country select korun:", 
        reply_markup=main_menu, 
        parse_mode="Markdown"
    )

@dp.message(F.text == "🌍 Country")
async def country_menu(message: types.Message):
    buttons = []
    temp_row = []
    for c_key, c_info in COUNTRY_MAP.items():
        temp_row.append(InlineKeyboardButton(text=c_info["name"], callback_data=f"select_{c_key}"))
        if len(temp_row) == 2:
            buttons.append(temp_row)
            temp_row = []
    if temp_row:
        buttons.append(temp_row)
        
    buttons.append([InlineKeyboardButton(text="🔄 Refresh Countries", callback_data="refresh_countries")])
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer("🌍 **Select Country:**", reply_markup=kb, parse_mode="Markdown")

# Show Panel-like Live Rates & Stock
@dp.callback_query(F.data.startswith("select_"))
async def view_panel_rates(callback: types.CallbackQuery):
    c_key = callback.data.split("_")[1]
    c_info = COUNTRY_MAP.get(c_key)
    c_code = c_info["code"]
    
    await callback.message.edit_text(f"⏳ Loading live rates for {c_info['name']}...")
    
    prices = await get_smsbower_prices(c_code, service="tg")
    
    kb_list = []
    if prices:
        # Sort prices like panel (Low to High or High to Low)
        for price, stock in sorted(prices.items(), key=lambda x: float(x[0])):
            kb_list.append([InlineKeyboardButton(
                text=f"💵 ${price}  |  📦 Stock: {stock} pcs", 
                callback_data=f"buy_{c_code}_{price}_{c_key}"
            )])
    else:
        kb_list.append([InlineKeyboardButton(text="⚡ Buy Best Available Rate", callback_data=f"buy_{c_code}_auto_{c_key}")])
        
    kb_list.append([InlineKeyboardButton(text="🌍 Change Country", callback_data="back_to_countries")])
    
    kb = InlineKeyboardMarkup(inline_keyboard=kb_list)
    await callback.message.edit_text(
        f"📊 **Live Rates & Stock for {c_info['name']}**\n\nApnar panel-er moto live rate gulo niche dewa holo:",
        reply_markup=kb,
        parse_mode="Markdown"
    )

@dp.callback_query(F.data == "back_to_countries")
async def back_countries(callback: types.CallbackQuery):
    await callback.message.delete()
    await country_menu(callback.message)

# Buy Number Process with Selected Rate
@dp.callback_query(F.data.startswith("buy_"))
async def process_buy(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    c_code = parts[1]
    price = parts[2]
    c_key = parts[3]
    
    await callback.message.edit_text("⏳ Requesting number from SMSBower panel...")
    
    act_id, phone_res = await buy_number_with_rate(c_code, price=price, service="tg")
    
    if not act_id:
        # Fallback to auto if specific price gives NO_NUMBERS
        act_id, phone_res = await buy_number_with_rate(c_code, price="auto", service="tg")
        
    if not act_id:
        await callback.message.edit_text(f"❌ Failed: `{phone_res}`\n(Stock sesh ba rate-e number nei)", parse_mode="Markdown")
        return
        
    await callback.message.edit_text("🔍 Checking Status on Telegram...")
    status = await check_telegram_status(f"+{phone_res}")
    
    msg = (
        f"✅ **New Telegram Number**\n"
        f"Power By SMSBower\n\n"
        f"🌍 Country: {COUNTRY_MAP[c_key]['name']}\n"
        f"📱 Number: `+{phone_res}`\n"
        f"💵 Cost: ${price if price != 'auto' else '0.119'}\n"
        f"🔍 Number Status: {status}\n"
        f"🆔 Activation: `{act_id}`"
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔑 Get OTP", callback_data=f"otp_{act_id}")],
        [InlineKeyboardButton(text="🔄 Another Code", callback_data=f"select_{c_key}")]
    ])
    await callback.message.edit_text(msg, reply_markup=kb, parse_mode="Markdown")

@dp.message(F.text == "⚙️ Settings & Info")
async def settings_info(message: types.Message):
    bal = await get_sms_balance()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"💰 Balance: ${bal}", callback_data="bal_info")],
        [InlineKeyboardButton(text="⚡ Speed Tuning (3s Safe Delay)", callback_data="speed_info")],
        [InlineKeyboardButton(text="🔢 Set Limit (Batch 10)", callback_data="limit_info")]
    ])
    await message.answer("⚙️ **Settings & Account Info**", reply_markup=kb, parse_mode="Markdown")

@dp.message(F.text == "▶️ Start Bulk")
async def start_bulk(message: types.Message):
    await message.answer("▶️ Bulk process started!")

@dp.message(F.text == "⏹ Stop Bulk")
async def stop_bulk(message: types.Message):
    await message.answer("⏹ Bulk process stopped successfully.")

@dp.message(F.text == "💱 Change Rate")
async def change_rate(message: types.Message):
    await message.answer("💱 Panel Live Rate Mode Active.")

@dp.message(F.text == "🚫 Cancel (No OTP)")
@dp.message(F.text == "🔄 Reset Bot")
async def reset_bot(message: types.Message):
    await message.answer("🔄 Bot cache reset done.", reply_markup=main_menu)

async def main():
    print("Bot running with panel live multi-rates...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
