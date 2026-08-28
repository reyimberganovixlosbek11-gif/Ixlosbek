import os
import sqlite3
import shutil
import logging
import asyncio
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F, Router
from aiogram.filters import Command, CommandStart, CommandObject
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, FSInputFile

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

def is_super_admin(user_id):
    return user_id in ADMIN_IDS

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
            views INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    try:
        c.execute("ALTER TABLE movies ADD COLUMN views INTEGER DEFAULT 0")
        conn.commit()
    except sqlite3.OperationalError:
        pass
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
    c.execute("""
        CREATE TABLE IF NOT EXISTS favorites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            movie_code INTEGER,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, movie_code)
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

def update_episode_file(movie_code, ep_num, file_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE episodes SET file_id = ? WHERE movie_code = ? AND episode_number = ?", (file_id, movie_code, ep_num))
    conn.commit()
    conn.close()

def update_episode_number(movie_code, old_num, new_num):
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE episodes SET episode_number = ? WHERE movie_code = ? AND episode_number = ?", (new_num, movie_code, old_num))
    conn.commit()
    conn.close()

def delete_episode(movie_code, ep_num):
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM episodes WHERE movie_code = ? AND episode_number = ?", (movie_code, ep_num))
    conn.commit()
    conn.close()

def episode_exists(movie_code, ep_num):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT 1 FROM episodes WHERE movie_code = ? AND episode_number = ?", (movie_code, ep_num))
    row = c.fetchone()
    conn.close()
    return row is not None

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

def get_distinct_countries():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT DISTINCT country FROM movies WHERE country IS NOT NULL AND country != '' ORDER BY country ASC")
    rows = c.fetchall()
    conn.close()
    return [r[0] for r in rows]

def get_distinct_years():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT DISTINCT year FROM movies WHERE year IS NOT NULL AND year != '' ORDER BY year DESC")
    rows = c.fetchall()
    conn.close()
    return [r[0] for r in rows]

def search_movies_by_genre(genre):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT code, title, year FROM movies WHERE genre LIKE ? ORDER BY code ASC", (f"%{genre}%",))
    rows = c.fetchall()
    conn.close()
    return rows

def search_movies_by_country(country):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT code, title, year FROM movies WHERE country = ? ORDER BY code ASC", (country,))
    rows = c.fetchall()
    conn.close()
    return rows

def search_movies_by_year(year):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT code, title, year FROM movies WHERE year = ? ORDER BY code ASC", (year,))
    rows = c.fetchall()
    conn.close()
    return rows

def get_top_rated_movies(limit=10):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""SELECT movies.code, movies.title, movies.year, AVG(comments.rating) as avg_r
                 FROM movies JOIN comments ON movies.code = comments.movie_code
                 GROUP BY movies.code ORDER BY avg_r DESC LIMIT ?""", (limit,))
    rows = c.fetchall()
    conn.close()
    return rows

def get_movies_without_episodes():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""SELECT code, title, year FROM movies 
                 WHERE code NOT IN (SELECT DISTINCT movie_code FROM episodes) ORDER BY code ASC""")
    rows = c.fetchall()
    conn.close()
    return rows

def get_movies_with_episodes():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""SELECT code, title, year FROM movies 
                 WHERE code IN (SELECT DISTINCT movie_code FROM episodes) ORDER BY code ASC""")
    rows = c.fetchall()
    conn.close()
    return rows

def add_favorite(user_id, movie_code):
    conn = get_conn()
    c = conn.cursor()
    try:
        c.execute("INSERT INTO favorites (user_id, movie_code) VALUES (?, ?)", (user_id, movie_code))
        conn.commit()
        success = True
    except sqlite3.IntegrityError:
        success = False
    conn.close()
    return success

def remove_favorite(user_id, movie_code):
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM favorites WHERE user_id = ? AND movie_code = ?", (user_id, movie_code))
    conn.commit()
    conn.close()

def is_favorite(user_id, movie_code):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT 1 FROM favorites WHERE user_id = ? AND movie_code = ?", (user_id, movie_code))
    row = c.fetchone()
    conn.close()
    return row is not None

