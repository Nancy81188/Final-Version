"""2.9.64: company files marked by an older version are upgraded again when the upgrade code changes
("no such column: i.payment_account" on files made before 2.9.54)."""
import sqlite3
import tempfile
import unittest
from pathlib import Path

import database
from database import Database


class UpgradeMarkerTest(unittest.TestCase):
    def test_marker_follows_the_upgrade_code(self):
        self.assertTrue(Database.STARTUP_SCHEMA_VERSION.startswith("4-"))
        self.assertEqual(Database.STARTUP_SCHEMA_VERSION, database._schema_fingerprint())

    def test_old_file_missing_a_column_is_upgraded(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "ecologe_2024.db"
            db = Database(path); db.initialize_if_needed("secret")
            # make it look like a file from 2.9.53: no payment_account column, marked with the old hand-made number "4"
            with sqlite3.connect(path) as conn:
                conn.execute("ALTER TABLE invoices DROP COLUMN payment_account")
                conn.execute("UPDATE app_settings SET value='4' WHERE key='startup_schema_version'")
            with sqlite3.connect(path) as conn:
                conn.row_factory = sqlite3.Row
                conn.execute("UPDATE app_settings SET value=? WHERE key='startup_schema_signature'", (Database._startup_schema_signature(conn),))
            old = Database(path)
            with self.assertRaisesRegex(sqlite3.OperationalError, "payment_account"): old.list_invoices()
            reopened = Database(path); reopened.initialize_if_needed("other")
            self.assertEqual(reopened.list_invoices(), [])
            with reopened.connect() as conn:
                marker = conn.execute("SELECT value FROM app_settings WHERE key='startup_schema_version'").fetchone()[0]
            self.assertEqual(marker, Database.STARTUP_SCHEMA_VERSION)


if __name__ == "__main__":
    unittest.main()
