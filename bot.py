import atexit
import logging
import os
import signal
import sys
import time

import telebot
from telebot import types

import database as db
from keep_alive import keep_alive

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN muhit o'zgaruvchisi o'rnatilmagan")

CHANNEL_ID = "@Animelaar_kanal"
CHANNEL_URL = "https://t.me/Animelaar_kanal"
ADMIN_ID = 6222096713

bot = telebot.TeleBot(TOKEN)

# Temporary storage for multi-step admin flows
temp_data: dict = {}

# ── DB init ───────────────────────────────────────────────────────────────────

db.init_db()


# ── Helpers ───────────────────────────────────────────────────────────────────


def md(text: str) -> str:
    """Escape arbitrary text for MarkdownV2."""
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
    markup.add(
        types.InlineKeyboardButton("➕ Anime qo'shish", callback_data="admin_add_anime")
    )
    markup.add(
        types.InlineKeyboardButton("📼 Qism qo'shish", callback_data="admin_add_ep")
    )
    markup.add(
        types.InlineKeyboardButton("🗑 Anime o'chirish", callback_data="admin_del_anime")
    )
    markup.add(types.InlineKeyboardButton("📊 Statistika", callback_data="admin_stats"))
    return markup


def episode_buttons_markup(anime_code: str) -> types.InlineKeyboardMarkup:
    """Inline episode number buttons for users (6 per row)."""
    eps = db.get_episode_numbers(anime_code)
    markup = types.InlineKeyboardMarkup(row_width=6)
    buttons = [
        types.InlineKeyboardButton(str(n), callback_data=f"ep_{anime_code}_{n}")
        for n in eps
    ]
    markup.add(*buttons)
    return markup


def anime_select_markup(callback_prefix: str) -> types.InlineKeyboardMarkup:
    """List all animes as buttons. callback_data = prefix_CODE."""
    animes = db.get_all_animes()
    markup = types.InlineKeyboardMarkup()
    for a in animes:
        markup.add(
            types.InlineKeyboardButton(
                f"{a['code']} — {a['title']}",
                callback_data=f"{callback_prefix}_{a['code']}",
            )
        )
    markup.add(types.InlineKeyboardButton("⬅️ Orqaga", callback_data="admin_back"))
    return markup


# ── /start ────────────────────────────────────────────────────────────────────


@bot.message_handler(commands=["start"])
def send_welcome(message):
    db.add_user(message.from_user.id)
    bot.send_message(
        message.chat.id,
        "🌟 *Assalomu aleykum botimizga xush kelibsiz\\!*\n\n"
        "📺 Botimizda animelarni kanalimizga kirib yuklab olib, tomosha qilishingiz mumkin\\.\n\n"
        "‼️ Botga anime kodini yuboring va qismlarni tanlang\\!",
        reply_markup=main_menu_markup(),
        parse_mode="MarkdownV2",
    )


# ── /list ─────────────────────────────────────────────────────────────────────


@bot.message_handler(commands=["list"])
def send_list(message):
    bot.reply_to(
        message,
        "🍿 Barcha anime kodlarini bizning rasmiy kanaldan topishingiz mumkin\\!\n\n"
        "👉 https://t\\.me/Animelaar\\_kanal\n\n"
        "Kanalga a'zo bo'ling va eng so'nggi animelar kodlarini birinchilardan bo'lib oling\\!",
        parse_mode="MarkdownV2",
    )


# ── /help ─────────────────────────────────────────────────────────────────────


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


# ── /admin ────────────────────────────────────────────────────────────────────


@bot.message_handler(commands=["admin"])
def admin_panel(message):
    if not is_admin(message.from_user.id):
        return
    bot.send_message(
        message.chat.id,
        "🔐 *Admin Panel*\n\nQuyidagi amallardan birini tanlang:",
        reply_markup=admin_panel_markup(),
        parse_mode="MarkdownV2",
    )


# ── /checkbot ─────────────────────────────────────────────────────────────────


@bot.message_handler(commands=["checkbot"])
def checkbot(message):
    try:
        chat = bot.get_chat(CHANNEL_ID)
        member = bot.get_chat_member(CHANNEL_ID, message.from_user.id)
        bot.reply_to(
            message,
            f"✅ *Kanal topildi\\!*\n\n"
            f"Nomi: `{md(chat.title)}`\n"
            f"Username: `{md(chat.username)}`\n"
            f"ID: `{chat.id}`\n\n"
            f"Sizning holatngiz: `{member.status}`",
            parse_mode="MarkdownV2",
        )
    except Exception as e:
        bot.reply_to(message, f"❌ *Xatolik:*\n\n`{md(e)}`", parse_mode="MarkdownV2")


