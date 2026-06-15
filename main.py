import os
import sqlite3
import logging
import asyncio
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F, Router
from aiogram.filters import Command, CommandStart, CommandObject
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

# =====================================================================
# 1. SOZLAMALAR (CONFIG)
# =====================================================================
BOT_TOKEN = "8925301984:AAF42KJodNwJCcLiSlFSiHC5I8cqH4nliTI"
ADMIN_IDS = [6222096713]
CHANNEL_ID = "@MovieUpHD"
CHANNEL_USERNAME = "MovieUpHD"  # https://t.me/MovieUpHD - kino qo'shilganda shu kanalga post yuboriladi
BOT_USERNAME = "Movie_Up_bot"
DB_PATH = "movies.db"
GENRES = ["Jangari", "Komediya", "Drama", "Triller", "Qo'rqinchli", "Romantik", "Fantastika", "Josus", "Sarguzasht", "Kriminal"]

logging.basicConfig(level=logging.INFO)

def is_admin(user_id):
    return user_id in ADMIN_IDS or user_id in get_extra_admins()

# =====================================================================
# 2. MA'LUMOTLAR BAZASI (DATABASE LOGIC)
# =====================================================================
def get_conn():
    return sqlite3.connect(DB_PATH)

def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            full_name TEXT,
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS movies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code INTEGER UNIQUE,
            title TEXT,
            year TEXT,
            quality TEXT,
            imdb TEXT,
            country TEXT,
            language TEXT,
            genre TEXT,
            description TEXT,
            poster_file_id TEXT,
            trailer_file_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS episodes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            movie_code INTEGER,
            episode_number INTEGER,
            file_id TEXT,
            FOREIGN KEY (movie_code) REFERENCES movies(code)
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS required_channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id TEXT UNIQUE,
            channel_name TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            user_id INTEGER PRIMARY KEY
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            movie_code INTEGER,
            user_id INTEGER,
            rating INTEGER,
            comment TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def add_user(user_id, username, full_name):
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, username, full_name) VALUES (?, ?, ?)", (user_id, username, full_name))
    conn.commit()
    conn.close()

def get_users_count():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users")
    count = c.fetchone()[0]
    conn.close()
    return count

def get_all_user_ids():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT user_id FROM users")
    rows = c.fetchall()
    conn.close()
    return [r[0] for r in rows]

def add_required_channel(channel_id, channel_name):
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO required_channels (channel_id, channel_name) VALUES (?, ?)", (channel_id, channel_name))
    conn.commit()
    conn.close()

