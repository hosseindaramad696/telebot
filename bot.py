import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

BOT_TOKEN = os.environ["BOT_TOKEN"]

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

class UserState(StatesGroup):
    idle = State()
    waiting = State()
    chatting = State()

waiting_queue: list[int] = []
active_chats: dict[int, int] = {}

def main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔍 جستجوی همکلام")],
            [KeyboardButton(text="📊 آمار"), KeyboardButton(text="❓ راهنما")],
        ],
        resize_keyboard=True
    )

def chat_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="⏭ همکلام بعدی"), KeyboardButton(text="🚫 پایان چت")],
        ],
        resize_keyboard=True
    )

def waiting_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ لغو جستجو")]],
        resize_keyboard=True
    )

@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.set_state(UserState.idle)
    name = message.from_user.first_name or "کاربر"
    await message.answer(
        f"👋 سلام {name}!\n\n"
        "به *تله چت* خوش اومدی 🎭\n"
        "اینجا می‌تونی با افراد ناشناس چت کنی.\n\n"
        "برای شروع دکمه 🔍 جستجوی همکلام رو بزن.",
        reply_markup=main_keyboard(),
        parse_mode="Markdown"
    )

@dp.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "📖 *راهنمای تله چت*\n\n"
        "🔍 جستجوی همکلام — وارد صف می‌شی\n"
        "⏭ همکلام بعدی — کاربر جدید\n"
        "🚫 پایان چت — قطع اتصال\n"
        "❌ لغو جستجو — خروج از صف\n\n"
        "📌 متن، عکس، ویدیو، صدا و استیکر پشتیبانی می‌شه.\n"
        "⚠️ هویت هیچ‌کس فاش نمی‌شه.",
        parse_mode="Markdown",
        reply_markup=main_keyboard()
    )

async def do_search(user_id: int, state: FSMContext):
    if waiting_queue:
        partner_id = waiting_queue.pop(0)
        active_chats[user_id] = partner_id
        active_chats[partner_id] = user_id

        await state.set_state(UserState.chatting)
        partner_state = FSMContext(storage=storage, key={"chat": partner_id, "user": partner_id, "bot": bot.id})
        await partner_state.set_state(UserState.chatting)

        msg = "✅ *همکلام پیدا شد!*\n\nشروع به چت کن 💬\nبرای پایان: 🚫 پایان چت"
        await bot.send_message(user_id, msg, reply_markup=chat_keyboard(), parse_mode="Markdown")
        await bot.send_message(partner_id, msg, reply_markup=chat_keyboard(), parse_mode="Markdown")
    else:
        waiting_queue.append(user_id)
        await state.set_state(UserState.waiting)
        online = len(active_chats) // 2
        await bot.send_message(
            user_id,
            f"🔍 *در حال جستجو...*\n\n"
            f"👥 آنلاین: {online * 2 + len(waiting_queue)}\n"
            f"💬 چت فعال: {online}\n\n"
            "صبر کن تا همکلام پیدا بشه ⏳",
            reply_markup=waiting_keyboard(),
            parse_mode="Markdown"
        )

async def do_end(user_id: int, state: FSMContext, reason="end", notify_partner=True):
    partner_id = active_chats.pop(user_id, None)
    if partner_id:
        active_chats.pop(partner_id, None)
    await state.set_state(UserState.idle)
    if partner_id and notify_partner:
        partner_state = FSMContext(storage=storage, key={"chat": partner_id, "user": partner_id, "bot": bot.id})
        await partner_state.set_state(UserState.idle)
        if reason == "next":
            txt = "⏭ همکلامت رفت سراغ نفر بعدی.\n\nبرای چت جدید 🔍 جستجو رو بزن."
        else:
            txt = "🚫 همکلامت چت رو پایان داد.\n\nبرای چت جدید 🔍 جستجو رو بزن."
        await bot.send_message(partner_id, txt, reply_markup=main_keyboard())
    return partner_id