# ══════════════════════════════════════════════════════════════════════════════
# ADMIN FLOW 1 — Anime qo'shish: code → title → poster → save
# ══════════════════════════════════════════════════════════════════════════════


def flow_ask_anime_code(message):
    msg = bot.send_message(
        message.chat.id,
        "➕ <b>Anime qo'shish — 1-qadam</b>\n\n"
        "Anime uchun qisqa <b>kod</b> kiriting (masalan: <code>1</code>, <code>AOT</code>, <code>SL</code>):",
        parse_mode="HTML",
    )
    bot.register_next_step_handler(msg, flow_receive_anime_code)


def flow_receive_anime_code(message):
    if not message.text:
        msg = bot.send_message(message.chat.id, "❗ Matn kiriting:")
        bot.register_next_step_handler(msg, flow_receive_anime_code)
        return
    code = message.text.strip().upper()
    temp_data[message.from_user.id] = {"code": code}
    msg = bot.send_message(
        message.chat.id,
        f"✅ Kod: <code>{code}</code>\n\n"
        "➕ <b>2-qadam</b> — Anime <b>nomini</b> yuboring:",
        parse_mode="HTML",
    )
    bot.register_next_step_handler(msg, flow_receive_anime_title)


def flow_receive_anime_title(message):
    if not message.text:
        msg = bot.send_message(message.chat.id, "❗ Nom kiriting:")
        bot.register_next_step_handler(msg, flow_receive_anime_title)
        return
    title = message.text.strip()
    temp_data[message.from_user.id]["title"] = title
    msg = bot.send_message(
        message.chat.id,
        f"✅ Nom: <b>{title}</b>\n\n"
        "➕ <b>3-qadam</b> — Animening <b>rasmini (posterini)</b> yuboring:\n"
        "<i>(Rasm yo'q bo'lsa, <code>skip</code> yozing)</i>",
        parse_mode="HTML",
    )
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
        msg = bot.send_message(
            message.chat.id,
            "❗ Rasm yuboring yoki <code>skip</code> yozing:",
            parse_mode="HTML",
        )
        bot.register_next_step_handler(msg, flow_receive_anime_poster)
        return

    db.add_anime(code, title, poster_file_id)
    logger.info("Admin added anime: code=%s title=%s", code, title)
    bot.send_message(
        message.chat.id,
        f"✅ <b>{title}</b> (kod: <code>{code}</code>) bazaga qo'shildi!\n\n"
        "Endi shu animega qismlar qo'shish uchun 📼 <b>Qism qo'shish</b> tugmasini bosing.",
        reply_markup=admin_panel_markup(),
        parse_mode="HTML",
    )


# ══════════════════════════════════════════════════════════════════════════════
# ADMIN FLOW 2 — Qism qo'shish: select anime → episode_num → video → save
# ══════════════════════════════════════════════════════════════════════════════


def flow_ask_episode_num(message, anime_code: str):
    eps = db.get_episode_numbers(anime_code)
    existing = f" (mavjud: {eps})" if eps else ""
    temp_data[message.from_user.id] = {"anime_code": anime_code}
    msg = bot.send_message(
        message.chat.id,
        f"📼 <b>Qism qo'shish</b> — <code>{anime_code}</code>{existing}\n\n"
        "Qism raqamini yuboring (masalan: <code>1</code>):",
        parse_mode="HTML",
    )
    bot.register_next_step_handler(msg, flow_receive_episode_num)


def flow_receive_episode_num(message):
    if not message.text or not message.text.strip().isdigit():
        msg = bot.send_message(message.chat.id, "❗ Faqat raqam kiriting (masalan: 1):")
        bot.register_next_step_handler(msg, flow_receive_episode_num)
        return
    ep_num = int(message.text.strip())
    temp_data[message.from_user.id]["episode_num"] = ep_num
    msg = bot.send_message(
        message.chat.id,
        f"✅ Qism raqami: <b>{ep_num}</b>\n\n"
        "📼 Endi shu qismning <b>video faylini</b> yuboring:",
        parse_mode="HTML",
    )
    bot.register_next_step_handler(msg, flow_receive_episode_video)


