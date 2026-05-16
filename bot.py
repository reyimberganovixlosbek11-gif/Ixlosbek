import atexit
import logging
import os
import signal
import sys
import time
from flask import Flask, request
import telebot
from telebot import types
import database as db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Token Render'dagi Environment Variable'dan avtomatik olinadi
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN muhit o'zgaruvchisi o'rnatilmagan")

CHANNEL_ID = "@Animelaar_kanal"
CHANNEL_URL = "https://t.me/Animelaar_kanal"
ADMIN_ID = 6222096713

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# Admin bosqichlarini eslab qolish uchun vaqtinchalik baza
temp_data = {}

# ── DB init ───────────────────────────────────────────────────────────────────
db.init_db()

# ── Helpers ───────────────────────────────────────────────────────────────────
def md(text: str) -> str:
    """MarkdownV2 parsi xato bermasligi uchun maxsus belgilarni tozalash."""
    special = r"_*[]()~`>#+-=|{}.!"
    return "".join(f"\\{c}" if c in special else c for c in str(text))

def check_subscription(user_id: int) -> bool:
    try:
        member = bot.get_chat_member(CHANNEL_ID, user_id)
        return member.status in ["member", "administrator", "creator"]
    except Exception as e:
        logger.error("Obuna tekshiruvda xato: %s", e)
        return False

def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID

# ── Markups ───────────────────────────────────────────────────────────────────
def subscription_markup() -> types.InlineKeyboardMarkup:
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📢 Kanalga obuna bo'lish", url=CHANNEL_URL))
    markup.add(types.InlineKeyboardButton("✅ Tasdiqlash", callback_data="check_sub"))
    return markup

def main_menu_markup() -> types.InlineKeyboardMarkup:
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(types.InlineKeyboardButton("🔍 Anime Izlash", callback_data="search"))
    markup.add(
        types.InlineKeyboardButton("⚙️ Kabinet", callback_data="cabinet"),
        types.InlineKeyboardButton("🔴 Shorts", callback_data="shorts"),
    )
    markup.add(
        types.InlineKeyboardButton("🗳 Qo'llanma", callback_data="guide"),
        types.InlineKeyboardButton("📢 Reklama", callback_data="ads"),
    )
    return markup

def admin_panel_markup() -> types.InlineKeyboardMarkup:
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("➕ Anime qo'shish", callback_data="admin_add_anime"))
    markup.add(types.InlineKeyboardButton("📼 Qism qo'shish", callback_data="admin_add_ep"))
    markup.add(types.InlineKeyboardButton("🗑 Anime o'chirish", callback_data="admin_del_anime"))
    markup.add(types.InlineKeyboardButton("📊 Statistika", callback_data="admin_stats"))
    return markup

def episode_buttons_markup(anime_code: str) -> types.InlineKeyboardMarkup:
    eps = db.get_episode_numbers(anime_code)
    markup = types.InlineKeyboardMarkup(row_width=6)
    buttons = [types.InlineKeyboardButton(str(n), callback_data=f"ep_{anime_code}_{n}") for n in eps]
    markup.add(*buttons)
    return markup

def anime_select_markup(callback_prefix: str) -> types.InlineKeyboardMarkup:
    animes = db.get_all_animes()
    markup = types.InlineKeyboardMarkup()
    for a in animes:
        markup.add(types.InlineKeyboardButton(f"{a['code']} — {a['title']}", callback_data=f"{callback_prefix}_{a['code']}"))
    markup.add(types.InlineKeyboardButton("⬅️ Orqaga", callback_data="admin_back"))
    return markup

# ── Commands ──────────────────────────────────────────────────────────────────
@bot.message_handler(commands=["start"])
def send_welcome(message):
    db.add_user(message.from_user.id)
    bot.send_message(
        message.chat.id,
        "🌟 *Assalomu aleykum botimizga xush kelibsiz\\!* \n\n"
        "📺 Botimizda animelarni kanalimizga kirib yuklab olib, tomosha qilishingiz mumkin\\.\n\n"
        "‼️ Botga anime kodini yuboring va qismlarni tanlang\\!",
        reply_markup=main_menu_markup(),
        parse_mode="MarkdownV2",
    )

