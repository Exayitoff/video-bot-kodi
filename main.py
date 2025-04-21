import os
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.utils import executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
import sqlite3
from datetime import datetime

# Bot konfiguratsiyasi
API_TOKEN = '5898886148:AAEJiLJtlviPYRSXGj0MS3GOXIRZKNfhols'
ADMIN_IDS = [693313498,7616547068,1976782521]  # Admin ID lari
CHANNELS = []  # Majburiy obuna kanallari

# Database yaratish
conn = sqlite3.connect('bot.db')
cursor = conn.cursor()

# Jadval yaratish
cursor.execute('''CREATE TABLE IF NOT EXISTS users
             (user_id INTEGER PRIMARY KEY, username TEXT, full_name TEXT, join_date TEXT, referrals INTEGER DEFAULT 0, is_premium INTEGER DEFAULT 0)''')

cursor.execute('''CREATE TABLE IF NOT EXISTS referrals
             (referrer_id INTEGER, referred_id INTEGER, PRIMARY KEY (referrer_id, referred_id))''')

cursor.execute('''CREATE TABLE IF NOT EXISTS videos
             (video_id INTEGER PRIMARY KEY AUTOINCREMENT, file_id TEXT, caption TEXT, category TEXT, is_premium INTEGER DEFAULT 0)''')

cursor.execute('''CREATE TABLE IF NOT EXISTS channels
             (channel_id TEXT PRIMARY KEY, channel_name TEXT)''')

conn.commit()

# Botni ishga tushirish
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# States
class AdminStates(StatesGroup):
    add_channel = State()
    remove_channel = State()
    add_video = State()
    add_video_caption = State()
    add_video_category = State()
    add_video_premium = State()

# Asosiy tugmachalarni yaratish
def main_menu():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(KeyboardButton('📹 Videolar'))
    keyboard.add(KeyboardButton('👥 Referal tizimi'))
    keyboard.add(KeyboardButton('ℹ️ Statistika'))

    return keyboard

def admin_menu():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(KeyboardButton('📊 Admin statistika'))
    keyboard.add(KeyboardButton('📹 Video qo\'shish'))
    keyboard.add(KeyboardButton('📺 Kanal qo\'shish'))
    keyboard.add(KeyboardButton('🗑 Kanal olib tashlash'))
    keyboard.add(KeyboardButton('🔙 Asosiy menyu'))
    return keyboard

def video_categories():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(KeyboardButton('🎬 Barcha videolar'))
    keyboard.add(KeyboardButton('⭐ Premium videolar'))
    keyboard.add(KeyboardButton('🔙 Asosiy menyu'))
    return keyboard