def remove_required_channel(channel_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM required_channels WHERE channel_id = ?", (channel_id,))
    conn.commit()
    conn.close()

def get_required_channels():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT channel_id, channel_name FROM required_channels")
    rows = c.fetchall()
    conn.close()
    return rows

def add_movie(code, title, year, quality, imdb, country, language, genre, description, poster, trailer):
    conn = get_conn()
    c = conn.cursor()
    try:
        c.execute("""INSERT INTO movies (code, title, year, quality, imdb, country, language, genre, description, poster_file_id, trailer_file_id)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                  (code, title, year, quality, imdb, country, language, genre, description, poster, trailer))
        conn.commit()
        success = True
    except sqlite3.IntegrityError:
        success = False
    conn.close()
    return success

def get_movie_by_code(code):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM movies WHERE code = ?", (code,))
    row = c.fetchone()
    conn.close()
    return row

def update_movie_field(code, field, value):
    conn = get_conn()
    c = conn.cursor()
    c.execute(f"UPDATE movies SET {field} = ? WHERE code = ?", (value, code))
    conn.commit()
    conn.close()

def delete_movie_by_code(code):
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM movies WHERE code = ?", (code,))
    c.execute("DELETE FROM episodes WHERE movie_code = ?", (code,))
    c.execute("DELETE FROM comments WHERE movie_code = ?", (code,))
    conn.commit()
    conn.close()

def add_episode(movie_code, ep_num, file_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT INTO episodes (movie_code, episode_number, file_id) VALUES (?, ?, ?)", (movie_code, ep_num, file_id))
    conn.commit()
    conn.close()

def get_episodes(movie_code):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT episode_number, file_id FROM episodes WHERE movie_code = ? ORDER BY episode_number ASC", (movie_code,))
    rows = c.fetchall()
    conn.close()
    return rows

def search_movies_by_title(query):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT code, title, year FROM movies WHERE title LIKE ?", (f"%{query}%",))
    rows = c.fetchall()
    conn.close()
    return rows

def add_comment(movie_code, user_id, rating, comment):
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT INTO comments (movie_code, user_id, rating, comment) VALUES (?, ?, ?, ?)", (movie_code, user_id, rating, comment))
    conn.commit()
    conn.close()

def get_comments(movie_code):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""SELECT users.full_name, comments.rating, comments.comment, comments.created_at 
                 FROM comments JOIN users ON comments.user_id = users.user_id 
                 WHERE comments.movie_code = ? ORDER BY comments.created_at DESC""", (movie_code,))
    rows = c.fetchall()
    conn.close()
    return rows

def get_average_rating(movie_code):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT AVG(rating) FROM comments WHERE movie_code = ?", (movie_code,))
    res = c.fetchone()[0]
    conn.close()
    return round(res, 1) if res else "Baholanmagan"

def get_all_movies():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT code, title, year FROM movies ORDER BY code ASC")
    rows = c.fetchall()
    conn.close()
    return rows

def add_admin(user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (user_id,))
    conn.commit()
    conn.close()

def remove_admin(user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM admins WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def get_extra_admins():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT user_id FROM admins")
    rows = c.fetchall()
    conn.close()
    return [r[0] for r in rows]

# =====================================================================
# 3. STATES TIZIMI (FSM STATES)
# =====================================================================
class AddMovie(StatesGroup):
    code = State()
    title = State()
    year = State()
    quality = State()
    imdb = State()
    country = State()
    language = State()
    genre = State()
    description = State()
    poster = State()
    trailer = State()

class AddEpisode(StatesGroup):
    movie_code = State()
    episode = State()
    file_id = State()

class EditMovie(StatesGroup):
    code = State()
    field = State()
    value = State()

class DeleteMovie(StatesGroup):
    code = State()

class Broadcast(StatesGroup):
    message = State()

class AddChannel(StatesGroup):
    channel_id = State()
    channel_name = State()

class RemoveChannel(StatesGroup):
    channel_id = State()

class AddAdmin(StatesGroup):
    user_id = State()

class RemoveAdmin(StatesGroup):
    user_id = State()

class SearchState(StatesGroup):
    query = State()

class CommentState(StatesGroup):
    movie_code = State()
    rating = State()
    comment = State()

# Routers
admin_router = Router()
user_router = Router()

# =====================================================================
# 4. ADMIN KEYBOARDS & HANDLERS
# =====================================================================
def admin_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Kino qo'shish", callback_data="add_movie"),
         InlineKeyboardButton(text="➕ Qism qo'shish", callback_data="add_episode")],
        [InlineKeyboardButton(text="📝 Kinoni tahrirlash", callback_data="edit_movie"),
         InlineKeyboardButton(text="🗑 Kinoni o'chirish", callback_data="delete_movie")],
        [InlineKeyboardButton(text="📢 Majburiy Obuna", callback_data="sub_channels"),
         InlineKeyboardButton(text="📊 Stat & Reklama", callback_data="admin_stats")],
        [InlineKeyboardButton(text="👮 Adminlar", callback_data="admins_menu")],
    ])

def cancel_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="back_to_admin")]
    ])

def movies_list_text():
    movies = get_all_movies()
    if not movies:
        return "📭 Hozircha botda kinolar mavjud emas."
    text = "🎬 <b>Botdagi mavjud kinolar:</b>\n\n"
    for code, title, year in movies:
        text += f"🔑 <code>{code}</code> — {title} ({year})\n"
    return text

def build_movie_caption(data, code):
    return (
        f"🎬 <b>{data['title']} ({data['year']})</b>\n\n"
        f"🌍 Davlat: {data['country']}\n"
        f"🗣 Til: {data['language']}\n"
        f"🎭 Janr: {data['genre']}\n"
        f"💾 Sifat: {data['quality']}\n"
        f"⭐ IMDb: {data['imdb']}\n\n"
        f"📝 <b>Tavsif:</b> {data['description']}\n\n"
        f"‼️ Filmni tomosha qilish uchun @{BOT_USERNAME} ga «{code}» kodini yuboring!\n\n"
        f"🔑 <b>FILM KODI:</b> <code>{code}</code>"
    )

@admin_router.message(Command("admin"), F.from_user.id.in_(ADMIN_IDS))
async def admin_panel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("🛠 Admin panelga xush kelibsiz! Kerakli bo'limni tanlang:", reply_markup=admin_menu())

