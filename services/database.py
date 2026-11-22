import sqlite3
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
SAAS_DB_PATH = BASE_DIR / "saas.db"


def get_connection():
    return sqlite3.connect(SAAS_DB_PATH)


def init_database():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT DEFAULT '',
            email TEXT UNIQUE NOT NULL,
            phone TEXT DEFAULT '',
            plan TEXT DEFAULT 'free',
            subscription_status TEXT DEFAULT 'inactive',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            plan TEXT DEFAULT 'free',
            status TEXT DEFAULT 'inactive',
            start_date TIMESTAMP,
            end_date TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            reels_used INTEGER DEFAULT 0,
            reels_limit INTEGER DEFAULT 0,
            month TEXT DEFAULT '',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS content (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            content_type TEXT DEFAULT 'property_reel',
            title TEXT DEFAULT '',
            file_path TEXT DEFAULT '',
            status TEXT DEFAULT 'created',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS social_accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            platform TEXT DEFAULT '',
            account_name TEXT DEFAULT '',
            account_id TEXT DEFAULT '',
            access_token TEXT DEFAULT '',
            connected INTEGER DEFAULT 0,
            connected_at TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    conn.commit()
    conn.close()
if __name__ == "__main__":
    init_database()
    print("SaaS database initialized successfully.")
