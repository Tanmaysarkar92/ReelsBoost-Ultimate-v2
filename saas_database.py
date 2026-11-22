
from contextlib import contextmanager

from services.database import get_connection, init_database


@contextmanager
def get_db():
    init_database()
    connection = get_connection()

    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def init_db():
    init_database()


if __name__ == "__main__":
    init_db()
    print("ReelsBoost SaaS database initialized.")