@admin_router.callback_query(F.data == "back_to_admin")
async def back_to_admin(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    await state.clear()
    await call.message.edit_text("🛠 Admin panelga xush kelibsiz! Kerakli bo'limni tanlang:", reply_markup=admin_menu())

# --- Stat va Reklama ---
@admin_router.callback_query(F.data == "admin_stats")
async def admin_stats(call: CallbackQuery):
    if not is_admin(call.from_user.id): return
    count = get_users_count()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Xabar tarqatish (Reklama)", callback_data="broadcast")],
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back_to_admin")]
    ])
    await call.message.edit_text(f"📊 <b>Bot Statistikasi:</b>\n\n👥 Jami foydalanuvchilar: {count} ta", parse_mode="HTML", reply_markup=kb)

@admin_router.callback_query(F.data == "broadcast")
async def start_broadcast(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    await call.message.edit_text("📝 Reklama xabarini yuboring (Matn, rasm, video bo'lishi mumkin):", reply_markup=cancel_kb())
    await state.set_state(Broadcast.message)

@admin_router.message(Broadcast.message, F.from_user.id.in_(ADMIN_IDS))
async def process_broadcast(message: Message, state: FSMContext, bot: Bot):
    await state.clear()
    user_ids = get_all_user_ids()
    await message.answer(f"🚀 Xabar {len(user_ids)} ta foydalanuvchiga yuborilmoqda...")
    
    sent, failed = 0, 0
    for u_id in user_ids:
        try:
            await bot.copy_message(chat_id=u_id, from_chat_id=message.chat.id, message_id=message.message_id)
            sent += 1
            await asyncio.sleep(0.05)
        except:
            failed += 1
    await message.answer(f"✅ Reklama yakunlandi!\n\n👍 Yetkazildi: {sent}\n👎 Muammo bo'ldi: {failed}")

# --- Majburiy Obuna Kanallari ---
@admin_router.callback_query(F.data == "sub_channels")
async def sub_channels_menu(call: CallbackQuery):
    if not is_admin(call.from_user.id): return
    channels = get_required_channels()
    text = "📢 <b>Majburiy obuna kanallari ro'yxati:</b>\n\n"
    if not channels:
         text += "📭 Kanallar qo'shilmagan."
    else:
        for ch_id, ch_name in channels:
            text += f"🔹 {ch_name} ({ch_id})\n"
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Kanal qo'shish", callback_data="add_sub_channel")],
        [InlineKeyboardButton(text="🗑 Kanalni o'chirish", callback_data="remove_sub_channel")],
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back_to_admin")]
    ])
    await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")

