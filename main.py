import os
import asyncio
import aiohttp
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram import Client
from pyrogram.errors import PhoneNumberBanned, PhoneNumberInvalid, FloodWait

# Environment Variables
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
SMSBOWER_KEY = os.getenv("SMSBOWER_KEY")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Pyrogram Client for checking Telegram status
tele_client = Client("checker_session", api_id=API_ID, api_hash=API_HASH)

# SMSBower Number Buy Function
async def get_smsbower_number(country="colombia", service="tg"):
    url = f"https://smsbower.com/stubs/handler_api.php?api_key={SMSBOWER_KEY}&action=getNumber&service={service}&country={country}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            text = await resp.text()
            # Response: ACCESS_NUMBER:$id:$number
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
            status = "🟡 Used (Active App)"
        else:
            status = "🟢 Fresh"
            
        return status, sent_code.phone_code_hash
    except PhoneNumberBanned:
        return "🔴 Blocked / Banned", None
    except Exception as e:
        return f"❌ Error ({str(e)})", None
    finally:
        await tele_client.stop()

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📱 Get Colombia Telegram Number", callback_data="get_colombia")]
    ])
    await message.answer("👋 **Welcome to SMS Bot!**\nNicher button-e click kore number nin:", reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data == "get_colombia")
async def process_get_number(callback: types.CallbackQuery):
    await callback.message.edit_text("⏳ Requesting number from SMSBower...")
    
    act_id, phone = await get_smsbower_number(country="colombia", service="tg")
    
    if not act_id:
        await callback.message.edit_text(f"❌ Failed to get number: {phone}")
        return
        
    await callback.message.edit_text("🔍 Checking Number Status on Telegram...")
    status, code_hash = await check_telegram_status(f"+{phone}")
    
    msg = (
        f"✅ **New Telegram Number**\n"
        f"Power By SMSBower\n\n"
        f"🌍 **Country:** Colombia\n"
        f"📱 **Number:** `+{phone}`\n"
        f"💵 **Cost:** $0.119\n"
        f"🔍 **Number Status:** {status}\n"
        f"🆔 **Activation:** `{act_id}`"
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔑 Get OTP", callback_data=f"otp_{act_id}")],
        [InlineKeyboardButton(text="🔄 Another Code", callback_data="get_colombia")]
    ])
    
    await callback.message.edit_text(msg, reply_markup=kb, parse_mode="Markdown")

async def main():
    print("Bot is running...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