def flow_receive_episode_video(message):
    try:
        file_id = None
        if message.content_type == "video" and message.video:
            file_id = message.video.file_id
        elif message.content_type == "document" and message.document:
            mime = message.document.mime_type or ""
            if mime.startswith("video/"):
                file_id = message.document.file_id

        if not file_id:
            msg = bot.send_message(
                message.chat.id,
                "❗ Iltimos, video yuboring (oddiy video, fayl sifatida emas):"
            )
            bot.register_next_step_handler(msg, flow_receive_episode_video)
            return

        data = temp_data.get(message.from_user.id)
        if not data:
            bot.send_message(message.chat.id, "❌ Session topilmadi.")
            return

        anime_code = data.get("anime_code", "?")
        ep_num = data.get("episode_num", 0)

        loading = bot.send_message(message.chat.id, "⏳ Video saqlanmoqda...")

        db.add_episode(anime_code, ep_num, file_id)
        test = db.get_episode(anime_code, ep_num)

        if not test:
            bot.edit_message_text("❌ Qism saqlanmadi!", loading.chat.id, loading.message_id)
            return

        temp_data.pop(message.from_user.id, None)
        eps = db.get_episode_numbers(anime_code)
        bot.edit_message_text(
            f"✅ <code>{anime_code}</code> — <b>{ep_num}-qism</b> qo'shildi!\n\n📋 Jami qismlar: {eps}",
            loading.chat.id,
            loading.message_id,
            parse_mode="HTML"
        )

    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Xatolik:\n{e}")


# ── Media handlers ────────────────────────────────────────────────────────────


@bot.message_handler(content_types=["photo"])
def handle_photo(message):
    pass


@bot.message_handler(content_types=["video", "document"])
def handle_video_standalone(message):
    if not is_admin(message.from_user.id):
        return
    if message.content_type == "video" and message.video:
        bot.reply_to(
            message,
            f"📋 *file\\_id:*\n\n`{message.video.file_id}`",
            parse_mode="MarkdownV2",
        )
    elif message.content_type == "document" and message.document:
        mime = message.document.mime_type or ""
        if mime.startswith("video/"):
            bot.reply_to(
                message,
                f"📋 *file\\_id:*\n\n`{message.document.file_id}`",
                parse_mode="MarkdownV2",
            )


# ── Text → anime code lookup ──────────────────────────────────────────────────


@bot.message_handler(func=lambda m: True)
def handle_code(message):
    db.add_user(message.from_user.id)

    if not check_subscription(message.from_user.id):
        bot.reply_to(
            message,
            "🛑 *Botdan foydalanish uchun avval kanalimizga obuna bo'lishingiz kerak\\.*\n\n"
            "Obuna bo'lgach, *Tasdiqlash* tugmasini bosing\\.",
            reply_markup=subscription_markup(),
            parse_mode="MarkdownV2",
        )
        return

    code = message.text.strip().upper()
    anime = db.get_anime(code)

    if not anime:
        bot.reply_to(
            message,
            f"❌ *{md(code)}* kodi topilmadi\\.\n\n"
            "Kodlar uchun kanalimizga a'zo bo'ling: https://t\\.me/Animelaar\\_kanal",
            parse_mode="MarkdownV2",
        )
        return

    eps = db.get_episode_numbers(code)
    if not eps:
        bot.reply_to(
            message,
            f"⏳ *{md(anime['title'])}* uchun hali qismlar yuklanmagan\\.\nTez orada qo'shiladi\\!",
            parse_mode="MarkdownV2",
        )
        return

    caption = f"🎬 *{md(anime['title'])}*\n\n📌 Qaysi qismni ko'rmoqchisiz? Pastdagi tugmani bosing\\!"
    markup = episode_buttons_markup(code)

    if anime.get("poster_file_id"):
        bot.send_photo(
            message.chat.id,
            anime["poster_file_id"],
            caption=caption,
            reply_markup=markup,
            parse_mode="MarkdownV2",
        )
    else:
        bot.send_message(
            message.chat.id,
            caption,
            reply_markup=markup,
            parse_mode="MarkdownV2",
        )


# ── Callback buttons ──────────────────────────────────────────────────────────


