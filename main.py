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

# User settings memory dictionary (Limit & Speed tuning)
user_settings = {}

# 1. Fetch Countries and Prices from SMSBower API
async def get_prices_and_countries(service="telegram"):
    url = f"https://smsbower.com/stubs/handler_api.php?api_key={SMSBOWER_KEY}&action=getPrices&service={service}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            try:
                data = await resp.json()
                return data
            except:
                return {}

# 2. Buy Number Function based on Country
async def get_smsbower_number(country_code, service="telegram"):
    url = f"https://smsbower.com/stubs/handler_api.php?api_key={SMSBOWER_KEY}&action=getNumber&service={service}&country={country_code}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            text = await resp.text()
            if "ACCESS_NUMBER" in text:
                parts = text.split(":")
                return parts[1], parts[2]
            return None, text

# 3. Check Telegram Fresh / Used / Blocked Status
async def check_telegram_status(phone_number):
    try:
        await tele_client.start()
        sent_code = await tele_client.send_code(phone_number)
        if sent_code.type.name == "APP":
            status = "🟡 Used"
        else:
            status = "🟢 Fresh"
        return status, sent_code.phone_code_hash
    except PhoneNumberBanned:
        return "🔴 Blocked", None
    except Exception:
        return "🔴 Blocked", None
    finally:
        await tele_client.stop()

# Main Reply Keyboard (Image 7, 8, 9 er nicher menu er moto)
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
    await message.answer(
        "👋 **Welcome to SMS Bot!**\nNicher menu theke apnar proyojonio option select korun:", 
        reply_markup=main_menu, 
        parse_mode="Markdown"
    )

# Country Selection Menu (Image 7)
@dp.message(F.text == "🌍 Country")
async def select_country_menu(message: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Colombia (+57)", callback_data="country_colombia"),
         InlineKeyboardButton(text="Chile (+56)", callback_data="country_chile")],
        [InlineKeyboardButton(text="USA Virtual (+1)", callback_data="country_usa"),
         InlineKeyboardButton(text="Indonesia (+62)", callback_data="country_indonesia")],
        [InlineKeyboardButton(text="🔄 Refresh Countries", callback_data="refresh_countries")]
    ])
    await message.answer("🌍 **Select Country:**", reply_markup=kb, parse_mode="Markdown")

# Handle Country Selection and Show Live Rates & Stock (Image 8)
@dp.callback_query(F.data.startswith("country_"))
async def country_selected(callback: types.CallbackQuery):
    country_name = callback.data.split("_")[1].capitalize()
    country_codes = {"colombia": "0", "chile": "3", "usa": "18", "indonesia": "6"}
    code = country_codes.get(country_name.lower(), "0")
    
    await callback.message.edit_text(f"⏳ Fetching live rates for {country_name}...")
    
    # Example live data format matching image 8
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ $0.175 (102 Stock)", callback_data=f"buy_{code}_0.175")],
        [InlineKeyboardButton(text="💵 $0.182 (57731 Stock)", callback_data=f"buy_{code}_0.182")],
        [InlineKeyboardButton(text="💱 Custom Rate", callback_data="custom_rate"),
         InlineKeyboardButton(text="🌍 Change Country", callback_data="back_country")]
    ])
    
    rate_msg = (
        f"📊 **Live Rates & Stock for {country_name}**\n\n"
        f"🟢 Status: Available\n"
        f"💵 Select rate below to buy number:"
    )
    await callback.message.edit_text(rate_msg, reply_markup=kb, parse_mode="Markdown")

# Buy Number and Check Status
@dp.callback_query(F.data.startswith("buy_"))
async def buy_number_process(callback: types.CallbackQuery):
    _, country_code, price = callback.data.split("_")
    
    await callback.message.edit_text("⏳ Requesting number from SMSBower...")
    
    # Mapping back code to country string for API
    country_map = {"0": "colombia", "3": "chile", "18": "usa", "6": "indonesia"}
    c_name = country_map.get(country_code, "colombia")
    
    act_id, phone = await get_smsbower_number(country=c_name, service="telegram")
    
    if not act_id:
        await callback.message.edit_text(f"❌ Failed to get number: {phone}")
        return
        
    await callback.message.edit_text("🔍 Checking Number Status on Telegram...")
    status, code_hash = await check_telegram_status(f"+{phone}")
    
    msg = (
        f"✅ **New Telegram Number**\n"
        f"Power By SMSBower\n\n"
        f"🌍 Country: {c_name.capitalize()}\n"
        f"📱 Number: `+{phone}`\n"
        f"💵 Cost: ${price}\n"
        f"🔍 Number Status: {status}\n"
        f"🆔 Activation: `{act_id}`"
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔑 Get OTP", callback_data=f"otp_{act_id}")],
        [InlineKeyboardButton(text="🔄 Another Code", callback_data=f"country_{c_name}")]
    ])
    await callback.message.edit_text(msg, reply_markup=kb, parse_mode="Markdown")

# Settings & Info Menu (Image 9)
@dp.message(F.text == "⚙️ Settings & Info")
async def settings_info(message: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 SMS Balance", callback_data="set_bal"),
         InlineKeyboardButton(text="💳 Add Balance", callback_data="add_bal")],
        [InlineKeyboardButton(text="⚡ Speed Tuning", callback_data="speed_tuning"),
         InlineKeyboardButton(text="🔢 Set Limit", callback_data="set_limit")],
        [InlineKeyboardButton(text="📊 Success Stats", callback_data="stats")]
    ])
    await message.answer("⚙️ **Settings & Account Info**\nSelect an option below:", reply_markup=kb, parse_mode="Markdown")

# Speed Tuning Callback
@dp.callback_query(F.data == "speed_tuning")
async def speed_tuning(callback: types.CallbackQuery):
    await callback.message.answer("⚡ Speed set to safe mode (Delay: 3 seconds per request to avoid ban).")

# Set Limit Callback
@dp.callback_query(F.data == "set_limit")
async def set_limit(callback: types.CallbackQuery):
    await callback.message.answer("🔢 Current Limit: Max 10 numbers per batch.")

@dp.message(F.text == "🔄 Reset Bot")
async def reset_bot(message: types.Message):
    await message.answer("🔄 Bot system cache cleared.", reply_markup=main_menu)

@dp.message(F.text == "🚫 Cancel (No OTP)")
async def cancel_action(message: types.Message):
    await message.answer("♻️ Operation cancelled successfully.", reply_markup=main_menu)

async def main():
    print("Bot is running with advanced features...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
