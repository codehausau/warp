import os
import pathlib
import threading
import time
import unittest

import psycopg2
from psycopg2 import Error


TEST_DSN = os.environ.get("WARP_TEST_POSTGRES_DSN")
REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
SCHEMA_SQL = (REPO_ROOT / "warp" / "sql" / "schema.sql").read_text(encoding="utf8")
SAMPLE_DATA_SQL = (REPO_ROOT / "warp" / "sql" / "sample_data.sql").read_text(encoding="utf8")


@unittest.skipUnless(TEST_DSN, "WARP_TEST_POSTGRES_DSN is required for PostgreSQL concurrency tests")
class BookingConcurrencyTests(unittest.TestCase):

    def setUp(self):
        self._reset_database()

    def _connect(self):
        conn = psycopg2.connect(TEST_DSN)
        conn.autocommit = False
        return conn

    def _reset_database(self):
        conn = psycopg2.connect(TEST_DSN)
        conn.autocommit = True
        try:
            with conn.cursor() as cur:
                cur.execute("DROP SCHEMA IF EXISTS public CASCADE;")
                cur.execute("CREATE SCHEMA public;")
                cur.execute(SCHEMA_SQL)
                cur.execute(SAMPLE_DATA_SQL)
        finally:
            conn.close()

    def _run_conflicting_insert(self, sql, params):
        outcome = {"status": "blocked", "error": None}
        finished = threading.Event()

        def worker():
            conn = self._connect()
            try:
                with conn.cursor() as cur:
                    cur.execute(sql, params)
                    conn.commit()
                outcome["status"] = "committed"
            except Error as err:
                conn.rollback()
                outcome["status"] = "failed"
                outcome["error"] = err
            finally:
                conn.close()
                finished.set()

        thread = threading.Thread(target=worker)
        thread.start()
        return thread, finished, outcome

    def test_conflicting_seat_booking_blocks_and_then_fails(self):
        conn1 = self._connect()
        try:
            with conn1.cursor() as cur:
                cur.execute(
                    "INSERT INTO book (login, sid, fromts, tots) VALUES (%s, %s, %s, %s)",
                    ("user1", 1, 1000, 2000),
                )

            thread, finished, outcome = self._run_conflicting_insert(
                "INSERT INTO book (login, sid, fromts, tots) VALUES (%s, %s, %s, %s)",
                ("user2", 1, 1500, 2500),
            )
            try:
                time.sleep(0.3)
                self.assertFalse(finished.is_set(), "conflicting insert should wait for the first transaction")
                conn1.commit()
                thread.join(timeout=5)
            finally:
                if thread.is_alive():
                    thread.join(timeout=1)

            self.assertEqual(outcome["status"], "failed")
            self.assertEqual(outcome["error"].pgcode, "23P01")
        finally:
            conn1.close()

    def test_conflicting_user_booking_in_same_zone_group_blocks_and_then_fails(self):
        conn1 = self._connect()
        try:
            with conn1.cursor() as cur:
                cur.execute(
                    "INSERT INTO book (login, sid, fromts, tots) VALUES (%s, %s, %s, %s)",
                    ("user1", 1, 1000, 2000),
                )

            thread, finished, outcome = self._run_conflicting_insert(
                "INSERT INTO book (login, sid, fromts, tots) VALUES (%s, %s, %s, %s)",
                ("user1", 28, 1500, 2500),
            )
            try:
                time.sleep(0.3)
                self.assertFalse(finished.is_set(), "same-user conflict should wait for the first transaction")
                conn1.commit()
                thread.join(timeout=5)
            finally:
                if thread.is_alive():
                    thread.join(timeout=1)

            self.assertEqual(outcome["status"], "failed")
            self.assertEqual(outcome["error"].pgcode, "23P01")
        finally:
            conn1.close()


if __name__ == "__main__":
    unittest.main()