@admin_router.callback_query(F.data == "add_sub_channel")
async def add_sub_channel(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    await call.message.edit_text("📢 Kanal username ini kiriting (masalan: @MyChannel):", reply_markup=cancel_kb())
    await state.set_state(AddChannel.channel_id)

@admin_router.message(AddChannel.channel_id, F.from_user.id.in_(ADMIN_IDS))
async def get_sub_channel_id(message: Message, state: FSMContext):
    await state.update_data(channel_id=message.text.strip())
    await message.answer("📝 Kanal nomini kiriting:")
    await state.set_state(AddChannel.channel_name)

@admin_router.message(AddChannel.channel_name, F.from_user.id.in_(ADMIN_IDS))
async def get_sub_channel_name(message: Message, state: FSMContext):
    data = await state.get_data()
    add_required_channel(data["channel_id"], message.text.strip())
    await state.clear()
    await message.answer("✅ Kanal qo'shildi!", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Orqaga", callback_data="sub_channels")]]))

@admin_router.callback_query(F.data == "remove_sub_channel")
async def remove_sub_channel(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    await call.message.edit_text("📢 O'chirish uchun kanal username ini kiriting (masalan: @MyChannel):", reply_markup=cancel_kb())
    await state.set_state(RemoveChannel.channel_id)

@admin_router.message(RemoveChannel.channel_id, F.from_user.id.in_(ADMIN_IDS))
async def process_remove_channel(message: Message, state: FSMContext):
    remove_required_channel(message.text.strip())
    await state.clear()
    await message.answer("✅ Kanal o'chirildi!", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Orqaga", callback_data="sub_channels")]]))

# --- Kino Qo'shish Ketma-ketligi (FSM) ---
@admin_router.callback_query(F.data == "add_movie")
async def cb_add_movie(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    await call.message.edit_text("🔢 Kino uchun noyob kod (raqam) kiriting:", reply_markup=cancel_kb())
    await state.set_state(AddMovie.code)

@admin_router.message(AddMovie.code, F.from_user.id.in_(ADMIN_IDS))
async def m_code(message: Message, state: FSMContext):
    if not message.text.isdigit():
        return await message.answer("❌ Iltimos, faqat raqam kiriting:")
    await state.update_data(code=int(message.text))
    await message.answer("🎬 Kino nomini kiriting:", reply_markup=cancel_kb())
    await state.set_state(AddMovie.title)

@admin_router.message(AddMovie.title, F.from_user.id.in_(ADMIN_IDS))
async def m_title(message: Message, state: FSMContext):
    await state.update_data(title=message.text)
    await message.answer("📅 Chiqqan yilini kiriting (masalan: 2024):", reply_markup=cancel_kb())
    await state.set_state(AddMovie.year)

@admin_router.message(AddMovie.year, F.from_user.id.in_(ADMIN_IDS))
async def m_year(message: Message, state: FSMContext):
    await state.update_data(year=message.text)
    await message.answer("💾 Sifatini kiriting (masalan: HD, 1080p):", reply_markup=cancel_kb())
    await state.set_state(AddMovie.quality)

@admin_router.message(AddMovie.quality, F.from_user.id.in_(ADMIN_IDS))
async def m_quality(message: Message, state: FSMContext):
    await state.update_data(quality=message.text)
    await message.answer("⭐ IMDb reytingini kiriting (masalan: 8.5):", reply_markup=cancel_kb())
    await state.set_state(AddMovie.imdb)

@admin_router.message(AddMovie.imdb, F.from_user.id.in_(ADMIN_IDS))
async def m_imdb(message: Message, state: FSMContext):
    await state.update_data(imdb=message.text)
    await message.answer("🌍 Ishlab chiqarilgan davlatni kiriting:", reply_markup=cancel_kb())
    await state.set_state(AddMovie.country)

@admin_router.message(AddMovie.country, F.from_user.id.in_(ADMIN_IDS))
async def m_country(message: Message, state: FSMContext):
    await state.update_data(country=message.text)
    await message.answer("🗣 Tilini kiriting (masalan: O'zbekcha):", reply_markup=cancel_kb())
    await state.set_state(AddMovie.language)

@admin_router.message(AddMovie.language, F.from_user.id.in_(ADMIN_IDS))
async def m_lang(message: Message, state: FSMContext):
    await state.update_data(language=message.text)
    buttons = [[InlineKeyboardButton(text=g, callback_data=f"g_{g}")] for g in GENRES]
    buttons.append([InlineKeyboardButton(text="❌ Bekor qilish", callback_data="back_to_admin")])
    await message.answer("🎭 Janrini tanlang:", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await state.set_state(AddMovie.genre)

@admin_router.callback_query(F.data.startswith("g_"), AddMovie.genre)
async def m_genre(call: CallbackQuery, state: FSMContext):
    genre = call.data.split("_")[1]
    await state.update_data(genre=genre)
    await call.message.edit_text("📝 Kino haqida qisqacha tavsif (tavsif matni) kiriting:", reply_markup=cancel_kb())
    await state.set_state(AddMovie.description)

@admin_router.message(AddMovie.description, F.from_user.id.in_(ADMIN_IDS))
async def m_desc(message: Message, state: FSMContext):
    await state.update_data(description=message.text)
    await message.answer("🖼 Kino posterini (Rasm) yuboring:", reply_markup=cancel_kb())
    await state.set_state(AddMovie.poster)

@admin_router.message(AddMovie.poster, F.photo, F.from_user.id.in_(ADMIN_IDS))
async def m_poster(message: Message, state: FSMContext):
    await state.update_data(poster=message.photo[-1].file_id)
    await message.answer("📹 Kino videosini yoki Treylerini yuboring:", reply_markup=cancel_kb())
    await state.set_state(AddMovie.trailer)

@admin_router.message(AddMovie.trailer, F.video, F.from_user.id.in_(ADMIN_IDS))
async def m_trailer(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    trailer_id = message.video.file_id
    
    success = add_movie(
        data['code'], data['title'], data['year'], data['quality'], data['imdb'],
        data['country'], data['language'], data['genre'], data['description'], data['poster'], trailer_id
    )
    await state.clear()
    if success:
        await message.answer(f"✅ Kino muvaffaqiyatli qo'shildi!\n🔑 Kod: <code>{data['code']}</code>", parse_mode="HTML", reply_markup=admin_menu())
        # Kanalga avtomatik post yuborish
        try:
            code = data['code']
            caption = build_movie_caption(data, code)
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=f"🎬 {code} kodini olish", url=f"https://t.me/{BOT_USERNAME}?start=film_{code}")]
            ])
            await bot.send_photo(chat_id=CHANNEL_ID, photo=data['poster'], caption=caption, parse_mode="HTML", reply_markup=kb)
        except Exception as e:
            logging.warning(f"Kanalga post yuborishda xatolik: {e}")
            await message.answer(f"⚠️ Kanalga avtomatik post yuborilmadi: {e}")
    else:
        await message.answer("❌ Bu kodli kino allaqachon mavjud!", reply_markup=admin_menu())

# --- Qism (Seriya) Qo'shish ---
@admin_router.callback_query(F.data == "add_episode")
async def cb_add_ep(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    text = "🔢 Qism qo'shiladigan kino kodini kiriting:\n\n" + movies_list_text()
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=cancel_kb())
    await state.set_state(AddEpisode.movie_code)

@admin_router.message(AddEpisode.movie_code, F.from_user.id.in_(ADMIN_IDS))
async def m_ep_code(message: Message, state: FSMContext):
    if not message.text.isdigit(): return await message.answer("Faqat raqam kiriting:", reply_markup=cancel_kb())
    code = int(message.text)
    if not get_movie_by_code(code): return await message.answer("❌ Bunday kodli kino topilmadi. Qaytadan kiriting:", reply_markup=cancel_kb())
    await state.update_data(movie_code=code)
    await message.answer("🔢 Qism raqamini kiriting (masalan: 1):", reply_markup=cancel_kb())
    await state.set_state(AddEpisode.episode)

@admin_router.message(AddEpisode.episode, F.from_user.id.in_(ADMIN_IDS))
async def m_ep_num(message: Message, state: FSMContext):
    if not message.text.isdigit(): return await message.answer("Faqat raqam kiriting:", reply_markup=cancel_kb())
    await state.update_data(episode=int(message.text))
    await message.answer("📹 Ushbu qism videosini yuboring:", reply_markup=cancel_kb())
    await state.set_state(AddEpisode.file_id)

@admin_router.message(AddEpisode.file_id, F.video, F.from_user.id.in_(ADMIN_IDS))
async def m_ep_file(message: Message, state: FSMContext):
    data = await state.get_data()
    add_episode(data["movie_code"], data["episode"], message.video.file_id)
    await state.clear()
    await message.answer(f"✅ {data['movie_code']} kodli kinoga {data['episode']}-qism qo'shildi!", reply_markup=admin_menu())

# --- O'chirish va Tahrirlash ---
@admin_router.callback_query(F.data == "delete_movie")
async def cb_del_movie(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    text = "🗑 O'chiriladigan kino kodini kiriting:\n\n" + movies_list_text()
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=cancel_kb())
    await state.set_state(DeleteMovie.code)

@admin_router.message(DeleteMovie.code, F.from_user.id.in_(ADMIN_IDS))
async def m_del_code(message: Message, state: FSMContext):
    if not message.text.isdigit(): return await message.answer("Faqat raqam!", reply_markup=cancel_kb())
    code = int(message.text)
    if get_movie_by_code(code):
        delete_movie_by_code(code)
        await message.answer(f"✅ Kod {code} bo'lgan kino o'chirildi.", reply_markup=admin_menu())
    else:
        await message.answer("❌ Topilmadi.", reply_markup=admin_menu())
    await state.clear()

@admin_router.callback_query(F.data == "edit_movie")
async def cb_edit_movie(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    text = "📝 Tahrirlanadigan kino kodini kiriting:\n\n" + movies_list_text()
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=cancel_kb())
    await state.set_state(EditMovie.code)

@admin_router.message(EditMovie.code, F.from_user.id.in_(ADMIN_IDS))
async def m_edit_code(message: Message, state: FSMContext):
    if not message.text.isdigit(): return await message.answer("Faqat raqam!", reply_markup=cancel_kb())
    code = int(message.text)
    if not get_movie_by_code(code): return await message.answer("Topilmadi. Qaytadan kiriting:", reply_markup=cancel_kb())
    await state.update_data(code=code)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Nomini tahrirlash", callback_data="field_title")],
        [InlineKeyboardButton(text="Tavsifni tahrirlash", callback_data="field_description")],
        [InlineKeyboardButton(text="IMDb ni tahrirlash", callback_data="field_imdb")],
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="back_to_admin")]
    ])
    await message.answer("Qaysi maydonni o'zgartirasiz?", reply_markup=kb)
    await state.set_state(EditMovie.field)

