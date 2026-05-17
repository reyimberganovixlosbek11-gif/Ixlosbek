
def flow_receive_episode_video(message):
    try:
        if message.content_type != "video":
            msg = bot.send_message(
                message.chat.id,
                "❗ Iltimos, video yuboring:"
            )
            bot.register_next_step_handler(msg, flow_receive_episode_video)
            return

        data = temp_data.get(message.from_user.id)

        if not data:
            bot.send_message(
                message.chat.id,
                "❌ Session topilmadi."
            )
            return

        anime_code = data.get("anime_code")
        ep_num = data.get("episode_num")

        loading = bot.send_message(
            message.chat.id,
            "⏳ Video saqlanmoqda..."
        )

        file_id = message.video.file_id

        db.add_episode(anime_code, ep_num, file_id)

        test = db.get_episode(anime_code, ep_num)

        if not test:
            bot.edit_message_text(
                "❌ Qism saqlanmadi!",
                loading.chat.id,
                loading.message_id
            )
            return

        temp_data.pop(message.from_user.id, None)

        bot.edit_message_text(
            f"✅ {anime_code} — {ep_num}-qism qo'shildi!",
            loading.chat.id,
            loading.message_id
        )

    except Exception as e:
        bot.send_message(
            message.chat.id,
            f"❌ Xatolik:\n{e}"
        )