@dp.message(F.text == "🔍 جستجوی همکلام")
async def btn_search(message: Message, state: FSMContext):
    user_id = message.from_user.id
    cur = await state.get_state()
    if cur == UserState.chatting.state:
        await do_end(user_id, state, reason="next", notify_partner=True)
        await asyncio.sleep(0.2)
    if user_id in waiting_queue:
        await message.answer("⏳ هنوز در صف انتظاری...", reply_markup=waiting_keyboard())
        return
    await do_search(user_id, state)

@dp.message(F.text == "❌ لغو جستجو")
async def btn_cancel(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if user_id in waiting_queue:
        waiting_queue.remove(user_id)
    await state.set_state(UserState.idle)
    await message.answer("✅ جستجو لغو شد.", reply_markup=main_keyboard())

@dp.message(F.text == "🚫 پایان چت")
async def btn_end(message: Message, state: FSMContext):
    user_id = message.from_user.id
    partner = await do_end(user_id, state, reason="end")
    if partner:
        await message.answer("🚫 چت پایان یافت.\n\nبرای چت جدید 🔍 جستجو رو بزن.", reply_markup=main_keyboard())
    else:
        await message.answer("❌ الان در هیچ چتی نیستی.", reply_markup=main_keyboard())

@dp.message(F.text == "⏭ همکلام بعدی")
async def btn_next(message: Message, state: FSMContext):
    user_id = message.from_user.id
    await do_end(user_id, state, reason="next")
    await message.answer("🔍 دنبال همکلام جدید می‌گردم...", reply_markup=waiting_keyboard())
    await asyncio.sleep(0.2)
    await do_search(user_id, state)

@dp.message(F.text == "📊 آمار")
async def btn_stats(message: Message):
    online = len(active_chats) // 2
    await message.answer(
        f"📊 *آمار تله چت*\n\n"
        f"💬 چت فعال: {online}\n"
        f"⏳ در صف: {len(waiting_queue)}\n"
        f"👥 آنلاین: {online * 2 + len(waiting_queue)}",
        parse_mode="Markdown"
    )

@dp.message(F.text == "❓ راهنما")
async def btn_help(message: Message):
    await cmd_help(message)

@dp.message(UserState.chatting)
async def relay(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if user_id not in active_chats:
        await state.set_state(UserState.idle)
        await message.answer("❌ اتصال قطع شده.", reply_markup=main_keyboard())
        return
    partner_id = active_chats[user_id]
    try:
        if message.text:
            await bot.send_message(partner_id, message.text)
        elif message.photo:
            await bot.send_photo(partner_id, message.photo[-1].file_id, caption=message.caption or "")
        elif message.video:
            await bot.send_video(partner_id, message.video.file_id, caption=message.caption or "")
        elif message.voice:
            await bot.send_voice(partner_id, message.voice.file_id)
        elif message.audio:
            await bot.send_audio(partner_id, message.audio.file_id)
        elif message.sticker:
            await bot.send_sticker(partner_id, message.sticker.file_id)
        elif message.document:
            await bot.send_document(partner_id, message.document.file_id, caption=message.caption or "")
        elif message.video_note:
            await bot.send_video_note(partner_id, message.video_note.file_id)
        elif message.animation:
            await bot.send_animation(partner_id, message.animation.file_id)
        elif message.location:
            await bot.send_location(partner_id, message.location.latitude, message.location.longitude)
        else:
            await message.answer("⚠️ این نوع پیام پشتیبانی نمی‌شه.")
    except Exception as e:
        logger.error(f"Relay error: {e}")
        await message.answer("❌ خطا در ارسال. همکلامت شاید ربات رو بلاک کرده.")
        await do_end(user_id, state, notify_partner=False)

@dp.message(UserState.waiting)
async def waiting_msg(message: Message):
    if message.text != "❌ لغو جستجو":
        await message.answer("⏳ هنوز در صف انتظاری...")

async def main():
    logger.info("Bot started!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