@admin_router.callback_query(F.data.startswith("field_"), EditMovie.field)
async def cb_edit_field(call: CallbackQuery, state: FSMContext):
    field = call.data.split("_")[1]
    await state.update_data(field=field)
    await call.message.edit_text(f"📝 Yangi qiymatni yuboring:", reply_markup=cancel_kb())
    await state.set_state(EditMovie.value)

@admin_router.message(EditMovie.value, F.from_user.id.in_(ADMIN_IDS))
async def m_edit_value(message: Message, state: FSMContext):
    data = await state.get_data()
    update_movie_field(data["code"], data["field"], message.text)
    await state.clear()
    await message.answer("✅ Muvaffaqiyatli tahrirlandi!", reply_markup=admin_menu())

# --- Adminlar Boshqaruvi ---
@admin_router.callback_query(F.data == "admins_menu")
async def admins_menu(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    await state.clear()
    extra = get_extra_admins()
    text = "👮 <b>Adminlar ro'yxati:</b>\n\n"
    text += "🔹 <b>Asosiy adminlar:</b>\n"
    for uid in ADMIN_IDS:
        text += f"<code>{uid}</code>\n"
    text += "\n🔹 <b>Qo'shilgan adminlar:</b>\n"
    if extra:
        for uid in extra:
            text += f"<code>{uid}</code>\n"
    else:
        text += "Yo'q\n"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Admin qo'shish", callback_data="add_admin")],
        [InlineKeyboardButton(text="➖ Admin o'chirish", callback_data="remove_admin")],
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back_to_admin")]
    ])
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=kb)

