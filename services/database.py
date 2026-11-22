
import os
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SAAS_DB_PATH = Path(
    os.getenv("SAAS_DATABASE_PATH", str(BASE_DIR / "saas.db"))
)


def get_connection():
    conn = sqlite3.connect(SAAS_DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_database():
    conn = get_connection()
    try:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT DEFAULT '',
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT DEFAULT '',
            phone TEXT DEFAULT '',
            plan TEXT DEFAULT 'free',
            subscription_status TEXT DEFAULT 'inactive',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            plan TEXT NOT NULL DEFAULT 'free',
            status TEXT NOT NULL DEFAULT 'inactive',
            provider TEXT,
            provider_subscription_id TEXT,
            current_period_end TIMESTAMP,
            start_date TIMESTAMP,
            end_date TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            feature TEXT DEFAULT 'reel',
            quantity INTEGER NOT NULL DEFAULT 1,
            period TEXT DEFAULT '',
            reels_used INTEGER DEFAULT 0,
            reels_limit INTEGER DEFAULT 0,
            month TEXT DEFAULT '',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );

        CREATE INDEX IF NOT EXISTS idx_usage_user_period
        ON usage(user_id, period);

        CREATE TABLE IF NOT EXISTS content (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            content_type TEXT DEFAULT 'property_reel',
            title TEXT DEFAULT '',
            file_path TEXT DEFAULT '',
            status TEXT DEFAULT 'created',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS social_accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            platform TEXT DEFAULT '',
            account_name TEXT DEFAULT '',
            account_id TEXT DEFAULT '',
            access_token TEXT DEFAULT '',
            connected INTEGER DEFAULT 0,
            connected_at TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );
        """)
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    init_database()
    print("SaaS database initialized successfully.")

