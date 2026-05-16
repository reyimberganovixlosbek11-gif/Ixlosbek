import sqlite3

def init_db():
    conn = sqlite3.connect("anime.db")
    cursor = conn.cursor()
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
    conn.close()

def add_user(user_id):
    conn = sqlite3.connect("anime.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    conn.commit()
    conn.close()

def add_anime(code, title, poster_file_id):
    conn = sqlite3.connect("anime.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO animes (code, title, poster_file_id) VALUES (?, ?, ?)", (code, title, poster_file_id))
    conn.commit()
    conn.close()

def get_anime(code):
    conn = sqlite3.connect("anime.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM animes WHERE code = ?", (code,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_all_animes():
    conn = sqlite3.connect("anime.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM animes")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def remove_anime(code):
    conn = sqlite3.connect("anime.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM animes WHERE code = ?", (code,))
    cursor.execute("DELETE FROM episodes WHERE anime_code = ?", (code,))
    changes = conn.total_changes
    conn.commit()
    conn.close()
    return changes > 0

def add_episode(anime_code, episode_num, file_id):
    conn = sqlite3.connect("anime.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO episodes (anime_code, episode_num, file_id) VALUES (?, ?, ?)", (anime_code, episode_num, file_id))
    conn.commit()
    conn.close()

def get_episode(anime_code, episode_num):
    conn = sqlite3.connect("anime.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM episodes WHERE anime_code = ? AND episode_num = ?", (anime_code, episode_num))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_episode_numbers(anime_code):
    conn = sqlite3.connect("anime.db")
    cursor = conn.cursor()
    cursor.execute("SELECT episode_num FROM episodes WHERE anime_code = ? ORDER BY episode_num ASC", (anime_code,))
    rows = cursor.fetchall()
    conn.close()
    return [r[0] for r in rows]

def get_stats():
    conn = sqlite3.connect("anime.db")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM animes")
    total_animes = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM episodes")
    total_episodes = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]
    conn.close()
    return {
        "total_animes": total_animes,
        "total_episodes": total_episodes,
        "total_users": total_users
    }
