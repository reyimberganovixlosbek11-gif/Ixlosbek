import asyncio
import logging
import os
import aiosqlite
from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN", "8878908034:AAFH0DhWmPFqp9PZIsmN5NMLY92PRakhThc")
ADMIN_IDS = [6222096713]
DB_PATH = "kino.db"

# ===================== DATABASE =====================
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""CREATE TABLE IF NOT EXISTS channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id TEXT NOT NULL,
            channel_name TEXT NOT NULL)""")
        await db.execute("""CREATE TABLE IF NOT EXISTS movies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            year TEXT, quality TEXT, imdb TEXT,
            country TEXT, language TEXT, genre TEXT,
            file_id TEXT NOT NULL, file_type TEXT DEFAULT 'video',
            poster_file_id TEXT)""")
        await db.execute("""CREATE TABLE IF NOT EXISTS parts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            movie_code TEXT NOT NULL, part_number INTEGER NOT NULL,
            file_id TEXT NOT NULL, file_type TEXT DEFAULT 'video')""")
        await db.execute("""CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY, username TEXT, full_name TEXT,
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
        try:
            await db.execute("ALTER TABLE movies ADD COLUMN poster_file_id TEXT")
        except Exception:
            pass
        await db.commit()

async def add_user(user_id, username, full_name):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO users (id, username, full_name) VALUES (?, ?, ?)",
                         (user_id, username, full_name))
        await db.commit()

async def get_all_user_ids():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id FROM users") as cursor:
            return [row[0] for row in await cursor.fetchall()]

async def get_user_count():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as cursor:
            return (await cursor.fetchone())[0]

async def get_channels():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT channel_id, channel_name FROM channels") as cursor:
            return await cursor.fetchall()

async def add_channel(channel_id, channel_name):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO channels (channel_id, channel_name) VALUES (?, ?)", (channel_id, channel_name))
        await db.commit()