@bot.message_handler(commands=["list"])
def send_list(message):
    bot.reply_to(
        message,
        "🍿 Barcha anime kodlarini bizning rasmiy kanaldan topishingiz mumkin\\!\n\n"
        "👉 https://t\\.me/Animelaar\\_kanal\n\n"
        "Kanalga a'zo bo'ling va eng so'nggi animelar kodlarini birinchilardan bo'lib oling\\!",
        parse_mode="MarkdownV2",
    )

@bot.message_handler(commands=["help"])
def send_help(message):
    bot.reply_to(
        message,
        "*Botdan foydalanish yo'riqnomasi*\n\n"
        "1\\. Anime kodini yuboring \\(masalan: `1`, `AOT`\\)\n"
        "2\\. Bot posterini va qismlar tugmalarini ko'rsatadi\n"
        "3\\. Kerakli qism tugmasini bosing — video keladi\\!\n\n"
        "Kodlar uchun kanalimizga a'zo bo'ling: https://t\\.me/Animelaar\\_kanal",
        parse_mode="MarkdownV2",
    )

@bot.message_handler(commands=["admin"])
def admin_panel(message):
    if not is_admin(message.from_user.id):
        return
    bot.send_message(message.chat.id, "🔐 *Admin Panel*\n\nQuyidagi amallardan birini tanlang:", reply_markup=admin_panel_markup(), parse_mode="MarkdownV2")

# ── Admin Flows (Anime qo'shish) ───────────────────────────────────────────────
def flow_ask_anime_code(message):
    msg = bot.send_message(message.chat.id, "➕ <b>Anime qo'shish — 1-qadam</b>\n\nAnime uchun qisqa <b>kod</b> kiriting (masalan: <code>1</code>, <code>AOT</code>):", parse_mode="HTML")
    bot.register_next_step_handler(msg, flow_receive_anime_code)

def flow_receive_anime_code(message):
    if not message.text:
        msg = bot.send_message(message.chat.id, "❗ Matn kiriting:")
        bot.register_next_step_handler(msg, flow_receive_anime_code)
        return
    code = message.text.strip().upper()
    temp_data[message.from_user.id] = {"code": code}
    msg = bot.send_message(message.chat.id, f"✅ Kod: <code>{code}</code>\n\n➕ <b>2-qadam</b> — Anime <b>nomini</b> yuboring:", parse_mode="HTML")
    bot.register_next_step_handler(msg, flow_receive_anime_title)

def flow_receive_anime_title(message):
    if not message.text:
        msg = bot.send_message(message.chat.id, "❗ Nom kiriting:")
        bot.register_next_step_handler(msg, flow_receive_anime_title)
        return
    title = message.text.strip()
    temp_data[message.from_user.id]["title"] = title
    msg = bot.send_message(message.chat.id, f"✅ Nom: <b>{title}</b>\n\n➕ <b>3-qadam</b> — Animening <b>rasmini</b> yuboring:\n<i>(Rasm yo'q bo'lsa, <code>skip</code> yozing)</i>", parse_mode="HTML")
    bot.register_next_step_handler(msg, flow_receive_anime_poster)

def flow_receive_anime_poster(message):
    data = temp_data.pop(message.from_user.id, {})
    code = data.get("code", "?")
    title = data.get("title", "?")
    poster_file_id = ""
    if message.content_type == "photo":
        poster_file_id = message.photo[-1].file_id
    elif message.text and message.text.strip().lower() == "skip":
        pass
    else:
        temp_data[message.from_user.id] = data
        msg = bot.send_message(message.chat.id, "❗ Rasm yuboring yoki <code>skip</code> yozing:", parse_mode="HTML")
        bot.register_next_step_handler(msg, flow_receive_anime_poster)
        return
    db.add_anime(code, title, poster_file_id)
    bot.send_message(message.chat.id, f"✅ <b>{title}</b> (kod: <code>{code}</code>) bazaga qo'shildi!", reply_markup=admin_panel_markup(), parse_mode="HTML")