@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    uid = call.from_user.id

    # ── Subscription check ──────────────────────────────────────────────────
    if call.data == "check_sub":
        if check_subscription(uid):
            bot.answer_callback_query(call.id, "✅ Obuna tasdiqlandi!")
            bot.edit_message_text(
                "✅ Xush kelibsiz\\! Anime kodini yuboring\\.",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                parse_mode="MarkdownV2",
            )
        else:
            bot.answer_callback_query(
                call.id, "❌ Siz hali kanalga obuna bo'lmagansiz!", show_alert=True
            )
        return

    # ── Episode send (user) ─────────────────────────────────────────────────
    if call.data.startswith("ep_"):
        # Format: ep_{anime_code}_{ep_num}
        # Use rfind so codes containing "_" are handled safely
        rest = call.data[3:]  # strip leading "ep_"
        sep = rest.rfind("_")
        if sep == -1:
            bot.answer_callback_query(call.id, "❌ Xatolik.", show_alert=True)
            return
        anime_code = rest[:sep]
        try:
            ep_num = int(rest[sep + 1 :])
        except ValueError:
            bot.answer_callback_query(call.id, "❌ Xatolik.", show_alert=True)
            return

        episode = db.get_episode(anime_code, ep_num)
        if episode:
            bot.answer_callback_query(call.id)
            anime = db.get_anime(anime_code)
            title = anime["title"] if anime else anime_code
            bot.send_video(
                call.message.chat.id,
                episode["file_id"],
                caption=f"🎬 {md(title)} — {md(str(ep_num))}\\-qism",
                parse_mode="MarkdownV2",
            )
        else:
            bot.answer_callback_query(
                call.id, "❌ Bu qism hali yuklanmagan.", show_alert=True
            )
        return

    # ── Main menu callbacks ─────────────────────────────────────────────────
    if call.data == "search":
        bot.answer_callback_query(call.id)
        bot.send_message(
            call.message.chat.id,
            "🔍 Anime kodini yuboring\\.\nKodlar: https://t\\.me/Animelaar\\_kanal",
            parse_mode="MarkdownV2",
        )
        return
    if call.data == "guide":
        bot.answer_callback_query(call.id)
        bot.send_message(
            call.message.chat.id,
            "🗳 *Qo'llanma*\n\n"
            "1\\. Anime kodini yuboring\n"
            "2\\. Poster va qismlar tugmalari chiqadi\n"
            "3\\. Kerakli qism tugmasini bosing \\— video keladi\\!",
            parse_mode="MarkdownV2",
        )
        return
    if call.data == "cabinet":
        bot.answer_callback_query(call.id)
        bot.send_message(
            call.message.chat.id, "⚙️ *Kabinet* — tez orada\\!", parse_mode="MarkdownV2"
        )
        return
    if call.data == "shorts":
        bot.answer_callback_query(call.id)
        bot.send_message(
            call.message.chat.id, "🔴 *Shorts* — tez orada\\!", parse_mode="MarkdownV2"
        )
        return
    if call.data == "ads":
        bot.answer_callback_query(call.id)
        bot.send_message(
            call.message.chat.id,
            "📢 *Reklama* — kanal admini bilan bog'laning\\.",
            parse_mode="MarkdownV2",
        )
        return

    # ── Admin-only below ────────────────────────────────────────────────────
    if not is_admin(uid):
        bot.answer_callback_query(call.id, "⛔ Ruxsat yo'q.", show_alert=True)
        return

    if call.data == "admin_back":
        bot.answer_callback_query(call.id)
        bot.send_message(
            call.message.chat.id,
            "🔐 *Admin Panel*",
            reply_markup=admin_panel_markup(),
            parse_mode="MarkdownV2",
        )
        return

    # ── Admin: add anime ────────────────────────────────────────────────────
    if call.data == "admin_add_anime":
        bot.answer_callback_query(call.id)
        flow_ask_anime_code(call.message)
        return

    # ── Admin: add episode — show anime list ────────────────────────────────
    if call.data == "admin_add_ep":
        bot.answer_callback_query(call.id)
        animes = db.get_all_animes()
        if not animes:
            bot.send_message(
                call.message.chat.id,
                "📭 Avval anime qo'shing\\!",
                reply_markup=admin_panel_markup(),
                parse_mode="MarkdownV2",
            )
            return
        bot.send_message(
            call.message.chat.id,
            "📼 *Qism qo'shish* — animeni tanlang:",
            reply_markup=anime_select_markup("addep"),
            parse_mode="MarkdownV2",
        )
        return

    # ── Admin: episode anime selected ───────────────────────────────────────
    if call.data.startswith("addep_"):
        anime_code = call.data[6:]
        bot.answer_callback_query(call.id)
        flow_ask_episode_num(call.message, anime_code)
        return

    # ── Admin: delete anime — show list ─────────────────────────────────────
    if call.data == "admin_del_anime":
        bot.answer_callback_query(call.id)
        animes = db.get_all_animes()
        if not animes:
            bot.send_message(call.message.chat.id, "📭 Bazada hech qanday anime yo'q.")
            return
        bot.send_message(
            call.message.chat.id,
            "🗑 *O'chirish uchun animeni tanlang:*\n_\\(barcha qismlari ham o'chadi\\)_",
            reply_markup=anime_select_markup("delanim"),
            parse_mode="MarkdownV2",
        )
        return

    # ── Admin: delete selected anime ────────────────────────────────────────
    if call.data.startswith("delanim_"):
        anime_code = call.data[8:]
        removed = db.remove_anime(anime_code)
        if removed:
            bot.answer_callback_query(call.id, f"✅ {anime_code} o'chirildi.")
            animes = db.get_all_animes()
            if animes:
                bot.edit_message_reply_markup(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    reply_markup=anime_select_markup("delanim"),
                )
            else:
                bot.edit_message_text(
                    "📭 Bazada hech qanday anime qolmadi\\.",
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    parse_mode="MarkdownV2",
                )
        else:
            bot.answer_callback_query(call.id, "❌ Anime topilmadi.", show_alert=True)
        return

    # ── Admin: stats ────────────────────────────────────────────────────────
    if call.data == "admin_stats":
        bot.answer_callback_query(call.id)
        stats = db.get_stats()
        bot.send_message(
            call.message.chat.id,
            f"📊 *Statistika*\n\n"
            f"🎌 Animelar: `{stats['total_animes']}`\n"
            f"🎬 Qismlar: `{stats['total_episodes']}`\n"
            f"👥 Foydalanuvchilar: `{stats['total_users']}`",
            reply_markup=admin_panel_markup(),
            parse_mode="MarkdownV2",
        )
        return


