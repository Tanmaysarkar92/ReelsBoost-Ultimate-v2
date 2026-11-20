
import sqlite3
import unittest
from pathlib import Path

from services.usage import reserve_reel_slot


class UsageTests(unittest.TestCase):
    def setUp(self):
        folder = Path(__file__).resolve().parent.parent / "project_tests"
        folder.mkdir(exist_ok=True)

        self.db = folder / f"usage_test_{self._testMethodName}.db"

        if self.db.exists():
            self.db.unlink()

        with sqlite3.connect(self.db) as conn:
            conn.executescript("""
                CREATE TABLE users (
                    id INTEGER PRIMARY KEY,
                    plan TEXT,
                    subscription_status TEXT
                );

                CREATE TABLE usage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    reels_used INTEGER DEFAULT 0,
                    reels_limit INTEGER DEFAULT 0,
                    month TEXT DEFAULT '',
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

    def tearDown(self):
        try:
            self.db.unlink(missing_ok=True)
        except PermissionError:
            print(f"Cleanup pending: {self.db.name}")

    def add_user(self, user_id, plan, status):
        with sqlite3.connect(self.db) as conn:
            conn.execute(
                """
                INSERT INTO users (id, plan, subscription_status)
                VALUES (?, ?, ?)
                """,
                (user_id, plan, status),
            )

    def test_monthly_limit(self):
        self.add_user(1, "free", "inactive")

        results = [
            reserve_reel_slot(1, db_path=self.db)
            for _ in range(4)
        ]

        self.assertEqual(
            [r["allowed"] for r in results],
            [True, True, True, False],
        )
        self.assertEqual(
            results[3]["error"],
            "monthly_limit_reached",
        )
        print("PASS: Free plan allows 3 reels, blocks the 4th.")

    def test_paid_plan_requires_active_subscription(self):
        self.add_user(1, "pro", "inactive")

        result = reserve_reel_slot(1, db_path=self.db)

        self.assertFalse(result["allowed"])
        self.assertEqual(result["error"], "subscription_inactive")
        print("PASS: Inactive paid subscription is blocked.")

    def test_unknown_user_is_blocked(self):
        result = reserve_reel_slot(999, db_path=self.db)

        self.assertFalse(result["allowed"])
        self.assertEqual(result["error"], "user_not_found")
        print("PASS: Unknown user is blocked.")

    def test_new_month_gets_fresh_usage(self):
        self.add_user(1, "free", "inactive")

        with sqlite3.connect(self.db) as conn:
            conn.execute(
                """
                INSERT INTO usage
                    (user_id, reels_used, reels_limit, month)
                VALUES (1, 3, 3, '2026-08')
                """
            )

        result = reserve_reel_slot(1, db_path=self.db)

        self.assertTrue(result["allowed"])
        self.assertEqual(result["used"], 1)
        self.assertEqual(result["remaining"], 2)
        print("PASS: New month starts fresh usage.")

    
    def test_concurrent_requests_respect_monthly_limit(self):
        from concurrent.futures import ThreadPoolExecutor

        self.add_user(1, "free", "inactive")

        with ThreadPoolExecutor(max_workers=8) as executor:
            results = list(
                executor.map(
                    lambda _: reserve_reel_slot(1, db_path=self.db),
                    range(10),
                )
            )

        allowed = sum(result["allowed"] for result in results)
        blocked = sum(not result["allowed"] for result in results)

        self.assertEqual(allowed, 3)
        self.assertEqual(blocked, 7)

        print("PASS: Concurrent requests respect the 3-reel limit.")

if __name__ == "__main__":
    unittest.main(verbosity=2)