@admin_router.callback_query(F.data == "add_admin")
async def cb_add_admin(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    await call.message.edit_text("➕ Yangi admin qilib tayinlash uchun foydalanuvchining Telegram ID raqamini yuboring:", reply_markup=cancel_kb())
    await state.set_state(AddAdmin.user_id)

@admin_router.message(AddAdmin.user_id, F.from_user.id.in_(ADMIN_IDS))
async def process_add_admin(message: Message, state: FSMContext):
    if not message.text.strip().lstrip("-").isdigit():
        return await message.answer("❌ Faqat ID raqam yuboring:", reply_markup=cancel_kb())
    new_id = int(message.text.strip())
    add_admin(new_id)
    await state.clear()
    await message.answer(f"✅ <code>{new_id}</code> endi admin sifatida tayinlandi!", parse_mode="HTML", reply_markup=admin_menu())

@admin_router.callback_query(F.data == "remove_admin")
async def cb_remove_admin(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    await call.message.edit_text("➖ Adminlikdan olib tashlash uchun foydalanuvchining Telegram ID raqamini yuboring:", reply_markup=cancel_kb())
    await state.set_state(RemoveAdmin.user_id)

@admin_router.message(RemoveAdmin.user_id, F.from_user.id.in_(ADMIN_IDS))
async def process_remove_admin(message: Message, state: FSMContext):
    if not message.text.strip().lstrip("-").isdigit():
        return await message.answer("❌ Faqat ID raqam yuboring:", reply_markup=cancel_kb())
    rem_id = int(message.text.strip())
    if rem_id in ADMIN_IDS:
        await state.clear()
        return await message.answer("❌ Asosiy adminni o'chirib bo'lmaydi!", reply_markup=admin_menu())
    remove_admin(rem_id)
    await state.clear()
    await message.answer(f"✅ <code>{rem_id}</code> adminlikdan olib tashlandi!", parse_mode="HTML", reply_markup=admin_menu())


# =====================================================================
# 5. USER HANDLERS & LOGIC
# =====================================================================
async def check_subscription(bot: Bot, user_id: int):
    channels = get_required_channels()
    not_subscribed = []
    for ch_id, ch_name in channels:
        try:
            member = await bot.get_chat_member(ch_id, user_id)
            if member.status in ["left", "kicked", "banned"]:
                not_subscribed.append((ch_id, ch_name))
        except:
            not_subscribed.append((ch_id, ch_name))
    return not_subscribed

async def subscription_warning(message: Message, not_subscribed):
    buttons = []
    for ch_id, ch_name in not_subscribed:
        url = f"https://t.me/{ch_id.lstrip('@')}"
        buttons.append([InlineKeyboardButton(text=f"📢 {ch_name}", url=url)])
    buttons.append([InlineKeyboardButton(text="✅ Tekshirish", callback_data="check_sub")])
    await message.answer("❌ <b>Botdan foydalanish uchun quyidagi kanallarga a'zo bo'ling:</b>", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

@user_router.message(CommandStart())
async def send_welcome(message: Message, bot: Bot, state: FSMContext, command: CommandObject):
    await state.clear()
    add_user(message.from_user.id, message.from_user.username, message.from_user.full_name)
    not_sub = await check_subscription(bot, message.from_user.id)
    if not_sub:
        return await subscription_warning(message, not_sub)

    # Kanaldagi "kodni olish" tugmasi orqali kelgan deep-link: /start film_123
    arg = command.args
    if arg and arg.startswith("film_") and arg.split("_", 1)[1].isdigit():
        code = int(arg.split("_", 1)[1])
        return await send_movie_by_code(message, bot, code)

    await message.answer(
        f"<b>Salom, {message.from_user.full_name}! 👋</b>\n\n"
        f"Kinolar botiga xush kelibsiz. Film ko'rish uchun uning <b>kodini</b> yuboring yoki /search buyrug'idan foydalaning.",
        parse_mode="HTML"
    )

@user_router.callback_query(F.data == "check_sub")
async def cb_check_sub(call: CallbackQuery, bot: Bot):
    not_sub = await check_subscription(bot, call.from_user.id)
    if not_sub:
        await call.answer("❌ Hali hamma kanallarga a'zo bo'lmadingiz!", show_alert=True)
    else:
        await call.message.delete()
        await call.message.answer("🎉 Rahmat! Obuna tasdiqlandi. Endi botdan bemalol foydalanishingiz mumkin. Kino kodini yuboring:")

@user_router.message(Command("search"))
async def cmd_search(message: Message, state: FSMContext, bot: Bot):
    await state.clear()
    not_sub = await check_subscription(bot, message.from_user.id)
    if not_sub: return await subscription_warning(message, not_sub)
    await message.answer("🔍 Qidirayotgan kino nomini kiriting:")
    await state.set_state(SearchState.query)

@user_router.message(SearchState.query)
async def process_search(message: Message, state: FSMContext):
    await state.clear()
    results = search_movies_by_title(message.text)
    if not results:
        return await message.answer("❌ Hech narsa topilmadi.")
    
    text = "🔍 <b>Topilgan kinolar:</b>\n\n"
    for code, title, year in results:
        text += f"🔑 Kod: <code>{code}</code> | 🎬 {title} ({year})\n"
    await message.answer(text, parse_mode="HTML")

# --- Kod Orqali Kino Berish ---
async def send_movie_by_code(message: Message, bot: Bot, code: int):
    movie = get_movie_by_code(code)
    if not movie:
        return await message.answer("❌ Afsuski, bunday kodli kino topilmadi.")
    
    # movie: (id, code, title, year, quality, imdb, country, language, genre, description, poster, trailer, ...)
    avg_rating = get_average_rating(code)
    caption = (
        f"🎬 <b>{movie[2]} ({movie[3]})</b>\n\n"
        f"🌍 Davlat: {movie[6]}\n"
        f"🗣 Til: {movie[7]}\n"
        f"🎭 Janr: {movie[8]}\n"
        f"💾 Sifat: {movie[4]}\n"
        f"⭐ IMDb: {movie[5]}\n"
        f"📊 Bot Reytingi: {avg_rating}\n\n"
        f"📝 <b>Tavsif:</b> {movie[9]}\n\n"
        f"🔑 Kod: <code>{code}</code>"
    )
    
    episodes = get_episodes(code)
    kb_list = []
    if episodes:
        # Serial bo'lsa qismlar tugmalari
        row = []
        for ep_num, _ in episodes:
            row.append(InlineKeyboardButton(text=f"{ep_num}-Qism", callback_data=f"ep_{code}_{ep_num}"))
            if len(row) == 3:
                kb_list.append(row)
                row = []
        if row: kb_list.append(row)
    else:
        # Yagona film bo'lsa
        kb_list.append([InlineKeyboardButton(text="📹 Kinoni ko'rish", callback_data=f"watch_{code}")])
        
    kb_list.append([
        InlineKeyboardButton(text="⭐ Baholash", callback_data=f"rate_{code}"),
        InlineKeyboardButton(text="💬 Izohlar", callback_data=f"ratings_{code}")
    ])
    
    await bot.send_photo(chat_id=message.chat.id, photo=movie[10], caption=caption, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_list))

@user_router.message(F.text.regexp(r'^\d+$'))
async def get_movie_handler(message: Message, bot: Bot):
    not_sub = await check_subscription(bot, message.from_user.id)
    if not_sub: return await subscription_warning(message, not_sub)
    
    code = int(message.text.strip())
    await send_movie_by_code(message, bot, code)

@user_router.callback_query(F.data.startswith("watch_"))
async def watch_single_movie(call: CallbackQuery, bot: Bot):
    code = int(call.data.split("_")[1])
    movie = get_movie_by_code(code)
    if movie:
        await bot.send_chat_action(chat_id=call.message.chat.id, action="upload_video")
        await bot.send_video(chat_id=call.message.chat.id, video=movie[11], caption=f"🎬 {movie[2]} (Treyler/Kino)")
        await call.answer()

@user_router.callback_query(F.data.startswith("ep_"))
async def watch_episode(call: CallbackQuery, bot: Bot):
    _, code, ep_num = call.data.split("_")
    code, ep_num = int(code), int(ep_num)
    episodes = get_episodes(code)
    file_id = None
    for num, fid in episodes:
        if num == ep_num:
            file_id = fid
            break
    if file_id:
        await bot.send_chat_action(chat_id=call.message.chat.id, action="upload_video")
        await bot.send_video(chat_id=call.message.chat.id, video=file_id, caption=f"🍿 Kino kodi: {code} | {ep_num}-Qism")
    await call.answer()

# --- Izohlar va Baholash Tizimi ---
@user_router.callback_query(F.data.startswith("rate_"))
async def rate_movie_start(call: CallbackQuery, state: FSMContext):
    code = int(call.data.split("_")[1])
    await state.update_data(movie_code=code)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⭐ 1", callback_data="score_1"),
         InlineKeyboardButton(text="⭐ 2", callback_data="score_2"),
         InlineKeyboardButton(text="⭐ 3", callback_data="score_3"),
         InlineKeyboardButton(text="⭐ 4", callback_data="score_4"),
         InlineKeyboardButton(text="⭐ 5", callback_data="score_5")],
    ])
    await call.message.answer("⭐ Kinoni baholang (1 dan 5 gacha):", reply_markup=kb)
    await state.set_state(CommentState.rating)