# ── PID lock (prevents two instances) ────────────────────────────────────────

PID_FILE = os.path.join(os.path.dirname(__file__), "bot.pid")


def _acquire_pid_lock() -> None:
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE) as f:
                old_pid = int(f.read().strip())
            os.kill(old_pid, 0)
            logger.error(
                "Bot allaqachon PID %s bilan ishlayapti. Chiqilmoqda.", old_pid
            )
            sys.exit(1)
        except (ProcessLookupError, ValueError):
            logger.warning("Eski PID fayl topildi, tozalanmoqda.")

    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))

    atexit.register(_release_pid_lock)
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, _signal_handler)


def _release_pid_lock() -> None:
    try:
        os.remove(PID_FILE)
    except FileNotFoundError:
        pass


def _signal_handler(signum, frame):
    logger.info("Signal %s qabul qilindi, chiqilmoqda...", signum)
    _release_pid_lock()
    sys.exit(0)


# ── Run ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    _acquire_pid_lock()
    keep_alive()

    try:
        bot.delete_webhook(drop_pending_updates=True)
        logger.info("Webhook tozalandi.")
    except Exception as e:
        logger.warning("Webhook tozalashda xato: %s", e)

    logger.info("Bot ishga tushmoqda...")

    while True:
        try:
            bot.infinity_polling(
                logger_level=logging.WARNING,
                skip_pending=True,
                timeout=30,
                long_polling_timeout=25,
                restart_on_change=False,
            )
        except telebot.apihelper.ApiTelegramException as e:
            if e.error_code == 409:
                logger.error("409 Conflict — 15 soniya kutilmoqda...")
                bot.stop_polling()
                time.sleep(15)
            else:
                logger.error("Telegram API xatosi: %s — 5 soniya kutilmoqda.", e)
                time.sleep(5)
        except Exception as e:
            logger.error("Kutilmagan xato: %s — 5 soniya kutilmoqda.", e)
            time.sleep(5)
