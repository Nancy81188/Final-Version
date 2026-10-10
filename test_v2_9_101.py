"""2.9.101: hidden owner account and licence, upgrade of older files, tables that show their columns in full."""
import socket
import tempfile
import threading
import time
import unittest
from pathlib import Path

import owner_access
from database_common import hash_password


class OwnerAccountTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import server
        from client import ApiClient
        cls.saved_hash = owner_access.OWNER_HASH
        owner_access.OWNER_HASH = hash_password("Owner-Test-2026")
        cls.folder = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        probe = socket.socket(); probe.bind(("127.0.0.1", 0)); port = probe.getsockname()[1]; probe.close()
        threading.Thread(target=server.run_server, kwargs={"host": "127.0.0.1", "port": port, "database": str(Path(cls.folder.name) / "o.db"),
                                                           "admin_password": "Admin-2025!"}, daemon=True).start()
        cls.url = f"http://127.0.0.1:{port}"
        for _ in range(200):
            try: ApiClient(cls.url).login("admin", "Admin-2025!"); break
            except Exception: time.sleep(0.05)

    @classmethod
    def tearDownClass(cls):
        owner_access.OWNER_HASH = cls.saved_hash
        import gc; gc.collect(); cls.folder.cleanup()

    def api(self, name, password):
        from client import ApiClient
        api = ApiClient(self.url); info = api.login(name, password); return api, info

    def test_owner_hidden_licence_and_password(self):
        admin, info = self.api("admin", "Admin-2025!")
        self.assertFalse(info.get("owner"))
        with self.assertRaises(Exception): self.api(owner_access.OWNER_USERNAME, "wrong-password")
        owner, info = self.api(owner_access.OWNER_USERNAME, "Owner-Test-2026")
        self.assertTrue(info["owner"]); self.assertEqual(info["role"], "admin")
        # not in the client's list, cannot be edited or taken as a name
        names = [u["username"] for u in admin.users()]
        self.assertNotIn(owner_access.OWNER_USERNAME, names)
        with self.assertRaises(Exception): admin.save_user({"username": owner_access.OWNER_USERNAME, "password": "x" * 8, "role": "admin", "language": "en"})
        # only the owner sets the licence
        with self.assertRaises(Exception): admin.set_licence("01-01-2020")
        owner.set_licence("01-01-2020")
        with self.assertRaises(Exception) as caught: self.api("admin", "Admin-2025!")
        self.assertIn("licence", str(caught.exception).lower())
        with self.assertRaises(Exception): admin.users()  # the open session stops too
        owner, _ = self.api(owner_access.OWNER_USERNAME, "Owner-Test-2026")  # the owner still signs in, to renew
        self.assertTrue(owner.set_licence("31-12-2099")["valid_until"].startswith("2099"))
        self.api("admin", "Admin-2025!")
        owner.set_licence("")
        # the owner password can be changed on this installation
        with self.assertRaises(Exception): owner.set_owner_password("bad", "Another-Owner-1")
        owner.set_owner_password("Owner-Test-2026", "Another-Owner-1")
        self.api(owner_access.OWNER_USERNAME, "Another-Owner-1")


class UpgradeFingerprintTest(unittest.TestCase):
    def test_new_tables_change_the_upgrade_fingerprint(self):
        import database, approvals
        source = database._schema_fingerprint.__code__.co_names + database._schema_fingerprint.__code__.co_consts
        self.assertIn("approvals", source); self.assertIn("audit_chain", source)
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as folder:
            db = database.Database(str(Path(folder) / "u.db")); db.initialize_if_needed("secret12345")
            with db.connect() as connection:
                connection.execute("DROP TABLE held_journal_lines")
                connection.execute("UPDATE app_settings SET value='old' WHERE key='startup_schema_version'")
            db2 = database.Database(str(Path(folder) / "u.db")); db2.initialize_if_needed("secret12345")
            self.assertEqual(approvals.pending(db2), [])


class ColumnFitTest(unittest.TestCase):
    def test_columns_show_title_and_fill_width(self):
        import tkinter as tk
        from tkinter import ttk
        import desktop_common  # noqa: F401 - installs the column fit
        try: root = tk.Tk()
        except tk.TclError: self.skipTest("no display")
        try:
            root.geometry("900x300")
            tree = ttk.Treeview(root, columns=("a", "b", "c"), show="headings"); tree.pack(fill="both", expand=True)
            tree.heading("a", text="A very long column title here"); tree.column("a", width=40)
            tree.heading("b", text="B"); tree.column("b", width=60)
            tree.heading("c", text="Hidden"); tree.column("c", width=0, minwidth=0, stretch=False)
            tree.insert("", "end", values=("x", "10-10-2026 long value", "z"))
            for _ in range(5): root.update(); time.sleep(0.05)
            from tkinter import font as tkfont
            self.assertGreaterEqual(tree.column("a", "width"), 150)
            self.assertEqual(tree.column("c", "width"), 0)
            self.assertGreater(tree.column("a", "width") + tree.column("b", "width"), 800)  # fills the table
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()


class NewItemDetailsTest(unittest.TestCase):
    def test_ask_settings_and_set_details(self):
        import inventory
        from database import Database
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as folder:
            db = Database(Path(folder) / "i.db"); db.initialize("secret12345")
            self.assertFalse(inventory.settings(db)["ask_brand"])
            inventory.save_settings(db, {"currency": "USD", "method": "average", "ask_category": True, "ask_brand": True}, 1)
            s = inventory.settings(db); self.assertTrue(s["ask_category"] and s["ask_brand"]); self.assertFalse(s["ask_subcategory"])
            item = inventory.save_item(db, {"name": "Steel bolt M8", "unit": "unit"}, 1) if hasattr(inventory, "save_item") else None
            item_id = item["id"] if isinstance(item, dict) else int(item)
            inventory.set_item_details(db, [{"id": item_id, "category": "Hardware", "brand": "Bosch"}], 1)
            with db.connect() as c: row = c.execute("SELECT category,brand FROM inventory_items WHERE id=?", (item_id,)).fetchone()
            self.assertEqual((row["category"], row["brand"]), ("Hardware", "Bosch"))
            self.assertIn("Hardware", [x["name"] for x in inventory.list_categories(db)["categories"]])
            self.assertIn("Bosch", inventory.brands(db))
