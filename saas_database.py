
from services.database import get_db, init_database


def init_db():
    init_database()


if __name__ == "__main__":
    init_db()
    print("ReelsBoost PostgreSQL database initialized.")