# Start komandasi
@dp.message_handler(commands=['start'])
async def send_welcome(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username
    full_name = message.from_user.full_name
    join_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Foydalanuvchini bazaga qo'shish
    cursor.execute("INSERT OR IGNORE INTO users (user_id, username, full_name, join_date) VALUES (?, ?, ?, ?)",
                  (user_id, username, full_name, join_date))
    conn.commit()
    
    # Referal parametrini tekshirish
    args = message.get_args()
    if args:
        referrer_id = int(args)
        if referrer_id != user_id:
            cursor.execute("INSERT OR IGNORE INTO referrals (referrer_id, referred_id) VALUES (?, ?)", (referrer_id, user_id))
            cursor.execute("UPDATE users SET referrals = referrals + 1 WHERE user_id = ?", (referrer_id,))
            
            # 3 ta referal bo'lsa premium qilish
            cursor.execute("SELECT referrals FROM users WHERE user_id = ?", (referrer_id,))
            referrals = cursor.fetchone()[0]
            if referrals >= 3:
                cursor.execute("UPDATE users SET is_premium = 1 WHERE user_id = ?", (referrer_id,))
            
            conn.commit()
    
    # Kanal(lar)ga obuna bo'lishni tekshirish
    not_subscribed = await check_subscription(user_id)
    if not_subscribed:
        await message.answer("Botdan to'liq foydalanish uchun quyidagi kanal(lar)ga obuna bo'ling:", 
                           reply_markup=not_subscribed)
        return
    
    # Agar barcha kanal(lar)ga obuna bo'lgan bo'lsa
    await message.answer(f"Salom {full_name}! Botimizga xush kelibsiz.", reply_markup=main_menu())
# Obunani tekshirish
async def check_subscription(user_id):
    # Bazada kanallar mavjudligini tekshirish
    cursor.execute("SELECT channel_id, channel_name FROM channels")
    channels = cursor.fetchall()
    
    if not channels:
        return None
    
    not_subscribed = []
    for channel in channels:
        channel_id, channel_name = channel
        try:
            # Kanal ID sini to'g'ri formatga keltirish
            if channel_id.startswith('@'):
                chat_id = channel_id[1:]  # @ ni olib tashlaymiz
            elif channel_id.startswith('-100'):
                chat_id = int(channel_id)  # Raqamli ID ni integer qilamiz
            else:
                chat_id = channel_id  # Boshqa formatlarni o'zgartirmaymiz
            
            # Obunani tekshirish
            member = await bot.get_chat_member(chat_id=chat_id, user_id=user_id)
            if member.status in ['left', 'kicked']:
                not_subscribed.append((channel_id, channel_name))
        except Exception as e:
            print(f"Obunani tekshirishda xato: {e}")
            # Xato bo'lsa ham foydalanuvchini kanalga obuna qilishni talab qilamiz
            not_subscribed.append((channel_id, channel_name))
    
    if not_subscribed:
        keyboard = InlineKeyboardMarkup(row_width=1)
        
        for channel_id, channel_name in not_subscribed:
            # Kanal linkini yaratish
            if channel_id.startswith('@'):
                link = f"https://t.me/{channel_id[1:]}"
            else:
                # Raqamli ID bo'lsa, username ni olishga harakat qilamiz
                try:
                    chat = await bot.get_chat(channel_id)
                    if chat.username:
                        link = f"https://t.me/{chat.username}"
                    else:
                        # Agar username bo'lmasa, kanalga obuna bo'lish uchun boshqa yo'l qidirish kerak
                        link = f"https://t.me/c/{channel_id[4:] if channel_id.startswith('-100') else channel_id}"
                        continue
                except:
                    link = f"https://t.me/c/{channel_id[4:] if channel_id.startswith('-100') else channel_id}"
            
            keyboard.add(InlineKeyboardButton(
                text=f"👉 {channel_name} kanaliga obuna bo'lish", 
                url=link
            ))
        
        keyboard.add(InlineKeyboardButton(
            text="✅ Obuna bo'ldim", 
            callback_data="check_subscription"
        ))
        
        return keyboard
    
    return None
# Obunani tekshirish tugmasi
@dp.callback_query_handler(lambda c: c.data == 'check_subscription')
async def process_check_subscription(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    
    # Obunani qayta tekshirish
    not_subscribed = await check_subscription(user_id)
    
    if not_subscribed:
        await bot.answer_callback_query(
            callback_query.id,
            "Hali barcha kanal(lar)ga obuna bo'lmagansiz!",
            show_alert=True
        )
        await bot.send_message(
            user_id,
            "Iltimos, quyidagi kanal(lar)ga obuna bo'ling:",
            reply_markup=not_subscribed
        )
    else:
        await bot.answer_callback_query(
            callback_query.id,
            "Obuna uchun rahmat! Endi botdan to'liq foydalanishingiz mumkin.",
            show_alert=True
        )
        await bot.send_message(
            user_id,
            "✅ Siz barcha kanal(lar)ga obuna bo'ldingiz! Botdan foydalanishingiz mumkin.",
            reply_markup=main_menu()
        )
# Videolar menyusi
@dp.message_handler(lambda message: message.text == '📹 Videolar')
async def videos_menu(message: types.Message):
    await message.answer("Videolar bo'limi:", reply_markup=video_categories())

# Barcha videolar
@dp.message_handler(lambda message: message.text == '🎬 Barcha videolar')
async def all_videos(message: types.Message):
    cursor.execute("SELECT * FROM videos WHERE is_premium = 0")
    videos = cursor.fetchall()
    
    if not videos:
        await message.answer("Hozircha videolar mavjud emas.")
        return
    
    for video in videos:
        file_id, caption, category = video[1], video[2], video[3]
        await bot.send_video(message.from_user.id, file_id, caption=f"{caption}\n\nKategoriya: {category}")

# Premium videolar
@dp.message_handler(lambda message: message.text == '⭐ Premium videolar')
async def premium_videos(message: types.Message):
    user_id = message.from_user.id
    cursor.execute("SELECT is_premium FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    
    if not user or not user[0]:
        await message.answer("Premium videolarni ko'rish uchun sizda 3 ta referal bo'lishi kerak.")
        return
    
    cursor.execute("SELECT * FROM videos WHERE is_premium = 1")
    videos = cursor.fetchall()
    
    if not videos:
        await message.answer("Hozircha premium videolar mavjud emas.")
        return
    
    for video in videos:
        file_id, caption, category = video[1], video[2], video[3]
        await bot.send_video(message.from_user.id, file_id, caption=f"⭐ {caption}\n\nKategoriya: {category}")

# Referal tizimi
@dp.message_handler(lambda message: message.text == '👥 Referal tizimi')
async def referral_system(message: types.Message):
    user_id = message.from_user.id
    cursor.execute("SELECT referrals, is_premium FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    
    if not result:
        await message.answer("Xatolik yuz berdi. Iltimos, /start ni bosing.")
        return
    
    referrals, is_premium = result
    referral_link = f"https://t.me/{(await bot.me).username}?start={user_id}"
    
    text = f"📌 Sizning referal havolangiz:\n{referral_link}\n\n"
    text += f"👥 Jami referallar: {referrals}\n"
    
    if is_premium:
        text += "✅ Siz premium foydalanuvchisiz!"
    else:
        text += f"🔓 Premium uchun kerak: {3 - referrals} ta referal"
    
    await message.answer(text)

# Statistika
@dp.message_handler(lambda message: message.text == 'ℹ️ Statistika')
async def statistics(message: types.Message):
    user_id = message.from_user.id
    
    # Umumiy statistika
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM users WHERE is_premium = 1")
    premium_users = cursor.fetchone()[0]
    
    # Foydalanuvchi statistikasi
    cursor.execute("SELECT referrals, is_premium FROM users WHERE user_id = ?", (user_id,))
    user_stats = cursor.fetchone()
    
    if not user_stats:
        await message.answer("Xatolik yuz berdi. Iltimos, /start ni bosing.")
        return
    
    referrals, is_premium = user_stats
    
    text = "📊 Bot statistikasi:\n\n"
    text += f"👥 Jami foydalanuvchilar: {total_users}\n"
    text += f"⭐ Premium foydalanuvchilar: {premium_users}\n\n"
    text += f"📌 Sizning statistikangiz:\n"
    text += f"👥 Referallar: {referrals}\n"
    text += f"🔓 Status: {'Premium' if is_premium else 'Oddiy'}"
    
    await message.answer(text)

# Admin tekshirish
async def is_admin(user_id):
    return user_id in ADMIN_IDS

# Admin menyusi
@dp.message_handler(lambda message: message.text == '🔙 Asosiy menyu')
async def back_to_main(message: types.Message):
    await message.answer("Asosiy menyu:", reply_markup=main_menu())

@dp.message_handler(lambda message: message.text == '📊 Admin statistika')
async def admin_statistics(message: types.Message):
    if not await is_admin(message.from_user.id):
        await message.answer("Siz admin emassiz!")
        return
    
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM users WHERE is_premium = 1")
    premium_users = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM videos")
    total_videos = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM videos WHERE is_premium = 1")
    premium_videos = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM channels")
    total_channels = cursor.fetchone()[0]
    
    text = "📊 Admin statistikasi:\n\n"
    text += f"👥 Jami foydalanuvchilar: {total_users}\n"
    text += f"⭐ Premium foydalanuvchilar: {premium_users}\n"
    text += f"📹 Jami videolar: {total_videos}\n"
    text += f"⭐ Premium videolar: {premium_videos}\n"
    text += f"📺 Majburiy obuna kanallari: {total_channels}"
    
    await message.answer(text, reply_markup=admin_menu())

# Video qo'shish
@dp.message_handler(lambda message: message.text == '📹 Video qo\'shish')
async def add_video_start(message: types.Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        await message.answer("Siz admin emassiz!")
        return
    
    await message.answer("Yangi video yuboring:", reply_markup=types.ReplyKeyboardRemove())
    await AdminStates.add_video.set()

@dp.message_handler(state=AdminStates.add_video, content_types=types.ContentType.VIDEO)
async def add_video_received(message: types.Message, state: FSMContext):
    video_id = message.video.file_id
    await state.update_data(video_id=video_id)
    
    await message.answer("Video uchun sarlavha yozing:")
    await AdminStates.add_video_caption.set()

@dp.message_handler(state=AdminStates.add_video_caption)
async def add_video_caption(message: types.Message, state: FSMContext):
    caption = message.text
    await state.update_data(caption=caption)
    
    await message.answer("Video kategoriyasini yozing:")
    await AdminStates.add_video_category.set()

@dp.message_handler(state=AdminStates.add_video_category)
async def add_video_category(message: types.Message, state: FSMContext):
    category = message.text
    await state.update_data(category=category)
    
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(KeyboardButton('Ha'))
    keyboard.add(KeyboardButton('Yo\'q'))
    
    await message.answer("Bu video premiummi?", reply_markup=keyboard)
    await AdminStates.add_video_premium.set()

@dp.message_handler(state=AdminStates.add_video_premium)
async def add_video_premium(message: types.Message, state: FSMContext):
    if message.text.lower() not in ['ha', 'yo\'q']:
        await message.answer("Iltimos, 'Ha' yoki 'Yo\'q' tugmalaridan birini bosing!")
        return
    
    is_premium = 1 if message.text.lower() == 'ha' else 0
    data = await state.get_data()
    
    cursor.execute("INSERT INTO videos (file_id, caption, category, is_premium) VALUES (?, ?, ?, ?)",
                  (data['video_id'], data['caption'], data['category'], is_premium))
    conn.commit()
    
    await message.answer("Video muvaffaqiyatli qo'shildi!", reply_markup=admin_menu())
    await state.finish()

# Kanal qo'shish
@dp.message_handler(lambda message: message.text == '📺 Kanal qo\'shish')
async def add_channel_start(message: types.Message):
    if not await is_admin(message.from_user.id):
        await message.answer("Siz admin emassiz!")
        return
    
    await message.answer("Yangi kanal ID sini yuboring (masalan, @channelusername):", reply_markup=types.ReplyKeyboardRemove())
    await AdminStates.add_channel.set()

@dp.message_handler(state=AdminStates.add_channel)
async def add_channel_received(message: types.Message, state: FSMContext):
    channel_id = message.text.strip()
    
    try:
        chat = await bot.get_chat(channel_id)
        channel_name = chat.title
        
        cursor.execute("INSERT OR IGNORE INTO channels (channel_id, channel_name) VALUES (?, ?)", (channel_id, channel_name))
        conn.commit()
        
        await message.answer(f"Kanal {channel_name} muvaffaqiyatli qo'shildi!", reply_markup=admin_menu())
        await state.finish()
    except Exception as e:
        await message.answer(f"Xatolik: {e}\nIltimos, to'g'ri kanal ID sini yuboring.")

# Kanal olib tashlash
@dp.message_handler(lambda message: message.text == '🗑 Kanal olib tashlash')
async def remove_channel_start(message: types.Message):
    if not await is_admin(message.from_user.id):
        await message.answer("Siz admin emassiz!")
        return
    
    cursor.execute("SELECT channel_id, channel_name FROM channels")
    channels = cursor.fetchall()
    
    if not channels:
        await message.answer("Hozircha kanallar mavjud emas.", reply_markup=admin_menu())
        return
    
    keyboard = InlineKeyboardMarkup()
    for channel_id, channel_name in channels:
        keyboard.add(InlineKeyboardButton(channel_name, callback_data=f"remove_channel_{channel_id}"))
    
    await message.answer("Olib tashlash uchun kanalni tanlang:", reply_markup=keyboard)

@dp.callback_query_handler(lambda c: c.data.startswith('remove_channel_'))
async def process_remove_channel(callback_query: types.CallbackQuery):
    channel_id = callback_query.data.replace('remove_channel_', '')
    
    cursor.execute("DELETE FROM channels WHERE channel_id = ?", (channel_id,))
    conn.commit()
    
    await bot.answer_callback_query(callback_query.id, "Kanal muvaffaqiyatli o'chirildi!")
    await bot.send_message(callback_query.from_user.id, "Kanal o'chirildi.", reply_markup=admin_menu())





@dp.message_handler(commands=['adminlar'])
async def admin_statistics(message: types.Message):
    await message.answer("Yangi video yuboring:", reply_markup=admin_menu())
# Botni ishga tushurish
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    executor.start_polling(dp, skip_updates=True)