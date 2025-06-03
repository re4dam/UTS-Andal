import sqlite3
import json
from config import DATABASE_NAME


def get_db_connection():
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row  # Memungkinkan akses kolom berdasarkan nama
    return conn


def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Tabel untuk menyimpan halaman yang telah di-crawl
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS pages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        url TEXT UNIQUE NOT NULL,
        title TEXT,
        last_crawled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")

    # Tabel untuk menyimpan konten teks halaman (dipisah untuk efisiensi jika konten besar)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS page_content (
        page_id INTEGER PRIMARY KEY,
        text_content TEXT,
        FOREIGN KEY (page_id) REFERENCES pages (id)
    )""")

    # Tabel untuk menyimpan rute dari seed ke halaman
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS paths (
        page_id INTEGER PRIMARY KEY,
        path_data TEXT, -- JSON string dari list of tuples [(url, link_text), ...]
        FOREIGN KEY (page_id) REFERENCES pages (id)
    )""")

    # Tabel indeks terbalik sederhana
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS inverted_index (
        keyword TEXT NOT NULL,
        page_id INTEGER NOT NULL,
        PRIMARY KEY (keyword, page_id),
        FOREIGN KEY (page_id) REFERENCES pages (id)
    )""")

    # Tabel untuk antrian crawling (jika crawling dilakukan secara bertahap/background)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS crawl_queue (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        url TEXT UNIQUE NOT NULL,
        depth INTEGER NOT NULL,
        path_to_here TEXT NOT NULL, -- JSON string dari list of tuples [(url, link_text), ...]
        status TEXT DEFAULT 'pending' -- pending, processing, done, error
    )""")

    # --- NEW TABLE FOR CONFIG SETTINGS ---
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS config_settings (
        setting_name TEXT PRIMARY KEY NOT NULL,
        setting_value TEXT
    )""")

    # Inisialisasi SEED_URL jika belum ada di config_settings
    # Ambil nilai default dari config.py saat pertama kali diinisialisasi
    from config import SEED_URL as DEFAULT_SEED_URL_FROM_CONFIG
    cursor.execute("INSERT OR IGNORE INTO config_settings (setting_name, setting_value) VALUES (?, ?)",
                   ("SEED_URL", DEFAULT_SEED_URL_FROM_CONFIG))

    conn.commit()
    conn.close()


def get_setting(setting_name):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT setting_value FROM config_settings WHERE setting_name = ?", (setting_name,))
    result = cursor.fetchone()
    conn.close()
    return result["setting_value"] if result else None

def set_setting(setting_name, setting_value):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO config_settings (setting_name, setting_value) VALUES (?, ?)",
                   (setting_name, setting_value))
    conn.commit()
    conn.close()

# Panggil init_db() sekali saat aplikasi pertama kali dijalankan atau saat setup
if __name__ == "__main__":
    print("Initializing database...")
    init_db()
    print("Database initialized.")