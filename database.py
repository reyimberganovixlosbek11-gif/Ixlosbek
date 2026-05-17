import sqlite3

DB_NAME = "anime.db"

def connect():
    return sqlite3.connect(DB_NAME, check_same_thread=False)

conn = connect()
cursor = conn.cursor()

def init_db():
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS animes (
        code TEXT PRIMARY KEY,
        title TEXT,
        poster_file_id TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS episodes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        anime_code TEXT,
        episode_num INTEGER,
        file_id TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY
    )
    """)

    conn.commit()

def add_user(user_id):
    cursor.execute("INSERT OR IGNORE INTO users(user_id) VALUES(?)", (user_id,))
    conn.commit()

def add_anime(code, title, poster_file_id):
    cursor.execute(
        "INSERT OR REPLACE INTO animes(code, title, poster_file_id) VALUES(?,?,?)",
        (code, title, poster_file_id)
    )
    conn.commit()

def get_anime(code):
    cursor.execute("SELECT * FROM animes WHERE code=?", (code,))
    row = cursor.fetchone()
    if not row:
        return None
    return {
        "code": row[0],
        "title": row[1],
        "poster_file_id": row[2]
    }

def get_all_animes():
    cursor.execute("SELECT * FROM animes")
    rows = cursor.fetchall()
    return [
        {"code": r[0], "title": r[1], "poster_file_id": r[2]}
        for r in rows
    ]

def remove_anime(code):
    cursor.execute("DELETE FROM animes WHERE code=?", (code,))
    cursor.execute("DELETE FROM episodes WHERE anime_code=?", (code,))
    conn.commit()
    return True

def add_episode(anime_code, episode_num, file_id):
    conn2 = sqlite3.connect(DB_NAME)
    cur2 = conn2.cursor()
    cur2.execute(
        "INSERT INTO episodes(anime_code, episode_num, file_id) VALUES(?,?,?)",
        (anime_code, episode_num, file_id)
    )
    conn2.commit()
    conn2.close()

def get_episode(anime_code, episode_num):
    cursor.execute(
        "SELECT file_id FROM episodes WHERE anime_code=? AND episode_num=?",
        (anime_code, episode_num)
    )
    row = cursor.fetchone()
    if not row:
        return None
    return {"file_id": row[0]}

def get_episode_numbers(anime_code):
    cursor.execute(
        "SELECT episode_num FROM episodes WHERE anime_code=? ORDER BY episode_num",
        (anime_code,)
    )
    return [r[0] for r in cursor.fetchall()]

def get_stats():
    cursor.execute("SELECT COUNT(*) FROM animes")
    total_animes = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM episodes")
    total_episodes = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]

    return {
        "total_animes": total_animes,
        "total_episodes": total_episodes,
        "total_users": total_users
    }