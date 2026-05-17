
def add_episode(anime_code, episode_num, file_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO episodes(anime_code, episode_num, file_id) VALUES(?,?,?)",
        (anime_code, episode_num, file_id)
    )

    conn.commit()
    conn.close()
