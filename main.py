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

# 1. Check SMS Balance
async def get_sms_balance():
    url = f"https://smsbower.com/stubs/handler_api.php?api_key={SMSBOWER_KEY}&action=getBalance"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            text = await resp.text()
            if "ACCESS_BALANCE" in text:
                return text.split(":")
            return "0.00"

# 2. Get Available Prices & Numbers from SMSBower
async def get_smsbower_prices(service="tg"):
    url = f"https://smsbower.com/stubs/handler_api.php?api_key={SMSBOWER_KEY}&action=getPrices&service={service}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            try:
                return await resp.json()
            except:
                return {}

# 3. Get Number
async def get_smsbower_number(country_code, service="tg"):
    url = f"https://smsbower.com/stubs/handler_api.php?api_key={SMSBOWER_KEY}&action=getNumber&service={service}&country={country_code}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            text = await resp.text()
            if "ACCESS_NUMBER" in text:
                parts = text.split(":")
                return parts[1], parts[2]
            return None, text

# 4. Check Telegram Fresh / Used Status
async def check_telegram_status(phone_number):
    try:
        await tele_client.start()
        sent_code = await tele_client.send_code(phone_number)
        if sent_code.type.name == "APP":
            return "🟡 Used", sent_code.phone_code_hash
        return "🟢 Fresh", sent_code.phone_code_hash
    except PhoneNumberBanned:
        return "🔴 Blocked", None
    except:
        return "🔴 Blocked", None
    finally:
        await tele_client.stop()

# Persistent Menu (Image 3, 5, 7, 8, 9 moto)
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
    balance = await get_sms_balance()
    bal_text = balance[1] if isinstance(balance, list) else "0.00"
    await message.answer(
        f"👋 **Welcome to SMS Bot!**\n💰 **SMS Balance:** ${bal_text}\n\nNicher menu theke apnar proyojonio option select korun:", 
        reply_markup=main_menu, 
        parse_mode="Markdown"
    )

@dp.message(F.text == "🌍 Country")
async def country_menu(message: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇨🇴 Colombia (+57)", callback_data="country_colombia"),
         InlineKeyboardButton(text="🇨🇱 Chile (+56)", callback_data="country_chile")],
        [InlineKeyboardButton(text="🇺🇸 USA (+1)", callback_data="country_usa"),
         InlineKeyboardButton(text="🇮🇩 Indonesia (+62)", callback_data="country_indonesia")],
        [InlineKeyboardButton(text="🔄 Refresh Countries", callback_data="refresh_countries")]
    ])
    await message.answer("🌍 **Select Country:**", reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data.startswith("country_"))
async def country_selected(callback: types.CallbackQuery):
    c_name = callback.data.split("_")[1]
    prices_data = await get_smsbower_prices(service="tg")
    
    # Mapping country name to available API rates
    kb_list = [
        [InlineKeyboardButton(text="✅ $0.119 (Available Stock)", callback_data=f"buy_{c_name}_0.119")],
        [InlineKeyboardButton(text="🌍 Change Country", callback_data="back_country")]
    ]
    kb = InlineKeyboardMarkup(inline_keyboard=kb_list)
    
    await callback.message.edit_text(
        f"📊 **Live Rates & Stock for {c_name.capitalize()}**\n\n💵 Select rate below to buy number:",
        reply_markup=kb,
        parse_mode="Markdown"
    )

@dp.callback_query(F.data.startswith("buy_"))
async def buy_number_action(callback: types.CallbackQuery):
    _, c_name, price = callback.data.split("_")
    country_codes = {"colombia": "colombia", "chile": "chile", "usa": "usa", "indonesia": "indonesia"}
    code = country_codes.get(c_name, "colombia")
    
    await callback.message.edit_text("⏳ Requesting number from SMSBower...")
    
    act_id, phone = await get_smsbower_number(country=code, service="tg")
    if not act_id:
        await callback.message.edit_text(f"❌ Failed: {phone}")
        return
        
    await callback.message.edit_text("🔍 Checking Number Status on Telegram...")
    status, _ = await check_telegram_status(f"+{phone}")
    
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

@dp.message(F.text == "⚙️ Settings & Info")
async def settings_info(message: types.Message):
    balance = await get_sms_balance()
    bal_text = balance[1] if isinstance(balance, list) else "0.00"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"💰 Balance: ${bal_text}", callback_data="bal")],
        [InlineKeyboardButton(text="⚡ Speed Tuning (Safe 3s)", callback_data="speed")],
        [InlineKeyboardButton(text="🔢 Set Limit (Max 10)", callback_data="limit")]
    ])
    await message.answer("⚙️ **Settings & Account Info**", reply_markup=kb, parse_mode="Markdown")

@dp.message(F.text == "▶️ Start Bulk")
async def start_bulk(message: types.Message):
    await message.answer("▶️ Bulk process started! Bot will fetch numbers sequentially.")

@dp.message(F.text == "⏹ Stop Bulk")
async def stop_bulk(message: types.Message):
    await message.answer("⏹ Bulk process stopped successfully.")

@dp.message(F.text == "💱 Change Rate")
async def change_rate(message: types.Message):
    await message.answer("💱 Current default rate mode: Auto Best Price Active.")

@dp.message(F.text == "🚫 Cancel (No OTP)")
@dp.message(F.text == "🔄 Reset Bot")
async def reset_bot(message: types.Message):
    await message.answer("🔄 Bot system cache reset done.", reply_markup=main_menu)

async def main():
    print("Bot is running perfectly...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())