def get_user_favorites(user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""SELECT movies.code, movies.title, movies.year FROM favorites
                 JOIN movies ON favorites.movie_code = movies.code
                 WHERE favorites.user_id = ? ORDER BY favorites.added_at DESC""", (user_id,))
    rows = c.fetchall()
    conn.close()
    return rows

def increment_views(code):
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE movies SET views = COALESCE(views, 0) + 1 WHERE code = ?", (code,))
    conn.commit()
    conn.close()

def get_total_views():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT COALESCE(SUM(views), 0) FROM movies")
    total = c.fetchone()[0]
    conn.close()
    return total

def get_new_users_today():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users WHERE date(joined_at) = date('now')")
    count = c.fetchone()[0]
    conn.close()
    return count

def get_total_episodes():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM episodes")
    count = c.fetchone()[0]
    conn.close()
    return count

def get_total_movies():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM movies")
    count = c.fetchone()[0]
    conn.close()
    return count

def get_user_join_date(user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT joined_at FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

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
    info = State()
    poster = State()

class AddEpisode(StatesGroup):
    movie_code = State()
    episode = State()
    file_id = State()

class EditMovie(StatesGroup):
    code = State()
    field = State()
    value = State()
    poster = State()

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

class MoviesListSearch(StatesGroup):
    query = State()

class PostToChannel(StatesGroup):
    content = State()

class ManageEpisodes(StatesGroup):
    movie_code = State()
    new_number = State()
    new_video = State()

class BackupRestore(StatesGroup):
    file = State()

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
def admin_menu(user_id=None):
    base = [
        [InlineKeyboardButton(text="➕ Kino Qo'shish", callback_data="add_movie"),
         InlineKeyboardButton(text="📺 Qism Qo'shish", callback_data="add_episode")],
        [InlineKeyboardButton(text="📋 Kinolar Ro'yxati", callback_data="movies_list_page_0"),
         InlineKeyboardButton(text="📊 Statistika", callback_data="admin_stats")],
        [InlineKeyboardButton(text="🗑 Kino O'chirish", callback_data="delete_movie"),
         InlineKeyboardButton(text="✏️ Kino Tahrirlash", callback_data="edit_movie")],
        [InlineKeyboardButton(text="📡 Kanallar", callback_data="sub_channels"),
         InlineKeyboardButton(text="📣 Xabar Yuborish", callback_data="broadcast")],
        [InlineKeyboardButton(text="📤 Kanalga Yuborish", callback_data="post_to_channel"),
         InlineKeyboardButton(text="🛠 Qism Boshqarish", callback_data="manage_episodes")],
        [InlineKeyboardButton(text="💾 Backup Olish", callback_data="backup_take"),
         InlineKeyboardButton(text="♻️ Backup Tiklash", callback_data="backup_restore")],
    ]
    if user_id is None or is_super_admin(user_id):
        base.append([InlineKeyboardButton(text="👥 Adminlar", callback_data="admins_menu")])
    base.append([InlineKeyboardButton(text="🔙 Asosiy Menu", callback_data="admin_to_main")])
    return InlineKeyboardMarkup(inline_keyboard=base)

@admin_router.callback_query(F.data == "admin_to_main")
async def cb_admin_to_main(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.delete()
    await call.message.answer("🏠 <b>BOSH SAHIFA</b>\n\nKerakli bo'limni tanlang 👇", parse_mode="HTML", reply_markup=main_menu_kb())
    await call.answer()

def main_menu_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔎 Kino qidirish")],
            [KeyboardButton(text="🎬 Filmlar"), KeyboardButton(text="📺 Seriallar")],
            [KeyboardButton(text="❤️ Sevimlilar"), KeyboardButton(text="👤 Profil")],
        ],
        resize_keyboard=True
    )

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
        f"‼️ Filmni tomosha qilish uchun @{BOT_USERNAME} ga «{code}» kodini yuboring!\n\n"
        f"🔑 <b>FILM KODI:</b> <code>{code}</code>"
    )

@admin_router.message(Command("admin"), F.from_user.id.in_(ADMIN_IDS))
async def admin_panel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("🛠 Admin panelga xush kelibsiz! Kerakli bo'limni tanlang:", reply_markup=admin_menu(message.from_user.id))

@admin_router.callback_query(F.data == "back_to_admin")
async def back_to_admin(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    await state.clear()
    try:
        await call.message.edit_text("🛠 Admin panelga xush kelibsiz! Kerakli bo'limni tanlang:", reply_markup=admin_menu(call.from_user.id))
    except Exception:
        await call.message.answer("🛠 Admin panelga xush kelibsiz! Kerakli bo'limni tanlang:", reply_markup=admin_menu(call.from_user.id))
    await call.answer()

MOVIES_PER_PAGE = 10

def movies_list_page_kb(page, total_pages):
    row = []
    if page > 0:
        row.append(InlineKeyboardButton(text="⬅️", callback_data=f"movies_list_page_{page-1}"))
    row.append(InlineKeyboardButton(text=f"{page+1}/{max(total_pages,1)}", callback_data="noop"))
    if page < total_pages - 1:
        row.append(InlineKeyboardButton(text="➡️", callback_data=f"movies_list_page_{page+1}"))
    kb = [row] if row else []
    kb.append([InlineKeyboardButton(text="🔎 Qidirish", callback_data="movies_list_search")])
    kb.append([InlineKeyboardButton(text="🔙 Admin Panel", callback_data="back_to_admin")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def movie_detail_kb(code):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Tahrirlash", callback_data=f"mdet_edit_{code}"),
         InlineKeyboardButton(text="🗑 O'chirish", callback_data=f"mdet_del_{code}")],
        [InlineKeyboardButton(text="📺 Qismlar", callback_data=f"mdet_eps_{code}")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="movies_list_page_0")]
    ])

@admin_router.callback_query(F.data.startswith("movies_list_page_"))
async def cb_movies_list_page(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    await state.clear()
    page = int(call.data.split("_")[-1])
    movies = get_all_movies()
    total_pages = max((len(movies) + MOVIES_PER_PAGE - 1) // MOVIES_PER_PAGE, 1)
    page = max(0, min(page, total_pages - 1))
    start = page * MOVIES_PER_PAGE
    chunk = movies[start:start + MOVIES_PER_PAGE]

    if not chunk:
        text = "📭 Hozircha botda kinolar mavjud emas."
    else:
        text = "📋 <b>KINOLAR RO'YXATI</b>\n\n"
        for i, (code, title, year) in enumerate(chunk, start=start + 1):
            text += f"{i}. {title} — Kod: {code}\n"

    kb_rows = [[InlineKeyboardButton(text=f"{title} ({code})", callback_data=f"mdet_{code}")] for code, title, year in chunk]
    nav = movies_list_page_kb(page, total_pages).inline_keyboard
    kb = InlineKeyboardMarkup(inline_keyboard=kb_rows + nav)
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    await call.answer()

@admin_router.callback_query(F.data == "noop")
async def cb_noop(call: CallbackQuery):
    await call.answer()

@admin_router.callback_query(F.data == "movies_list_search")
async def cb_movies_list_search(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    await call.message.edit_text("🔎 Qidirilayotgan kino nomi yoki kodini yuboring:", reply_markup=cancel_kb())
    await state.set_state(MoviesListSearch.query)

@admin_router.message(MoviesListSearch.query, F.from_user.id.in_(ADMIN_IDS))
async def m_movies_list_search(message: Message, state: FSMContext):
    await state.clear()
    q = message.text.strip()
    if q.isdigit():
        movie = get_movie_by_code(int(q))
        rows = [(movie[1], movie[2], movie[3])] if movie else []
    else:
        rows = search_movies_by_title(q)
    if not rows:
        return await message.answer("❌ Hech narsa topilmadi.", reply_markup=admin_menu(message.from_user.id))
    kb_rows = [[InlineKeyboardButton(text=f"{title} ({code})", callback_data=f"mdet_{code}")] for code, title, year in rows]
    kb_rows.append([InlineKeyboardButton(text="🔙 Admin Panel", callback_data="back_to_admin")])
    await message.answer("🔎 Natijalar:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows))

@admin_router.callback_query(F.data.startswith("mdet_") & ~F.data.startswith("mdet_edit_") & ~F.data.startswith("mdet_del_") & ~F.data.startswith("mdet_eps_"))
async def cb_movie_detail(call: CallbackQuery):
    if not is_admin(call.from_user.id): return
    code = int(call.data.split("_")[1])
    movie = get_movie_by_code(code)
    if not movie:
        return await call.answer("❌ Topilmadi.", show_alert=True)
    ep_count = len(get_episodes(code))
    text = (
        f"🎬 <b>{movie[2]}</b>\n\n"
        f"🔢 Kod: {movie[1]}\n"
        f"📅 Yil: {movie[3]}\n"
        f"🎭 Janr: {movie[8]}\n"
        f"🌍 Davlat: {movie[6]}\n"
        f"⭐ Reyting: {movie[5]}\n"
        f"📺 Qismlar soni: {ep_count}"
    )
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=movie_detail_kb(code))
    await call.answer()

@admin_router.callback_query(F.data.startswith("mdet_edit_"))
async def cb_movie_detail_edit(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    code = int(call.data.split("_")[2])
    await state.update_data(code=code)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Nom", callback_data="field_title"),
         InlineKeyboardButton(text="📅 Yil", callback_data="field_year")],
        [InlineKeyboardButton(text="🎭 Janr", callback_data="field_genre"),
         InlineKeyboardButton(text="🌍 Davlat", callback_data="field_country")],
        [InlineKeyboardButton(text="⭐ Reyting", callback_data="field_imdb"),
         InlineKeyboardButton(text="🖼 Poster", callback_data="field_poster")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_admin")]
    ])
    await call.message.edit_text("✏️ <b>NIMANI TAHRIRLAMOQCHISIZ?</b>", parse_mode="HTML", reply_markup=kb)
    await state.set_state(EditMovie.field)
    await call.answer()

@admin_router.callback_query(F.data.startswith("mdet_del_"))
async def cb_movie_detail_del(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    code = int(call.data.split("_")[2])
    movie = get_movie_by_code(code)
    if not movie:
        return await call.answer("❌ Topilmadi.", show_alert=True)
    await state.update_data(del_code=code)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗑 Ha, O'chirish", callback_data="confirm_delete"),
         InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"mdet_{code}")]
    ])
    await call.message.edit_text(f"⚠️ <b>O'CHIRISHNI TASDIQLANG</b>\n\n🎬 Nom: {movie[2]}\n🔢 Kod: {code}", parse_mode="HTML", reply_markup=kb)
    await call.answer()

@admin_router.callback_query(F.data.startswith("mdet_eps_"))
async def cb_movie_detail_eps(call: CallbackQuery):
    if not is_admin(call.from_user.id): return
    code = int(call.data.split("_")[2])
    episodes = get_episodes(code)
    if not episodes:
        text = "📭 Bu kinoda hali qismlar yo'q."
    else:
        text = f"📺 <b>Qismlar ({len(episodes)} ta):</b>\n\n" + "\n".join(f"{ep}-qism" for ep, _ in episodes)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Orqaga", callback_data=f"mdet_{code}")]])
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    await call.answer()

# --- Stat va Reklama ---
@admin_router.callback_query(F.data == "admin_stats")
async def admin_stats(call: CallbackQuery):
    if not is_super_admin(call.from_user.id):
        return await call.answer("❌ Bu bo'lim faqat asosiy adminlar uchun!", show_alert=True)
    count = get_users_count()
    new_today = get_new_users_today()
    total_movies = get_total_movies()
    total_eps = get_total_episodes()
    total_views = get_total_views()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Xabar tarqatish (Reklama)", callback_data="broadcast")],
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back_to_admin")]
    ])
    text = (
        "📊 <b>BOT STATISTIKASI</b>\n\n"
        f"👥 Jami foydalanuvchilar: {count}\n"
        f"🆕 Bugun qo'shilgan: {new_today}\n\n"
        f"🎬 Jami kinolar: {total_movies}\n"
        f"📺 Jami qismlar: {total_eps}\n\n"
        f"👁 Jami ko'rishlar: {total_views}"
    )
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=kb)

@admin_router.callback_query(F.data == "broadcast")
async def start_broadcast(call: CallbackQuery, state: FSMContext):
    if not is_super_admin(call.from_user.id):
        return await call.answer("❌ Bu bo'lim faqat asosiy adminlar uchun!", show_alert=True)
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
    text = "📡 <b>KANALLAR</b>\n\n"
    if not channels:
         text += "📭 Kanallar qo'shilmagan."
    else:
        for ch_id, ch_name in channels:
            text += f"🔹 {ch_name} ({ch_id})\n"
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Kanal Qo'shish", callback_data="add_sub_channel")],
        [InlineKeyboardButton(text="📋 Kanallar Ro'yxati", callback_data="sub_channels")],
        [InlineKeyboardButton(text="🗑 Kanal O'chirish", callback_data="remove_sub_channel")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_admin")]
    ])
    await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")

@admin_router.callback_query(F.data == "add_sub_channel")
async def add_sub_channel(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    await call.message.edit_text("📢 Kanal username yoki ID yuboring:\n\nMasalan:\n@MovieChannel", reply_markup=cancel_kb())
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

# --- Kanalga Yuborish ---
@admin_router.callback_query(F.data == "post_to_channel")
async def cb_post_to_channel(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    channels = get_required_channels()
    if not channels:
        return await call.answer("📭 Avval kanal qo'shing.", show_alert=True)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=ch_name, callback_data=f"ptc_ch_{ch_id}")] for ch_id, ch_name in channels
    ] + [[InlineKeyboardButton(text="❌ Bekor qilish", callback_data="back_to_admin")]])
    await call.message.edit_text("📡 Kanalni tanlang:", reply_markup=kb)

@admin_router.callback_query(F.data.startswith("ptc_ch_"))
async def cb_ptc_channel_chosen(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    channel_id = call.data.split("_", 2)[2]
    await state.update_data(target_channel=channel_id)
    await call.message.edit_text("📝 Xabar yuboring:", reply_markup=cancel_kb())
    await state.set_state(PostToChannel.content)

@admin_router.message(PostToChannel.content, F.from_user.id.in_(ADMIN_IDS))
async def m_ptc_content(message: Message, state: FSMContext):
    await state.update_data(msg_id=message.message_id, from_chat=message.chat.id)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📤 Kanalga Yuborish", callback_data="ptc_confirm"),
         InlineKeyboardButton(text="❌ Bekor qilish", callback_data="back_to_admin")]
    ])
    await message.answer("👀 Xabar shu ko'rinishda yuboriladi. Tasdiqlaysizmi?", reply_markup=kb)

@admin_router.callback_query(F.data == "ptc_confirm")
async def cb_ptc_confirm(call: CallbackQuery, state: FSMContext, bot: Bot):
    if not is_admin(call.from_user.id): return
    data = await state.get_data()
    await state.clear()
    try:
        await bot.copy_message(chat_id=data["target_channel"], from_chat_id=data["from_chat"], message_id=data["msg_id"])
        await call.message.edit_text("✅ Xabar kanalga yuborildi.")
    except Exception as e:
        await call.message.edit_text(f"❌ Xatolik: {e}")
    await call.message.answer("🛠 Admin panel:", reply_markup=admin_menu(call.from_user.id))
    await call.answer()

# --- Qism Boshqarish ---
EPISODES_PER_PAGE = 10

@admin_router.callback_query(F.data == "manage_episodes")
async def cb_manage_episodes(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    await call.message.edit_text("🔢 Kino kodini yuboring:", reply_markup=cancel_kb())
    await state.set_state(ManageEpisodes.movie_code)

@admin_router.message(ManageEpisodes.movie_code, F.from_user.id.in_(ADMIN_IDS))
async def m_manage_ep_code(message: Message, state: FSMContext):
    if not message.text.isdigit(): return await message.answer("Faqat raqam kiriting:", reply_markup=cancel_kb())
    code = int(message.text)
    movie = get_movie_by_code(code)
    if not movie:
        return await message.answer("❌ Bunday kodli kino topilmadi.", reply_markup=cancel_kb())
    await state.clear()
    await show_episodes_page(message, code, 0)

async def show_episodes_page(target, code, page):
    movie = get_movie_by_code(code)
    episodes = get_episodes(code)
    total_pages = max((len(episodes) + EPISODES_PER_PAGE - 1) // EPISODES_PER_PAGE, 1)
    page = max(0, min(page, total_pages - 1))
    chunk = episodes[page * EPISODES_PER_PAGE: page * EPISODES_PER_PAGE + EPISODES_PER_PAGE]

    text = f"🎬 <b>{movie[2]}</b>\n\n"
    if not episodes:
        text += "📭 Qismlar mavjud emas."
    else:
        text += "\n".join(f"{ep}-qism" for ep, _ in chunk)

    kb_rows = [[InlineKeyboardButton(text=f"{ep}-qism", callback_data=f"epm_{code}_{ep}")] for ep, _ in chunk]
    nav = []
    if page > 0: nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"epmpage_{code}_{page-1}"))
    nav.append(InlineKeyboardButton(text=f"{page+1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1: nav.append(InlineKeyboardButton(text="➡️", callback_data=f"epmpage_{code}_{page+1}"))
    if nav: kb_rows.append(nav)
    kb_rows.append([InlineKeyboardButton(text="🔙 Admin Panel", callback_data="back_to_admin")])

    if isinstance(target, Message):
        await target.answer(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows))
    else:
        await target.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows))

@admin_router.callback_query(F.data.startswith("epmpage_"))
async def cb_epm_page(call: CallbackQuery):
    if not is_admin(call.from_user.id): return
    _, code, page = call.data.split("_")
    await show_episodes_page(call, int(code), int(page))
    await call.answer()

@admin_router.callback_query(
    F.data.startswith("epm_")
    & ~F.data.in_(["epm_edit_num", "epm_edit_video", "epm_delete", "epm_delete_confirm"])
)
async def cb_epm_detail(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    _, code, ep = call.data.split("_")
    code, ep = int(code), int(ep)
    await state.update_data(epm_code=code, epm_ep=ep)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Qism ma'lumotini tahrirlash", callback_data="epm_edit_num")],
        [InlineKeyboardButton(text="🔄 Videoni almashtirish", callback_data="epm_edit_video")],
        [InlineKeyboardButton(text="🗑 Qismni o'chirish", callback_data="epm_delete")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data=f"epmpage_{code}_0")]
    ])
    await call.message.edit_text(f"📺 <b>{ep}-qism</b> (kino kodi: {code})", parse_mode="HTML", reply_markup=kb)
    await call.answer()

@admin_router.callback_query(F.data == "epm_edit_num")
async def cb_epm_edit_num(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    await call.message.edit_text("🔢 Qism uchun yangi raqamni yuboring:", reply_markup=cancel_kb())
    await state.set_state(ManageEpisodes.new_number)

@admin_router.message(ManageEpisodes.new_number, F.from_user.id.in_(ADMIN_IDS))
async def m_epm_new_number(message: Message, state: FSMContext):
    if not message.text.isdigit(): return await message.answer("Faqat raqam kiriting:", reply_markup=cancel_kb())
    data = await state.get_data()
    update_episode_number(data["epm_code"], data["epm_ep"], int(message.text))
    await state.clear()
    await message.answer("✅ Qism ma'lumoti yangilandi!", reply_markup=admin_menu(message.from_user.id))

@admin_router.callback_query(F.data == "epm_edit_video")
async def cb_epm_edit_video(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    await call.message.edit_text("🎥 Yangi video yuboring:", reply_markup=cancel_kb())
    await state.set_state(ManageEpisodes.new_video)

@admin_router.message(ManageEpisodes.new_video, F.video, F.from_user.id.in_(ADMIN_IDS))
async def m_epm_new_video(message: Message, state: FSMContext):
    data = await state.get_data()
    update_episode_file(data["epm_code"], data["epm_ep"], message.video.file_id)
    await state.clear()
    await message.answer("✅ Video muvaffaqiyatli almashtirildi!", reply_markup=admin_menu(message.from_user.id))

@admin_router.callback_query(F.data == "epm_delete")
async def cb_epm_delete(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    data = await state.get_data()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗑 Ha, O'chirish", callback_data="epm_delete_confirm"),
         InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"epm_{data['epm_code']}_{data['epm_ep']}")]
    ])
    await call.message.edit_text(f"⚠️ {data['epm_ep']}-qismni o'chirishni tasdiqlaysizmi?", reply_markup=kb)
    await call.answer()

@admin_router.callback_query(F.data == "epm_delete_confirm")
async def cb_epm_delete_confirm(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    data = await state.get_data()
    delete_episode(data["epm_code"], data["epm_ep"])
    await state.clear()
    await call.message.edit_text("✅ Qism o'chirildi.")
    await call.message.answer("🛠 Admin panel:", reply_markup=admin_menu(call.from_user.id))
    await call.answer()

# --- Backup ---
@admin_router.callback_query(F.data == "backup_take")
async def cb_backup_take(call: CallbackQuery, bot: Bot):
    if not is_super_admin(call.from_user.id):
        return await call.answer("❌ Bu bo'lim faqat asosiy adminlar uchun!", show_alert=True)
    date_str = datetime.now().strftime("%Y_%m_%d")
    backup_name = f"movie_backup_{date_str}.db"
    backup_path = os.path.join("/tmp", backup_name)
    shutil.copy(DB_PATH, backup_path)
    await bot.send_document(chat_id=call.from_user.id, document=FSInputFile(backup_path, filename=backup_name))
    await call.message.answer("✅ Backup muvaffaqiyatli yaratildi.", reply_markup=admin_menu(call.from_user.id))
    await call.answer()

@admin_router.callback_query(F.data == "backup_restore")
async def cb_backup_restore(call: CallbackQuery, state: FSMContext):
    if not is_super_admin(call.from_user.id):
        return await call.answer("❌ Bu bo'lim faqat asosiy adminlar uchun!", show_alert=True)
    await call.message.edit_text(
        "⚠️ <b>DIQQAT!</b>\n\nHozirgi database backup bilan almashtiriladi.\n\n.db faylni yuboring:",
        parse_mode="HTML", reply_markup=cancel_kb()
    )
    await state.set_state(BackupRestore.file)

@admin_router.message(BackupRestore.file, F.document, F.from_user.id.in_(ADMIN_IDS))
async def m_backup_restore_file(message: Message, state: FSMContext, bot: Bot):
    await state.update_data(file_id=message.document.file_id)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Ha, Tiklash", callback_data="backup_restore_confirm"),
         InlineKeyboardButton(text="❌ Bekor qilish", callback_data="back_to_admin")]
    ])
    await message.answer("⚠️ Davom etasizmi? Bu amalni orqaga qaytarib bo'lmaydi.", reply_markup=kb)

@admin_router.callback_query(F.data == "backup_restore_confirm")
async def cb_backup_restore_confirm(call: CallbackQuery, state: FSMContext, bot: Bot):
    if not is_super_admin(call.from_user.id): return
    data = await state.get_data()
    await state.clear()
    file = await bot.get_file(data["file_id"])
    await bot.download_file(file.file_path, destination=DB_PATH)
    await call.message.edit_text("✅ Database muvaffaqiyatli tiklandi.")
    await call.message.answer("🛠 Admin panel:", reply_markup=admin_menu(call.from_user.id))
    await call.answer()

# --- Kino Qo'shish Ketma-ketligi (FSM) ---
@admin_router.callback_query(F.data == "add_movie")
async def cb_add_movie(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    await call.message.edit_text("🎬 Kino kodini yozing:\n(faqat raqam, masalan: 101)", reply_markup=cancel_kb())
    await state.set_state(AddMovie.code)

@admin_router.message(AddMovie.code, F.from_user.id.in_(ADMIN_IDS))
async def m_code(message: Message, state: FSMContext):
    if not message.text.isdigit():
        return await message.answer("❌ Iltimos, faqat raqam kiriting:")
    code = int(message.text)
    if get_movie_by_code(code):
        return await message.answer("❌ Bu kod allaqachon mavjud.\nBoshqa kod yuboring.")
    await state.update_data(code=code)
    await message.answer(
        "📝 Endi kino ma'lumotlarini bitta xabarda quyidagi ko'rinishda yuboring:\n\n"
        "Nom:\nYil:\nJanr:\nDavlat:\nReyting:\n\n"
        "Masalan:\n\n"
        "Nom: One Piece\nYil: 1999\nJanr: Jangari, Sarguzasht\nDavlat: Yaponiya\nReyting: 8.5",
        reply_markup=cancel_kb()
    )
    await state.set_state(AddMovie.info)

@admin_router.message(AddMovie.info, F.from_user.id.in_(ADMIN_IDS))
async def m_info(message: Message, state: FSMContext):
    fields = {"nom": "", "yil": "", "janr": "", "davlat": "", "reyting": ""}
    for line in message.text.splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip().lower()
        if key in fields:
            fields[key] = value.strip()

    if not fields["nom"] or not fields["yil"]:
        return await message.answer(
            "❌ Format noto'g'ri. Iltimos, quyidagicha yuboring:\n\n"
            "Nom:\nYil:\nJanr:\nDavlat:\nReyting:",
            reply_markup=cancel_kb()
        )

    await state.update_data(
        title=fields["nom"], year=fields["yil"], genre=fields["janr"],
        country=fields["davlat"], imdb=fields["reyting"],
        quality="", language="", description=""
    )
    await message.answer("🖼 Endi kino posterini yuboring:", reply_markup=cancel_kb())
    await state.set_state(AddMovie.poster)

@admin_router.message(AddMovie.poster, F.photo, F.from_user.id.in_(ADMIN_IDS))
async def m_poster(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    poster = message.photo[-1].file_id

    success = add_movie(
        data['code'], data['title'], data['year'], data['quality'], data['imdb'],
        data['country'], data['language'], data['genre'], data['description'], poster, None
    )
    await state.clear()
    if success:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Yana Kino Qo'shish", callback_data="add_movie")],
            [InlineKeyboardButton(text="🔙 Admin Panel", callback_data="back_to_admin")]
        ])
        await message.answer(
            f"✅ Kino muvaffaqiyatli qo'shildi!\n\n🎬 Nomi: {data['title']}\n🔢 Kodi: {data['code']}",
            reply_markup=kb
        )
        try:
            caption = build_movie_caption(data, data['code'])
            movie_kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🎬 Ko'rish", url=f"https://t.me/{BOT_USERNAME}?start=film_{data['code']}")]
            ])
            await bot.send_photo(chat_id=CHANNEL_ID, photo=poster, caption=caption, parse_mode="HTML", reply_markup=movie_kb)
        except Exception as e:
            logging.warning(f"Kanalga post yuborishda xatolik: {e}")
    else:
        await message.answer("❌ Bu kodli kino allaqachon mavjud!", reply_markup=admin_menu(message.from_user.id))

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
    await state.update_data(new_file_id=message.video.file_id)
    if episode_exists(data["movie_code"], data["episode"]):
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Almashtirish", callback_data="ep_replace_confirm"),
             InlineKeyboardButton(text="❌ Bekor qilish", callback_data="back_to_admin")]
        ])
        return await message.answer("⚠️ Bu qism allaqachon mavjud.", reply_markup=kb)
    add_episode(data["movie_code"], data["episode"], message.video.file_id)
    await state.clear()
    await message.answer(
        f"✅ Qism muvaffaqiyatli qo'shildi!\n\n🎬 Kino: {data['movie_code']}\n📺 Qism: {data['episode']}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Yana Qism Qo'shish", callback_data="add_episode")],
            [InlineKeyboardButton(text="🔙 Admin Panel", callback_data="back_to_admin")]
        ])
    )

@admin_router.callback_query(F.data == "ep_replace_confirm")
async def cb_ep_replace_confirm(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    data = await state.get_data()
    update_episode_file(data["movie_code"], data["episode"], data["new_file_id"])
    await state.clear()
    await call.message.edit_text(f"✅ Qism muvaffaqiyatli qo'shildi!\n\n🎬 Kino: {data['movie_code']}\n📺 Qism: {data['episode']}")
    await call.message.answer("🛠 Admin panel:", reply_markup=admin_menu(call.from_user.id))
    await call.answer()

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
    movie = get_movie_by_code(code)
    if not movie:
        await state.clear()
        return await message.answer("❌ Topilmadi.", reply_markup=admin_menu(message.from_user.id))
    await state.update_data(del_code=code)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Ha, o'chirish", callback_data="confirm_delete"),
         InlineKeyboardButton(text="❌ Yo'q", callback_data="back_to_admin")]
    ])
    await message.answer(f"⚠️ Rostan ham <b>{movie[2]} ({movie[3]})</b> (kod: {code}) kinoni o'chirmoqchimisiz?", parse_mode="HTML", reply_markup=kb)

@admin_router.callback_query(F.data == "confirm_delete")
async def cb_confirm_delete(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    data = await state.get_data()
    code = data.get("del_code")
    await state.clear()
    if code is not None and get_movie_by_code(code):
        delete_movie_by_code(code)
        await call.message.edit_text(f"✅ Kod {code} bo'lgan kino o'chirildi.")
        await call.message.answer("🛠 Admin panel:", reply_markup=admin_menu(call.from_user.id))
    else:
        await call.message.edit_text("❌ Topilmadi yoki allaqachon o'chirilgan.")
        await call.message.answer("🛠 Admin panel:", reply_markup=admin_menu(call.from_user.id))
    await call.answer()

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
        [InlineKeyboardButton(text="📝 Nom", callback_data="field_title"),
         InlineKeyboardButton(text="📅 Yil", callback_data="field_year")],
        [InlineKeyboardButton(text="🎭 Janr", callback_data="field_genre"),
         InlineKeyboardButton(text="🌍 Davlat", callback_data="field_country")],
        [InlineKeyboardButton(text="⭐ Reyting", callback_data="field_imdb"),
         InlineKeyboardButton(text="🖼 Poster", callback_data="field_poster")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_admin")]
    ])
    await message.answer("✏️ <b>NIMANI TAHRIRLAMOQCHISIZ?</b>", parse_mode="HTML", reply_markup=kb)
    await state.set_state(EditMovie.field)

@admin_router.callback_query(F.data.startswith("field_"), EditMovie.field)
async def cb_edit_field(call: CallbackQuery, state: FSMContext):
    field_map = {"title": "title", "year": "year", "genre": "genre", "country": "country", "imdb": "imdb", "poster": "poster_file_id"}
    field = call.data.split("_", 1)[1]
    await state.update_data(field=field_map.get(field, field))
    if field == "poster":
        await call.message.edit_text("🖼 Yangi posterni (rasm) yuboring:", reply_markup=cancel_kb())
        await state.set_state(EditMovie.poster)
    else:
        await call.message.edit_text("📝 Yangi qiymatni yuboring:", reply_markup=cancel_kb())
        await state.set_state(EditMovie.value)

@admin_router.message(EditMovie.poster, F.photo, F.from_user.id.in_(ADMIN_IDS))
async def m_edit_poster(message: Message, state: FSMContext):
    data = await state.get_data()
    update_movie_field(data["code"], data["field"], message.photo[-1].file_id)
    await state.clear()
    await message.answer("✅ Muvaffaqiyatli tahrirlandi!", reply_markup=admin_menu(message.from_user.id))

@admin_router.message(EditMovie.value, F.from_user.id.in_(ADMIN_IDS))
async def m_edit_value(message: Message, state: FSMContext):
    data = await state.get_data()
    update_movie_field(data["code"], data["field"], message.text)
    await state.clear()
    await message.answer("✅ Muvaffaqiyatli tahrirlandi!", reply_markup=admin_menu(message.from_user.id))

# --- Adminlar Boshqaruvi ---
@admin_router.callback_query(F.data == "admins_menu")
async def admins_menu(call: CallbackQuery, state: FSMContext):
    if not is_super_admin(call.from_user.id):
        return await call.answer("❌ Bu bo'lim faqat asosiy adminlar uchun!", show_alert=True)
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
    await message.answer(f"✅ <code>{new_id}</code> endi admin sifatida tayinlandi!", parse_mode="HTML", reply_markup=admin_menu(message.from_user.id))

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
        return await message.answer("❌ Asosiy adminni o'chirib bo'lmaydi!", reply_markup=admin_menu(message.from_user.id))
    remove_admin(rem_id)
    await state.clear()
    await message.answer(f"✅ <code>{rem_id}</code> adminlikdan olib tashlandi!", parse_mode="HTML", reply_markup=admin_menu(message.from_user.id))


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
        movie = get_movie_by_code(code)
        if movie:
            return await send_movie_by_code(message, bot, code)
        # Kod topilmasa ham, foydalanuvchiga asosiy menyu ko'rsatiladi
        await message.answer("❌ Afsuski, bunday kodli kino topilmadi.")

    await message.answer(
        f"🎬 <b>Salom, {message.from_user.full_name}!</b> 👋\n\n"
        f"Xush kelibsiz! Quyidagi menyudan kerakli bo'limni tanlang 👇",
        parse_mode="HTML",
        reply_markup=main_menu_kb()
    )

def search_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔤 Nom orqali", callback_data="search_by_title"),
         InlineKeyboardButton(text="🔢 Kod orqali", callback_data="search_by_code")],
        [InlineKeyboardButton(text="📢 Kanaldan qidirish", url=f"https://t.me/{CHANNEL_USERNAME}")],
        [InlineKeyboardButton(text="🎭 Janr", callback_data="search_by_genre"),
         InlineKeyboardButton(text="🌍 Davlat", callback_data="search_by_country")],
        [InlineKeyboardButton(text="📅 Yil", callback_data="search_by_year"),
         InlineKeyboardButton(text="⭐ Reyting", callback_data="search_by_rating")],
        [InlineKeyboardButton(text="🎬 Filmlar", callback_data="filter_movies"),
         InlineKeyboardButton(text="📺 Seriallar", callback_data="filter_series")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_main")]
    ])

@user_router.message(F.text == "🔎 Kino qidirish")
async def open_search_menu(message: Message, bot: Bot):
    not_sub = await check_subscription(bot, message.from_user.id)
    if not_sub: return await subscription_warning(message, not_sub)
    await message.answer("🔎 <b>KINO QIDIRISH</b>\n\nKerakli usulni tanlang:", parse_mode="HTML", reply_markup=search_menu_kb())

@user_router.callback_query(F.data == "back_to_main")
async def cb_back_to_main(call: CallbackQuery):
    await call.message.delete()
    await call.message.answer("🏠 <b>BOSH SAHIFA</b>\n\nKerakli bo'limni tanlang 👇", parse_mode="HTML", reply_markup=main_menu_kb())
    await call.answer()

@user_router.callback_query(F.data == "search_by_title")
async def cb_search_by_title(call: CallbackQuery, state: FSMContext):
    await call.message.edit_text("🔤 Qidirayotgan kino nomini kiriting:")
    await state.set_state(SearchState.query)
    await call.answer()

@user_router.callback_query(F.data == "search_by_code")
async def cb_search_by_code(call: CallbackQuery):
    await call.message.edit_text("🔢 Kino kodini raqam ko'rinishida yuboring:")
    await call.answer()

def movies_result_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="reopen_search")]
    ])

@user_router.callback_query(F.data == "reopen_search")
async def cb_reopen_search(call: CallbackQuery):
    await call.message.edit_text("🔎 <b>KINO QIDIRISH</b>\n\nKerakli usulni tanlang:", parse_mode="HTML", reply_markup=search_menu_kb())
    await call.answer()

def format_movie_rows(rows, empty_text="❌ Hech narsa topilmadi."):
    if not rows:
        return empty_text
    text = ""
    for code, title, year in rows:
        text += f"🔑 Kod: <code>{code}</code> | 🎬 {title} ({year})\n"
    return text

@user_router.callback_query(F.data == "filter_movies")
async def cb_filter_movies(call: CallbackQuery):
    rows = get_movies_without_episodes()
    text = "🎬 <b>Filmlar:</b>\n\n" + format_movie_rows(rows, "📭 Hozircha filmlar mavjud emas.")
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=movies_result_kb())
    await call.answer()

@user_router.callback_query(F.data == "filter_series")
async def cb_filter_series(call: CallbackQuery):
    rows = get_movies_with_episodes()
    text = "📺 <b>Seriallar:</b>\n\n" + format_movie_rows(rows, "📭 Hozircha seriallar mavjud emas.")
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=movies_result_kb())
    await call.answer()

@user_router.callback_query(F.data == "search_by_rating")
async def cb_search_by_rating(call: CallbackQuery):
    rows = get_top_rated_movies()
    if not rows:
        text = "📭 Hozircha baholangan kinolar mavjud emas."
    else:
        text = "⭐ <b>Eng yuqori baholangan kinolar:</b>\n\n"
        for code, title, year, avg_r in rows:
            text += f"🔑 <code>{code}</code> | 🎬 {title} ({year}) — ⭐ {round(avg_r, 1)}\n"
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=movies_result_kb())
    await call.answer()

@user_router.callback_query(F.data == "search_by_genre")
async def cb_search_by_genre(call: CallbackQuery):
    buttons = [[InlineKeyboardButton(text=g, callback_data=f"fg_{g}")] for g in GENRES]
    buttons.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="reopen_search")])
    await call.message.edit_text("🎭 Janrni tanlang:", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await call.answer()

@user_router.callback_query(F.data.startswith("fg_"))
async def cb_filter_by_genre(call: CallbackQuery):
    genre = call.data.split("_", 1)[1]
    rows = search_movies_by_genre(genre)
    text = f"🎭 <b>{genre}:</b>\n\n" + format_movie_rows(rows)
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=movies_result_kb())
    await call.answer()

@user_router.callback_query(F.data == "search_by_country")
async def cb_search_by_country(call: CallbackQuery):
    countries = get_distinct_countries()
    if not countries:
        await call.answer("📭 Hozircha davlatlar mavjud emas.", show_alert=True)
        return
    buttons = [[InlineKeyboardButton(text=c, callback_data=f"fc_{c}")] for c in countries]
    buttons.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="reopen_search")])
    await call.message.edit_text("🌍 Davlatni tanlang:", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await call.answer()

@user_router.callback_query(F.data.startswith("fc_"))
async def cb_filter_by_country(call: CallbackQuery):
    country = call.data.split("_", 1)[1]
    rows = search_movies_by_country(country)
    text = f"🌍 <b>{country}:</b>\n\n" + format_movie_rows(rows)
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=movies_result_kb())
    await call.answer()

@user_router.callback_query(F.data == "search_by_year")
async def cb_search_by_year(call: CallbackQuery):
    years = get_distinct_years()
    if not years:
        await call.answer("📭 Hozircha yillar mavjud emas.", show_alert=True)
        return
    buttons = [[InlineKeyboardButton(text=y, callback_data=f"fy_{y}")] for y in years]
    buttons.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="reopen_search")])
    await call.message.edit_text("📅 Yilni tanlang:", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await call.answer()

@user_router.callback_query(F.data.startswith("fy_"))
async def cb_filter_by_year(call: CallbackQuery):
    year = call.data.split("_", 1)[1]
    rows = search_movies_by_year(year)
    text = f"📅 <b>{year}:</b>\n\n" + format_movie_rows(rows)
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=movies_result_kb())
    await call.answer()

@user_router.message(F.text == "🎬 Filmlar")
async def rk_filmlar(message: Message, bot: Bot):
    not_sub = await check_subscription(bot, message.from_user.id)
    if not_sub: return await subscription_warning(message, not_sub)
    rows = get_movies_without_episodes()
    text = "🎬 <b>Filmlar:</b>\n\n" + format_movie_rows(rows, "📭 Hozircha filmlar mavjud emas.")
    await message.answer(text, parse_mode="HTML")

@user_router.message(F.text == "📺 Seriallar")
async def rk_seriallar(message: Message, bot: Bot):
    not_sub = await check_subscription(bot, message.from_user.id)
    if not_sub: return await subscription_warning(message, not_sub)
    rows = get_movies_with_episodes()
    text = "📺 <b>Seriallar:</b>\n\n" + format_movie_rows(rows, "📭 Hozircha seriallar mavjud emas.")
    await message.answer(text, parse_mode="HTML")

@user_router.message(F.text == "❤️ Sevimlilar")
async def rk_sevimlilar(message: Message, bot: Bot):
    not_sub = await check_subscription(bot, message.from_user.id)
    if not_sub: return await subscription_warning(message, not_sub)
    rows = get_user_favorites(message.from_user.id)
    text = "❤️ <b>Sevimli kinolaringiz:</b>\n\n" + format_movie_rows(rows, "📭 Sevimlilar ro'yxati bo'sh.\n\nKino ochib, ❤️ tugmasini bosing.")
    await message.answer(text, parse_mode="HTML")

@user_router.message(F.text == "👤 Profil")
async def rk_profil(message: Message, bot: Bot):
    not_sub = await check_subscription(bot, message.from_user.id)
    if not_sub: return await subscription_warning(message, not_sub)
    fav_count = len(get_user_favorites(message.from_user.id))
    joined = get_user_join_date(message.from_user.id) or "—"
    text = (
        f"👤 <b>Profil</b>\n\n"
        f"🆔 ID: <code>{message.from_user.id}</code>\n"
        f"👤 Ism: {message.from_user.full_name}\n"
        f"📅 Ro'yxatdan o'tgan: {joined}\n"
        f"❤️ Sevimlilar soni: {fav_count} ta"
    )
    await message.answer(text, parse_mode="HTML")

@user_router.callback_query(F.data == "show_movies_list")
async def cb_show_movies_list(call: CallbackQuery):
    await call.message.answer(movies_list_text(), parse_mode="HTML")
    await call.answer()

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
    increment_views(code)
    
    # movie: (id, code, title, year, quality, imdb, country, language, genre, description, poster, trailer, ...)
    caption = (
        f"🎬 <b>{movie[2]} ({movie[3]})</b>\n\n"
        f"🌍 Davlat: {movie[6]}\n"
        f"🗣 Til: {movie[7]}\n"
        f"🎭 Janr: {movie[8]}\n"
        f"💾 Sifat: {movie[4]}\n"
        f"⭐ IMDb: {movie[5]}\n\n"
        f"🔑 Kod: <code>{code}</code>"
    )
    
    episodes = get_episodes(code)
    kb_list = []
    if episodes:
        # Serial bo'lsa faqat qismlar tugmalari (1-Qism, 2-Qism, ...)
        row = []
        for ep_num, _ in episodes:
            row.append(InlineKeyboardButton(text=f"{ep_num}-Qism", callback_data=f"ep_{code}_{ep_num}"))
            if len(row) == 3:
                kb_list.append(row)
                row = []
        if row: kb_list.append(row)
    else:
        # Yagona film bo'lsa, qo'shishda yuklangan video
        kb_list.append([InlineKeyboardButton(text="🎬 Kinoni ko'rish", callback_data=f"watch_{code}")])

    fav_text = "💔 Sevimlilardan olib tashlash" if is_favorite(message.from_user.id, code) else "❤️ Sevimlilarga qo'shish"
    kb_list.append([InlineKeyboardButton(text=fav_text, callback_data=f"fav_{code}")])

    await bot.send_photo(chat_id=message.chat.id, photo=movie[10], caption=caption, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_list))

@user_router.callback_query(F.data.startswith("fav_"))
async def cb_toggle_favorite(call: CallbackQuery):
    code = int(call.data.split("_")[1])
    user_id = call.from_user.id
    if is_favorite(user_id, code):
        remove_favorite(user_id, code)
        await call.answer("💔 Sevimlilardan olib tashlandi")
    else:
        add_favorite(user_id, code)
        await call.answer("❤️ Sevimlilarga qo'shildi")

    kb = call.message.reply_markup.inline_keyboard
    new_kb = []
    for row in kb:
        new_row = []
        for btn in row:
            if btn.callback_data == f"fav_{code}":
                text = "💔 Sevimlilardan olib tashlash" if is_favorite(user_id, code) else "❤️ Sevimlilarga qo'shish"
                new_row.append(InlineKeyboardButton(text=text, callback_data=btn.callback_data))
            else:
                new_row.append(btn)
        new_kb.append(new_row)
    await call.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(inline_keyboard=new_kb))

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