# ── Admin Flows (Qism qo'shish - TUZATILDI!) ──────────────────────────────────
def flow_ask_episode_num(message, anime_code: str):
    eps = db.get_episode_numbers(anime_code)
    existing = f" (mavjud qismlar: {eps})" if eps else ""
    temp_data[message.from_user.id] = {"anime_code": anime_code}
    msg = bot.send_message(message.chat.id, f"📼 <b>Qism qo'shish</b> — <code>{anime_code}</code>{existing}\n\nQism raqamini yuboring:", parse_mode="HTML")
    bot.register_next_step_handler(msg, flow_receive_episode_num)

def flow_receive_episode_num(message):
    if not message.text or not message.text.strip().isdigit():
        msg = bot.send_message(message.chat.id, "❗ Faqat raqam kiriting:")
        bot.register_next_step_handler(msg, flow_receive_episode_num)
        return
    ep_num = int(message.text.strip())
    temp_data[message.from_user.id]["episode_num"] = ep_num
    msg = bot.send_message(message.chat.id, f"✅ Qism raqami: <b>{ep_num}</b>\n\n制造 Endi shu qismning <b>video faylini</b> yuboring:", parse_mode="HTML")
    
    # MANA SHU YERGA KEYINGI QADAMNI KUTISH QO'SHILDI (XATO TUZATILDI!)
    bot.register_next_step_handler(msg, flow_receive_episode_video)

def flow_receive_episode_video(message):
    if message.content_type != "video":
        msg = bot.send_message(message.chat.id, "❗ Iltimos, faqat video fayl yuboring:")
        bot.register_next_step_handler(msg, flow_receive_episode_video)
        return
    
    data = temp_data.pop(message.from_user.id, {})
    anime_code = data.get("anime_code", "?")
    ep_num = data.get("episode_num", 0)
    file_id = message.video.file_id
    
    db.add_episode(anime_code, ep_num, file_id)
    eps = db.get_episode_numbers(anime_code)
    bot.send_message(message.chat.id, f"✅ <code>{anime_code}</code> — <b>{ep_num}-qism</b> muvaffaqiyatli qo'shildi!\n\nJami qismlar: {eps}", reply_markup=admin_panel_markup(), parse_mode="HTML")

# ── Standalone Media Handlers ─────────────────────────────────────────────────
@bot.message_handler(content_types=["photo"])
def handle_photo(message):
    pass

@bot.message_handler(content_types=["video"])
def handle_video_standalone(message):
    if is_admin(message.from_user.id):
        bot.reply_to(message, f"📋 *file\\_id:*\n\n`{message.video.file_id}`", parse_mode="MarkdownV2")

# ── Text Handlers (Anime qidiruv) ─────────────────────────────────────────────
@bot.message_handler(func=lambda m: True)
def handle_code(message):
    db.add_user(message.from_user.id)
    if not check_subscription(message.from_user.id):
        bot.reply_to(message, "🛑 *Botdan foydalanish uchun avval kanalimizga obuna bo'lishingiz kerak\\.*\n\nObuna bo'lgach, *Tasdiqlash* tugmasini bosing\\.", reply_markup=subscription_markup(), parse_mode="MarkdownV2")
        return
    code = message.text.strip().upper()
    anime = db.get_anime(code)
    if not anime:
        bot.reply_to(message, f"❌ *{md(code)}* kodi topilmadi\\.\n\nKodlar kanali: https://t\\.me/Animelaar\\_kanal", parse_mode="MarkdownV2")
        return
    eps = db.get_episode_numbers(code)
    if not eps:
        bot.reply_to(message, f"⏳ *{md(anime['title'])}* uchun hali qismlar yuklanmagan\\.", parse_mode="MarkdownV2")
        return
    caption = f"🎬 *{md(anime['title'])}*\n\n📌 Qaysi qismni ko'rmoqchisiz? Pastdagi tugmani bosing\\!"
    markup = episode_buttons_markup(code)
    if anime.get("poster_file_id"):
        bot.send_photo(message.chat.id, anime["poster_file_id"], caption=caption, reply_markup=markup, parse_mode="MarkdownV2")
    else:
        bot.send_message(message.chat.id, caption, reply_markup=markup, parse_mode="MarkdownV2")