async def remove_channel(channel_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM channels WHERE channel_id = ?", (channel_id,))
        await db.commit()

async def add_movie(code, name, year, quality, imdb, country, language, genre, file_id, file_type="video", poster_file_id=None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""INSERT OR REPLACE INTO movies
            (code, name, year, quality, imdb, country, language, genre, file_id, file_type, poster_file_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (code.lower(), name, year, quality, imdb, country, language, genre, file_id, file_type, poster_file_id))
        await db.commit()

async def update_movie_info(code, name, year, quality, imdb, country, language, genre):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""UPDATE movies SET name=?, year=?, quality=?, imdb=?, country=?, language=?, genre=?
            WHERE code=?""", (name, year, quality, imdb, country, language, genre, code.lower()))
        await db.commit()

async def get_movie(code):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT * FROM movies WHERE code = ?", (code.lower(),)) as cursor:
            return await cursor.fetchone()

async def add_part(movie_code, part_number, file_id, file_type="video"):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO parts (movie_code, part_number, file_id, file_type) VALUES (?, ?, ?, ?)",
                         (movie_code, part_number, file_id, file_type))
        await db.commit()

async def get_parts(movie_code):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT part_number, file_id, file_type FROM parts WHERE movie_code = ? ORDER BY part_number",
                               (movie_code,)) as cursor:
            return await cursor.fetchall()

async def get_all_movies():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT code, name FROM movies ORDER BY id DESC") as cursor:
            return await cursor.fetchall()

async def delete_movie(code):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM parts WHERE movie_code = ?", (code,))
        await db.execute("DELETE FROM movies WHERE code = ?", (code,))
        await db.commit()

# ===================== HELPERS =====================
def is_admin(user_id):
    return user_id in ADMIN_IDS

def cancel_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_action")]
    ])

async def check_subscription(bot: Bot, user_id: int):
    channels = await get_channels()
    not_subscribed = []
    for channel_id, channel_name in channels:
        try:
            member = await bot.get_chat_member(channel_id, user_id)
            if member.status in ("left", "kicked", "banned"):
                not_subscribed.append((channel_id, channel_name))
        except Exception:
            not_subscribed.append((channel_id, channel_name))
    return not_subscribed

def subscription_keyboard(not_subscribed):
    buttons = []
    for channel_id, channel_name in not_subscribed:
        link = f"https://t.me/{channel_id.lstrip('@')}"
        buttons.append([InlineKeyboardButton(text=f"📢 {channel_name}", url=link)])
    buttons.append([InlineKeyboardButton(text="✅ Tekshirish", callback_data="check_sub")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def main_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Botda mavjud kinolar ro'yxati", callback_data="movie_list")]
    ])

def admin_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎬 Kino qo'shish", callback_data="add_movie")],
        [InlineKeyboardButton(text="📁 Qism qo'shish", callback_data="add_part")],
        [InlineKeyboardButton(text="📋 Kinolar ro'yxati", callback_data="admin_movies")],
        [InlineKeyboardButton(text="📢 Kanallar", callback_data="manage_channels")],
        [InlineKeyboardButton(text="📨 Xabar yuborish", callback_data="broadcast")],
        [InlineKeyboardButton(text="👥 Foydalanuvchilar soni", callback_data="user_count")],
    ])

# ===================== STATES =====================
class AddMovie(StatesGroup):
    code = State()
    name = State()
    year = State()
    quality = State()
    imdb = State()
    country = State()
    language = State()
    genre = State()
    poster = State()
    file = State()

class AddPart(StatesGroup):
    movie_code = State()
    part_number = State()
    file = State()

class AddChannel(StatesGroup):
    channel_id = State()
    channel_name = State()

class Broadcast(StatesGroup):
    message = State()

class EditMovie(StatesGroup):
    name = State()
    year = State()
    quality = State()
    imdb = State()
    country = State()
    language = State()
    genre = State()

# ===================== ROUTER =====================
router = Router()

# ===== Bekor qilish (hamma state uchun) =====
@router.callback_query(F.data == "cancel_action")
async def cancel_handler(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await state.clear()
    await call.message.edit_text("❌ Bekor qilindi!", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Admin panel", callback_data="admin_panel")]
    ]))

# ===== /start =====
@router.message(CommandStart())
async def start_handler(message: Message, bot: Bot):
    await add_user(message.from_user.id, message.from_user.username or "", message.from_user.full_name)
    not_subscribed = await check_subscription(bot, message.from_user.id)
    if not_subscribed:
        await message.answer("🔐 Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:",
                             reply_markup=subscription_keyboard(not_subscribed))
        return
    await message.answer("🎬 Xush kelibsiz!\n\n🎞 Kino kodini yuboring:", reply_markup=main_keyboard())

# ===== /admin =====
@router.message(Command("admin"))
async def admin_panel(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.clear()
    await message.answer("🛠 Admin panel:", reply_markup=admin_keyboard())

@router.callback_query(F.data == "admin_panel")
async def back_to_admin(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await state.clear()
    await call.message.edit_text("🛠 Admin panel:", reply_markup=admin_keyboard())

# ===== Obuna tekshirish =====
@router.callback_query(F.data == "check_sub")
async def check_sub_callback(call: CallbackQuery, bot: Bot):
    not_subscribed = await check_subscription(bot, call.from_user.id)
    if not_subscribed:
        await call.answer("❌ Siz hali barcha kanallarga obuna bo'lmadingiz!", show_alert=True)
        return
    await call.message.edit_text("✅ Obuna tasdiqlandi!\n\n🎞 Kino kodini yuboring:", reply_markup=main_keyboard())

@router.callback_query(F.data == "movie_list")
async def movie_list_callback(call: CallbackQuery):
    await call.answer()
    await call.message.answer(
        "🎬 Botda mavjud barcha kino kodlarini quyidagi kanaldan topasiz! 👇",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎬 Kanalga kirish", url="https://t.me/Jangari_Kinolaarr")]
        ])
    )

# ===== Kino qo'shish =====
@router.callback_query(F.data == "add_movie")
async def add_movie_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await state.clear()
    await call.message.edit_text(
        "🎬 <b>Kino qo'shish</b>\n\n1️⃣ Kino kodini kiriting (masalan: 403):",
        parse_mode="HTML",
        reply_markup=cancel_kb()
    )
    await state.set_state(AddMovie.code)

@router.message(AddMovie.code)
async def movie_code_input(message: Message, state: FSMContext):
    await state.update_data(code=message.text.strip().lower())
    await message.answer("2️⃣ Kino nomini kiriting:\n\nMasalan: <b>Avengers</b>",
                         parse_mode="HTML", reply_markup=cancel_kb())
    await state.set_state(AddMovie.name)

@router.message(AddMovie.name)
async def movie_name_input(message: Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await message.answer("3️⃣ Yilini kiriting:\n\nMasalan: <b>2024</b>",
                         parse_mode="HTML", reply_markup=cancel_kb())
    await state.set_state(AddMovie.year)

@router.message(AddMovie.year)
async def movie_year_input(message: Message, state: FSMContext):
    await state.update_data(year=message.text.strip())
    await message.answer("4️⃣ Sifatini kiriting:\n\nMasalan: <b>1080p | Full HD</b>",
                         parse_mode="HTML", reply_markup=cancel_kb())
    await state.set_state(AddMovie.quality)

@router.message(AddMovie.quality)
async def movie_quality_input(message: Message, state: FSMContext):
    await state.update_data(quality=message.text.strip())
    await message.answer("5️⃣ IMDb reytingini kiriting:\n\nMasalan: <b>8.5/10</b>",
                         parse_mode="HTML", reply_markup=cancel_kb())
    await state.set_state(AddMovie.imdb)

@router.message(AddMovie.imdb)
async def movie_imdb_input(message: Message, state: FSMContext):
    await state.update_data(imdb=message.text.strip())
    await message.answer("6️⃣ Davlatini kiriting:\n\nMasalan: <b>AQSh, Kanada</b>",
                         parse_mode="HTML", reply_markup=cancel_kb())
    await state.set_state(AddMovie.country)

@router.message(AddMovie.country)
async def movie_country_input(message: Message, state: FSMContext):
    await state.update_data(country=message.text.strip())
    await message.answer("7️⃣ Tilini kiriting:\n\nMasalan: <b>O'zbek tilida</b>",
                         parse_mode="HTML", reply_markup=cancel_kb())
    await state.set_state(AddMovie.language)

@router.message(AddMovie.language)
async def movie_language_input(message: Message, state: FSMContext):
    await state.update_data(language=message.text.strip())
    await message.answer("8️⃣ Janrini kiriting:\n\nMasalan: <b>#drama, #komediya</b>",
                         parse_mode="HTML", reply_markup=cancel_kb())
    await state.set_state(AddMovie.genre)

@router.message(AddMovie.genre)
async def movie_genre_input(message: Message, state: FSMContext):
    await state.update_data(genre=message.text.strip())
    data = await state.get_data()
    await message.answer(
        f"✅ <b>Ma'lumotlar qabul qilindi:</b>\n\n"
        f"🔢 Kod: <b>{data['code']}</b>\n"
        f"🎬 Nomi: <b>{data['name']}</b>\n"
        f"📅 Yili: <b>{data['year']}</b>\n"
        f"📺 Sifati: <b>{data['quality']}</b>\n"
        f"⭐ IMDb: <b>{data['imdb']}</b>\n"
        f"🌍 Davlati: <b>{data['country']}</b>\n"
        f"🇺🇿 Tili: <b>{data['language']}</b>\n"
        f"🎭 Janri: <b>{data['genre']}</b>\n\n"
        f"9️⃣ Kino posterini yuboring (rasm):",
        parse_mode="HTML",
        reply_markup=cancel_kb()
    )
    await state.set_state(AddMovie.poster)

@router.message(AddMovie.poster, F.photo)
async def movie_poster_input(message: Message, state: FSMContext):
    await state.update_data(poster_file_id=message.photo[-1].file_id)
    await message.answer("🔟 Endi kino faylini yuboring (video yoki document):",
                         reply_markup=cancel_kb())
    await state.set_state(AddMovie.file)

@router.message(AddMovie.file, F.video | F.document)
async def movie_file_input(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    file_id = message.video.file_id if message.video else message.document.file_id
    file_type = "video" if message.video else "document"
    await add_movie(
        code=data["code"], name=data["name"], year=data["year"],
        quality=data["quality"], imdb=data["imdb"], country=data["country"],
        language=data["language"], genre=data["genre"],
        file_id=file_id, file_type=file_type,
        poster_file_id=data.get("poster_file_id")
    )
    await state.clear()
    await message.answer(
        f"✅ <b>Kino muvaffaqiyatli qo'shildi!</b>\n\n"
        f"🎬 <b>{data['name']}</b>\n🔢 Kod: <b>{data['code']}</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📢 Barcha userlarga yuborish", callback_data=f"notify_{data['code']}")],
            [InlineKeyboardButton(text="🔙 Admin panel", callback_data="admin_panel")]
        ])
    )

@router.callback_query(F.data.startswith("notify_"))
async def notify_users(call: CallbackQuery, bot: Bot):
    if not is_admin(call.from_user.id):
        return
    code = call.data.split("_", 1)[1]
    user_ids = await get_all_user_ids()
    await call.answer("📨 Yuborilmoqda...", show_alert=True)
    success = 0
    for user_id in user_ids:
        try:
            await bot.send_message(user_id,
                f"🎬 Yangi kino qo'shildi!\n\n🔢 Kodi: <b>{code}</b>\n\n"
                f"Kodini botga yuboring va kinoni tomosha qiling! 🍿",
                parse_mode="HTML")
            success += 1
        except Exception:
            pass
    await call.message.answer(f"✅ {success} ta foydalanuvchiga xabar yuborildi!")

# ===== Qism qo'shish =====
@router.callback_query(F.data == "add_part")
async def add_part_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await state.clear()
    await call.message.edit_text(
        "📁 Qaysi kinoga qism qo'shmoqchisiz?\n\nKino kodini kiriting:",
        reply_markup=cancel_kb()
    )
    await state.set_state(AddPart.movie_code)

@router.message(AddPart.movie_code)
async def part_movie_code_input(message: Message, state: FSMContext):
    await state.update_data(movie_code=message.text.strip().lower())
    await message.answer("🔢 Qism raqamini kiriting (masalan: 1, 2, 3):", reply_markup=cancel_kb())
    await state.set_state(AddPart.part_number)

@router.message(AddPart.part_number)
async def part_number_input(message: Message, state: FSMContext):
    try:
        num = int(message.text.strip())
        await state.update_data(part_number=num)
        await message.answer("🎞 Qism faylini yuboring:", reply_markup=cancel_kb())
        await state.set_state(AddPart.file)
    except ValueError:
        await message.answer("❌ Raqam kiriting!", reply_markup=cancel_kb())

@router.message(AddPart.file, F.video | F.document)
async def part_file_input(message: Message, state: FSMContext):
    data = await state.get_data()
    file_id = message.video.file_id if message.video else message.document.file_id
    file_type = "video" if message.video else "document"
    await add_part(data["movie_code"], data["part_number"], file_id, file_type)
    await state.clear()
    await message.answer(
        f"✅ {data['part_number']}-qism qo'shildi!\nKino kodi: <b>{data['movie_code']}</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Admin panel", callback_data="admin_panel")]
        ])
    )

# ===== Kinolar ro'yxati =====
@router.callback_query(F.data == "admin_movies")
async def admin_movies(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    movies = await get_all_movies()
    if not movies:
        await call.answer("📭 Hozircha kinolar yo'q!", show_alert=True)
        return
    text = "🎬 <b>Barcha kinolar:</b>\n\n"
    buttons = []
    for code, name in movies:
        text += f"🔢 <code>{code}</code> — {name}\n"
        buttons.append([
            InlineKeyboardButton(text="✏️ Tahrirlash", callback_data=f"edit_{code}"),
            InlineKeyboardButton(text="🗑 O'chir", callback_data=f"del_{code}")
        ])
    buttons.append([InlineKeyboardButton(text="🔙 Admin panel", callback_data="admin_panel")])
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

# ===== Tahrirlash =====
@router.callback_query(F.data.startswith("edit_"))
async def edit_movie_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    code = call.data.split("_", 1)[1]
    movie = await get_movie(code)
    if not movie:
        await call.answer("❌ Kino topilmadi!", show_alert=True)
        return
    _, m_code, name, year, quality, imdb, country, language, genre, *_ = movie
    await state.update_data(edit_code=code)
    await call.message.edit_text(
        f"✏️ <b>{name}</b> kinoni tahrirlash\n\n"
        f"Hozirgi qiymatlar:\n"
        f"📝 Nom: <b>{name}</b> | 📅 Yil: <b>{year}</b>\n"
        f"📺 Sifat: <b>{quality}</b> | ⭐ IMDb: <b>{imdb}</b>\n"
        f"🌍 Davlat: <b>{country}</b> | 🇺🇿 Til: <b>{language}</b>\n"
        f"🎭 Janr: <b>{genre}</b>\n\n"
        f"1️⃣ Yangi nomni kiriting:",
        parse_mode="HTML",
        reply_markup=cancel_kb()
    )
    await state.set_state(EditMovie.name)

@router.message(EditMovie.name)
async def edit_name_input(message: Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await message.answer("2️⃣ Yangi yilini kiriting:\n\nMasalan: <b>2024</b>",
                         parse_mode="HTML", reply_markup=cancel_kb())
    await state.set_state(EditMovie.year)

@router.message(EditMovie.year)
async def edit_year_input(message: Message, state: FSMContext):
    await state.update_data(year=message.text.strip())
    await message.answer("3️⃣ Yangi sifatini kiriting:\n\nMasalan: <b>1080p | Full HD</b>",
                         parse_mode="HTML", reply_markup=cancel_kb())
    await state.set_state(EditMovie.quality)

@router.message(EditMovie.quality)
async def edit_quality_input(message: Message, state: FSMContext):
    await state.update_data(quality=message.text.strip())
    await message.answer("4️⃣ Yangi IMDb reytingini kiriting:\n\nMasalan: <b>8.5/10</b>",
                         parse_mode="HTML", reply_markup=cancel_kb())
    await state.set_state(EditMovie.imdb)

@router.message(EditMovie.imdb)
async def edit_imdb_input(message: Message, state: FSMContext):
    await state.update_data(imdb=message.text.strip())
    await message.answer("5️⃣ Yangi davlatini kiriting:\n\nMasalan: <b>AQSh, Kanada</b>",
                         parse_mode="HTML", reply_markup=cancel_kb())
    await state.set_state(EditMovie.country)

@router.message(EditMovie.country)
async def edit_country_input(message: Message, state: FSMContext):
    await state.update_data(country=message.text.strip())
    await message.answer("6️⃣ Yangi tilini kiriting:\n\nMasalan: <b>O'zbek tilida</b>",
                         parse_mode="HTML", reply_markup=cancel_kb())
    await state.set_state(EditMovie.language)

@router.message(EditMovie.language)
async def edit_language_input(message: Message, state: FSMContext):
    await state.update_data(language=message.text.strip())
    await message.answer("7️⃣ Yangi janrini kiriting:\n\nMasalan: <b>#drama, #komediya</b>",
                         parse_mode="HTML", reply_markup=cancel_kb())
    await state.set_state(EditMovie.genre)

@router.message(EditMovie.genre)
async def edit_genre_input(message: Message, state: FSMContext):
    await state.update_data(genre=message.text.strip())
    data = await state.get_data()
    await update_movie_info(
        code=data["edit_code"], name=data["name"], year=data["year"],
        quality=data["quality"], imdb=data["imdb"],
        country=data["country"], language=data["language"], genre=data["genre"]
    )
    await state.clear()
    await message.answer(
        f"✅ <b>Kino muvaffaqiyatli tahrirlandi!</b>\n\n"
        f"🔢 Kod: <b>{data['edit_code']}</b>\n"
        f"🎬 Nomi: <b>{data['name']}</b>\n"
        f"📅 Yili: <b>{data['year']}</b>\n"
        f"📺 Sifati: <b>{data['quality']}</b>\n"
        f"⭐ IMDb: <b>{data['imdb']}</b>\n"
        f"🌍 Davlati: <b>{data['country']}</b>\n"
        f"🇺🇿 Tili: <b>{data['language']}</b>\n"
        f"🎭 Janri: <b>{data['genre']}</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📋 Kinolar ro'yxati", callback_data="admin_movies")],
            [InlineKeyboardButton(text="🔙 Admin panel", callback_data="admin_panel")]
        ])
    )

# ===== O'chirish =====
@router.callback_query(F.data.startswith("del_"))
async def delete_movie_confirm(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    code = call.data.split("_", 1)[1]
    await call.message.edit_text(
        f"❓ <b>{code}</b> kodli kinoni o'chirishni tasdiqlaysizmi?",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Ha, o'chir", callback_data=f"confirm_del_{code}"),
             InlineKeyboardButton(text="❌ Yo'q", callback_data="admin_movies")]
        ])
    )

@router.callback_query(F.data.startswith("confirm_del_"))
async def confirm_delete(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    code = call.data.split("_", 2)[2]
    await delete_movie(code)
    await call.answer(f"✅ {code} o'chirildi!", show_alert=True)
    movies = await get_all_movies()
    if not movies:
        await call.message.edit_text("🛠 Admin panel:", reply_markup=admin_keyboard())
        return
    text = "🎬 <b>Barcha kinolar:</b>\n\n"
    buttons = []
    for c, name in movies:
        text += f"🔢 <code>{c}</code> — {name}\n"
        buttons.append([
            InlineKeyboardButton(text="✏️ Tahrirlash", callback_data=f"edit_{c}"),
            InlineKeyboardButton(text="🗑 O'chir", callback_data=f"del_{c}")
        ])
    buttons.append([InlineKeyboardButton(text="🔙 Admin panel", callback_data="admin_panel")])
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

# ===== Kanallar =====
@router.callback_query(F.data == "manage_channels")
async def manage_channels(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    channels = await get_channels()
    text = "📢 <b>Majburiy obuna kanallar:</b>\n\n"
    buttons = []
    if channels:
        for ch_id, ch_name in channels:
            text += f"• {ch_name} — <code>{ch_id}</code>\n"
            buttons.append([InlineKeyboardButton(text=f"🗑 {ch_name}", callback_data=f"rmch_{ch_id}")])
    else:
        text += "Hozircha kanallar yo'q."
    buttons.append([InlineKeyboardButton(text="➕ Kanal qo'shish", callback_data="add_channel")])
    buttons.append([InlineKeyboardButton(text="🔙 Admin panel", callback_data="admin_panel")])
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

@router.callback_query(F.data == "add_channel")
async def add_channel_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await call.message.edit_text(
        "📢 Kanal username kiriting:\n\nMisol: <code>@mening_kanalim</code>",
        parse_mode="HTML",
        reply_markup=cancel_kb()
    )
    await state.set_state(AddChannel.channel_id)

@router.message(AddChannel.channel_id)
async def channel_id_input(message: Message, state: FSMContext):
    await state.update_data(channel_id=message.text.strip())
    await message.answer("📝 Kanal nomini kiriting (ko'rsatiladigan nom):", reply_markup=cancel_kb())
    await state.set_state(AddChannel.channel_name)

@router.message(AddChannel.channel_name)
async def channel_name_input(message: Message, state: FSMContext):
    data = await state.get_data()
    await add_channel(data["channel_id"], message.text.strip())
    await state.clear()
    await message.answer(f"✅ Kanal qo'shildi: <b>{message.text.strip()}</b>", parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Admin panel", callback_data="admin_panel")]
        ]))

@router.callback_query(F.data.startswith("rmch_"))
async def remove_channel_handler(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    ch_id = call.data[5:]
    await remove_channel(ch_id)
    await call.answer("✅ Kanal o'chirildi!", show_alert=True)
    channels = await get_channels()
    text = "📢 <b>Majburiy obuna kanallar:</b>\n\n"
    buttons = []
    if channels:
        for c_id, c_name in channels:
            text += f"• {c_name} — <code>{c_id}</code>\n"
            buttons.append([InlineKeyboardButton(text=f"🗑 {c_name}", callback_data=f"rmch_{c_id}")])
    else:
        text += "Hozircha kanallar yo'q."
    buttons.append([InlineKeyboardButton(text="➕ Kanal qo'shish", callback_data="add_channel")])
    buttons.append([InlineKeyboardButton(text="🔙 Admin panel", callback_data="admin_panel")])
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

# ===== Broadcast =====
@router.callback_query(F.data == "broadcast")
async def broadcast_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await call.message.edit_text(
        "📨 Barcha foydalanuvchilarga yuboriladigan xabarni yozing:",
        reply_markup=cancel_kb()
    )
    await state.set_state(Broadcast.message)

@router.message(Broadcast.message)
async def broadcast_send(message: Message, state: FSMContext, bot: Bot):
    if not is_admin(message.from_user.id):
        return
    await state.clear()
    user_ids = await get_all_user_ids()
    success = 0
    for user_id in user_ids:
        try:
            await bot.copy_message(user_id, message.chat.id, message.message_id)
            success += 1
        except Exception:
            pass
    await message.answer(f"✅ Xabar yuborildi!\n👥 {success} ta foydalanuvchi oldi.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Admin panel", callback_data="admin_panel")]
        ]))

# ===== User count =====
@router.callback_query(F.data == "user_count")
async def user_count_handler(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    count = await get_user_count()
    await call.answer(f"👥 Jami foydalanuvchilar: {count}", show_alert=True)

# ===== Kino kodi (eng oxirida!) =====
@router.message(F.text)
async def code_handler(message: Message, bot: Bot, state: FSMContext):
    current_state = await state.get_state()
    if current_state is not None:
        return
    if message.text.startswith("/"):
        return

    if not is_admin(message.from_user.id):
        not_subscribed = await check_subscription(bot, message.from_user.id)
        if not_subscribed:
            await message.answer("🔐 Avval kanallarga obuna bo'ling:",
                                 reply_markup=subscription_keyboard(not_subscribed))
            return

    code = message.text.strip().lower()
    movie = await get_movie(code)
    if not movie:
        await message.answer("❌ Bunday kodli kino topilmadi!\n\n🎞 Kino kodini to'g'ri kiriting.")
        return

    _, m_code, name, year, quality, imdb, country, language, genre, file_id, file_type, poster_file_id = movie
    caption = (
        f"🎬 <b>Nomi:</b> {name}\n\n"
        f"📅 <b>Yili:</b> {year}\n"
        f"📺 <b>Sifati:</b> {quality}\n"
        f"⭐ <b>IMDb:</b> {imdb}\n"
        f"🌍 <b>Davlati:</b> {country}\n"
        f"🇺🇿 <b>Tili:</b> {language}\n"
        f"🎭 <b>Janri:</b> {genre}\n\n"
        f"🔢 <b>FILM KODI:</b> {m_code}"
    )

    try:
        if poster_file_id:
            await bot.send_photo(message.chat.id, poster_file_id, caption=caption, parse_mode="HTML")
        if file_type == "video":
            await bot.send_video(message.chat.id, file_id, parse_mode="HTML")
        else:
            await bot.send_document(message.chat.id, file_id, parse_mode="HTML")
    except Exception as e:
        await message.answer(f"⚠️ Xato: {e}")
        return

    parts = await get_parts(m_code)
    if len(parts) == 1:
        part_num, part_file_id, part_file_type = parts[0]
        try:
            if part_file_type == "video":
                await bot.send_video(message.chat.id, part_file_id, caption=f"📁 {name} — {part_num}-qism")
            else:
                await bot.send_document(message.chat.id, part_file_id, caption=f"📁 {name} — {part_num}-qism")
        except Exception:
            pass
    elif len(parts) > 1:
        buttons = []
        row = []
        for part_num, _, _ in parts:
            row.append(InlineKeyboardButton(text=str(part_num), callback_data=f"part_{m_code}_{part_num}"))
            if len(row) == 6:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)
        await message.answer(
            f"📁 <b>{name}</b> — qismni tanlang:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
        )

# ===== Qism yuborish =====
@router.callback_query(F.data.startswith("part_"))
async def send_part(call: CallbackQuery, bot: Bot):
    _, movie_code, part_number = call.data.split("_", 2)
    parts = await get_parts(movie_code)
    for p_num, p_file_id, p_file_type in parts:
        if str(p_num) == part_number:
            await call.answer()
            if p_file_type == "video":
                await bot.send_video(call.message.chat.id, p_file_id, caption=f"📁 {part_number}-qism")
            else:
                await bot.send_document(call.message.chat.id, p_file_id, caption=f"📁 {part_number}-qism")
            return

# ===================== MAIN =====================
async def main():
    await init_db()
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
