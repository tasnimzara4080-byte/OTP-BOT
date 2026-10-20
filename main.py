import os
import asyncio
import aiohttp
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram import Client
from pyrogram.errors import PhoneNumberBanned

BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
SMSBOWER_KEY = os.getenv("SMSBOWER_KEY")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

tele_client = Client("checker_session", api_id=API_ID, api_hash=API_HASH)

COUNTRY_MAP = {
    "colombia": {"code": "0", "name": "Colombia (+57)"},
    "chile": {"code": "3", "name": "Chile (+56)"},
    "usa": {"code": "18", "name": "USA Virtual (+1)"},
    "indonesia": {"code": "6", "name": "Indonesia (+62)"},
    "argentina": {"code": "52", "name": "Argentina (+54)"},
    "ukraine": {"code": "1", "name": "Ukraine (+380)"}
}

async def get_sms_balance():
    url = f"https://smsbower.com/stubs/handler_api.php?api_key={SMSBOWER_KEY}&action=getBalance"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            text = await resp.text()
            if "ACCESS_BALANCE" in text:
                return text.split(":")[1]
            return "0.00"

# Robust price parser for SMSBower API
async def get_smsbower_prices(country_code, service="tg"):
    url = f"https://smsbower.com/stubs/handler_api.php?api_key={SMSBOWER_KEY}&action=getPrices&service={service}&country={country_code}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            try:
                data = await resp.json()
                # Handle different possible JSON nested formats from SMSBower
                if str(country_code) in data:
                    c_data = data[str(country_code)]
                    if service in c_data:
                        return c_data[service]
                    return c_data
                elif service in data:
                    return data[service]
                return data
            except Exception:
                return {}

async def buy_number_with_rate(country_code, price=None, service="tg"):
    url = f"https://smsbower.com/stubs/handler_api.php?api_key={SMSBOWER_KEY}&action=getNumber&service={service}&country={country_code}"
    if price and price != "auto":
        url += f"&price={price}"
        
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            text = await resp.text()
            if "ACCESS_NUMBER" in text:
                parts = text.split(":")
                return parts[1], parts[2]
            return None, text

async def cancel_smsbower_activation(activation_id):
    url = f"https://smsbower.com/stubs/handler_api.php?api_key={SMSBOWER_KEY}&action=setStatus&status=8&id={activation_id}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            return await resp.text()

async def check_telegram_status(phone_number):
    try:
        if not tele_client.is_connected:
            await tele_client.start()
        sent_code = await tele_client.send_code(phone_number)
        if sent_code.type.name == "APP":
            return "Used"
        return "Fresh"
    except PhoneNumberBanned:
        return "Blocked"
    except Exception:
        return "Blocked"

async def fetch_fresh_number(c_code, price):
    max_attempts = 3
    for attempt in range(max_attempts):
        act_id, phone_res = await buy_number_with_rate(c_code, price=price, service="tg")
        if not act_id:
            continue
            
        status = await check_telegram_status(f"+{phone_res}")
        if status == "Fresh":
            return act_id, phone_res, status
        else:
            await cancel_smsbower_activation(act_id)
            await asyncio.sleep(1)
            
    return None, None, "Failed"

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
    await message.answer(f"👋 **Welcome to SMS Bot!**\n💰 **SMS Balance:** ${bal}\n\nSelect country:", reply_markup=main_menu, parse_mode="Markdown")

@dp.message(F.text == "🌍 Country")
async def country_menu(message: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=info["name"], callback_data=f"select_{key}")] for key, info in COUNTRY_MAP.items()
    ])
    await message.answer("🌍 **Select Country:**", reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data.startswith("select_"))
async def view_panel_rates(callback: types.CallbackQuery):
    c_key = callback.data.split("_")[1]
    c_info = COUNTRY_MAP.get(c_key)
    
    await callback.message.edit_text(f"⏳ Loading live rates for {c_info['name']}...")
    
    prices = await get_smsbower_prices(c_info["code"], service="tg")
    
    kb_list = []
    if prices and isinstance(prices, dict):
        for price, stock in sorted(prices.items(), key=lambda x: float(x[0])):
            kb_list.append([InlineKeyboardButton(text=f"💵 ${price}  |  📦 Stock: {stock} pcs", callback_data=f"buy_{c_info['code']}_{price}_{c_key}")])
    else:
        # Fallback rates if api structure varies
        default_rates = ["0.119", "0.134", "0.175", "0.182", "0.19"]
        for p in default_rates:
            kb_list.append([InlineKeyboardButton(text=f"💵 ${p}  |  📦 Stock: Available", callback_data=f"buy_{c_info['code']}_{p}_{c_key}")])
            
    kb_list.append([InlineKeyboardButton(text="🌍 Change Country", callback_data="back_to_countries")])
    kb = InlineKeyboardMarkup(inline_keyboard=kb_list)
    
    await callback.message.edit_text(f"📊 **Live Rates & Stock for {c_info['name']}**\nNiche apnar panel-er moto live rate gulo dewa holo:", reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data == "back_to_countries")
async def back_countries(callback: types.CallbackQuery):
    await callback.message.delete()
    await country_menu(callback.message)

@dp.callback_query(F.data.startswith("buy_"))
async def process_buy(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    c_code, price, c_key = parts[1], parts[2], parts[3]
    
    await callback.message.edit_text(f"⏳ Searching for a 🟢 Fresh number at ${price}...")
    
    act_id, phone_res, status = await fetch_fresh_number(c_code, price)
    
    if not act_id or status != "Fresh":
        await callback.message.edit_text(f"❌ ${price} rate-e ekhoni kono fresh number paowa jayni (Blocked chilo ba stock sesh).", parse_mode="Markdown")
        return
        
    msg = (
        f"✅ **New Telegram Number**\n"
        f"Power By SMSBower\n\n"
        f"🌍 Country: {COUNTRY_MAP[c_key]['name']}\n"
        f"📱 Number: `+{phone_res}`\n"
        f"💵 Cost: ${price}\n"
        f"🔍 Number Status: 🟢 Fresh\n"
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
    await message.answer(f"⚙️ **Balance:** ${bal}", parse_mode="Markdown")

@dp.message(F.text == "🚫 Cancel (No OTP)")
@dp.message(F.text == "🔄 Reset Bot")
async def reset_bot(message: types.Message):
    await message.answer("🔄 Reset done.", reply_markup=main_menu)

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
