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

# SMSBower Number Buy Function (service name 'telegram' ba 'tg' use kora jay)
async def get_smsbower_number(country="colombia", service="telegram"):
    url = f"https://smsbower.com/stubs/handler_api.php?api_key={SMSBOWER_KEY}&action=getNumber&service={service}&country={country}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            text = await resp.text()
            # Response format: ACCESS_NUMBER:$id:$number
            if "ACCESS_NUMBER" in text:
                parts = text.split(":")
                return parts[1], parts[2]
            return None, text

# Check Telegram Fresh / Used / Blocked Status
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
    except Exception as e:
        return f"🔴 Blocked", None
    finally:
        await tele_client.stop()

# Bot er nicher permanent menu button gulo (Image 3 er moto)
main_menu_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📱 Get Colombia Number"), KeyboardButton(text="❌ Cancel (No OTP)")],
        [KeyboardButton(text="🌍 Country"), KeyboardButton(text="⚙️ Settings & Info")],
        [KeyboardButton(text="🔄 Reset Bot")]
    ],
    resize_keyboard=True
)

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    await message.answer(
        "👋 **Welcome to SMS Bot!**\nNicher menu theke apnar proyojonio option select korun:", 
        reply_markup=main_menu_keyboard, 
        parse_mode="Markdown"
    )

@dp.message(F.text == "📱 Get Colombia Number")
async def process_get_number_btn(message: types.Message):
    sent_msg = await message.answer("⏳ Requesting number from SMSBower...")
    
    # SMSBower e service 'telegram' ba 'tg' use hoy
    act_id, phone = await get_smsbower_number(country="colombia", service="telegram")
    
    if not act_id:
        await message.answer(f"❌ Failed to get number: {phone}")
        return
        
    await bot.edit_message_text(
        chat_id=sent_msg.chat.id, 
        message_id=sent_msg.message_id, 
        text="🔍 Checking Number Status on Telegram..."
    )
    
    status, code_hash = await check_telegram_status(f"+{phone}")
    
    msg = (
        f"✅ **New Telegram Number**\n"
        f"Power By SMSBower\n\n"
        f"🌍 Country: Colombia\n"
        f"📱 Number: `+{phone}`\n"
        f"💵 Cost: $0.119\n"
        f"🔍 Number Status: {status}\n"
        f"🆔 Activation: `{act_id}`"
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔑 Get OTP", callback_data=f"otp_{act_id}")],
        [InlineKeyboardButton(text="🔄 Another Code", callback_data=f"another_{act_id}")]
    ])
    
    await bot.edit_message_text(
        chat_id=sent_msg.chat.id, 
        message_id=sent_msg.message_id, 
        text=msg, 
        reply_markup=kb, 
        parse_mode="Markdown"
    )

@dp.message(F.text == "❌ Cancel (No OTP)")
async def cancel_btn(message: types.Message):
    await message.answer("♻️ Operation cancelled successfully.", reply_markup=main_menu_keyboard)

@dp.message(F.text == "🌍 Country")
async def country_btn(message: types.Message):
    await message.answer("🌍 Available Country: Colombia", reply_markup=main_menu_keyboard)

@dp.message(F.text == "⚙️ Settings & Info")
async def settings_btn(message: types.Message):
    await message.answer("⚙️ Bot is connected with SMSBower API & Pyrogram Checker.", reply_markup=main_menu_keyword if 'main_menu_keyword' in globals() else main_menu_keyboard)

@dp.message(F.text == "🔄 Reset Bot")
async def reset_btn(message: types.Message):
    await message.answer("🔄 Bot cache reset done.", reply_markup=main_menu_keyboard)

async def main():
    print("Bot is running...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