# ── Callbacks ─────────────────────────────────────────────────────────────────
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    uid = call.from_user.id
    if call.data == "check_sub":
        if check_subscription(uid):
            bot.answer_callback_query(call.id, "✅ Obuna tasdiqlandi!")
            bot.edit_message_text("✅ Xush kelibsiz! Anime kodini yuboring.", chat_id=call.message.chat.id, message_id=call.message.message_id)
        else:
            bot.answer_callback_query(call.id, "❌ Siz hali kanalga obuna bo'lmagansiz!", show_alert=True)
        return
    if call.data.startswith("ep_"):
        rest = call.data[3:]
        sep = rest.rfind("_")
        if sep == -1:
            return
        anime_code = rest[:sep]
        try:
            ep_num = int(rest[sep + 1 :])
        except ValueError:
            return
        episode = db.get_episode(anime_code, ep_num)
        if episode:
            bot.answer_callback_query(call.id)
            anime = db.get_anime(anime_code)
            title = anime["title"] if anime else anime_code
            bot.send_video(call.message.chat.id, episode["file_id"], caption=f"🎬 {md(title)} — {md(str(ep_num))}\\-qism", parse_mode="MarkdownV2")
        return
    if call.data == "search":
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "🔍 Anime kodini yuboring.")
        return
    if call.data == "guide":
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "🗳 *Qo'llanma*\n\n1\\. Kodni yuboring\n2\\. Qismni tanlang va tomosha qiling\\!", parse_mode="MarkdownV2")
        return
    if call.data in ["cabinet", "shorts", "ads"]:
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "⚙️ Bu bo'lim tez orada mukammal qilib ishga tushiriladi!")
        return
    
    # Admin amallari
    if not is_admin(uid):
        return
    if call.data == "admin_back":
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "🔐 *Admin Panel*", reply_markup=admin_panel_markup(), parse_mode="MarkdownV2")
        return
    if call.data == "admin_add_anime":
        bot.answer_callback_query(call.id)
        flow_ask_anime_code(call.message)
        return
    if call.data == "admin_add_ep":
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "📼 *Qism qo'shish* — tanlang:", reply_markup=anime_select_markup("addep"), parse_mode="MarkdownV2")
        return
    if call.data.startswith("addep_"):
        bot.answer_callback_query(call.id)
        flow_ask_episode_num(call.message, call.data[6:])
        return
    if call.data == "admin_del_anime":
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "🗑 *O'chirish uchun tanlang:*", reply_markup=anime_select_markup("delanim"), parse_mode="MarkdownV2")
        return
    if call.data.startswith("delanim_"):
        anime_code = call.data[8:]
        db.remove_anime(anime_code)
        bot.answer_callback_query(call.id, f"✅ {anime_code} o'chirildi.")
        bot.edit_message_text("📭 Yangilandi.", chat_id=call.message.chat.id, message_id=call.message.message_id)
        return
    if call.data == "admin_stats":
        bot.answer_callback_query(call.id)
        stats = db.get_stats()
        bot.send_message(call.message.chat.id, f"📊 *Statistika*\n\n🎌 Animelar: `{stats['total_animes']}`\n🎬 Qismlar: `{stats['total_episodes']}`\n👥 Foydalanuvchilar: `{stats['total_users']}`", reply_markup=admin_panel_markup(), parse_mode="MarkdownV2")
        return

# ── WEB SERVER & WEBHOOK CONFIG ───────────────────────────────────────────────
@app.route("/", methods=["GET"])
def home():
    return "Bot is running 24/7 on Render!", 200

@app.route("/" + TOKEN, methods=["POST"])
def get_message():
    json_string = request.get_data().decode("utf-8")
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "!", 200

if __name__ == "__main__":
    bot.remove_webhook()
    time.sleep(1)
    
    # Render beradigan avtomatik tashqi URL havola
    RENDER_URL = os.environ.get("RENDER_EXTERNAL_URL")
    if RENDER_URL:
        bot.set_webhook(url=RENDER_URL + "/" + TOKEN)
        logger.info(f"Webhook o'rnatildi: {RENDER_URL}")
    else:
        logger.warning("RENDER_EXTERNAL_URL topilmadi.")

    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