@user_router.callback_query(F.data.startswith("score_"), CommentState.rating)
async def rate_movie_score(call: CallbackQuery, state: FSMContext):
    rating = int(call.data.split("_")[1])
    await state.update_data(rating=rating)
    await call.message.edit_text(f"⭐ {rating} ball berdingiz! Endi kino haqida fikringizni (izoh) yozib yuboring:")
    await state.set_state(CommentState.comment)

@user_router.message(CommentState.comment)
async def save_movie_comment(message: Message, state: FSMContext):
    data = await state.get_data()
    add_comment(data["movie_code"], message.from_user.id, data["rating"], message.text.strip())
    await state.clear()
    await message.answer("✅ Izohingiz va bahongiz muvaffaqiyatli saqlandi! Rahmat.")

@user_router.callback_query(F.data.startswith("ratings_"))
async def show_movie_comments(call: CallbackQuery):
    code = int(call.data.split("_")[1])
    comments = get_comments(code)
    if not comments:
        return await call.answer("Hozircha izohlar yo'q.", show_alert=True)
    
    text = f"💬 <b>Kino ({code}) uchun qoldirilgan oxirgi izohlar:</b>\n\n"
    for name, rating, comment, date in comments[:5]: # Oxirgi 5 tasini chiqarish
        text += f"👤 {name} | ⭐ {rating}/5\n💬 <i>{comment}</i>\n🕒 {date}\n\n"
    await call.message.answer(text, parse_mode="HTML")
    await call.answer()

@user_router.message(F.text)
async def text_handler(message: Message):
    await message.answer("🔢 Iltimos, kino ko'rish uchun uning kodini faqat raqam ko'rinishida yuboring.")

# =====================================================================
# 6. MAIN - ISHGA TUSHIRISH
# =====================================================================
async def main():
    init_db()  # Ma'lumotlar bazasini yaratish/tekshirish
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    dp.include_router(admin_router)
    dp.include_router(user_router)

    print("✅ Barcha funksiyalarga ega super bot muvaffaqiyatli ishga tushdi!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
