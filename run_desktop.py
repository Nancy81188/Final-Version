"""Start Saber Accounting: one copy per Windows user, its own private data service, an error log."""
import json
import logging
import secrets
import sys
import threading
import tkinter as tk
from tkinter import messagebox, simpledialog
from urllib.request import Request, urlopen

import app_runtime
from desktop import main
from server import run_server

log = logging.getLogger("saber.start")


def local_server_ready(url=None, key=None):
    url = url or app_runtime.LOCAL_URL; key = key or app_runtime.LOCAL_KEY
    if not url: return False
    try:
        request = Request(url + "/health", headers={app_runtime.KEY_HEADER: key or ""})
        with urlopen(request, timeout=0.5) as response:
            result = json.loads(response.read().decode("utf-8"))
        return result.get("application") == "Saber Accounting"
    except Exception:
        return False


def _ask_initial_password():
    root = tk.Tk(); root.withdraw()
    try:
        while True:
            password = simpledialog.askstring("Saber Accounting", "Create the initial admin password (at least 10 characters):", show="*", parent=root)
            if password is None: return None
            if len(password) >= 10: return password
    finally: root.destroy()


def start_local_server(database=None):
    """Start the private per-PC data service invisibly inside the desktop app.

    Windows picks a free port (no clash with other programs) and a new secret key is made at every
    start; only this window knows it, so no other program on the PC can read or change the data.
    Returns False when the user cancelled the first-time admin password.
    """
    database = database or app_runtime.main_database_path()
    database.parent.mkdir(parents=True, exist_ok=True)
    initial_password = None
    if not database.exists():
        initial_password = _ask_initial_password()
        if initial_password is None: return False
    key = secrets.token_urlsafe(32); ready = threading.Event(); chosen = {}

    def on_ready(port):
        chosen["port"] = port; ready.set()

    def serve():
        try:
            run_server(host="127.0.0.1", port=0, database=str(database), admin_password=initial_password, local_key=key, on_ready=on_ready)
        except Exception:
            log.exception("The data service stopped")
            ready.set()

    thread = threading.Thread(target=serve, name="SaberLocalDataService", daemon=True)
    thread.start()
    if not ready.wait(60) or "port" not in chosen:
        raise RuntimeError("Saber Accounting could not start its local data service. See the log file in the SaberAccounting\\logs folder.")
    app_runtime.LOCAL_URL = f"http://127.0.0.1:{chosen['port']}"; app_runtime.LOCAL_KEY = key
    if initial_password:
        from backup_service import backup_all
        try: backup_all(database)
        except Exception: log.exception("First backup failed")
    return True


def _tell(message, error=False):
    root = tk.Tk(); root.withdraw()
    try: (messagebox.showerror if error else messagebox.showinfo)("Saber Accounting", message, parent=root)
    finally: root.destroy()


def run():
    app_runtime.setup_logging()
    instance = app_runtime.SingleInstance()
    if not instance.acquire():
        if not instance.bring_existing_to_front():
            _tell("Saber Accounting is already open on this computer.")
        return 0
    app_runtime.INSTANCE = instance
    try:
        if not start_local_server(): return 0
        main()
        return 0
    except Exception as exc:
        log.exception("Saber Accounting stopped")
        _tell(f"Saber Accounting could not continue:\n{exc}\n\nThe details are in the log file (SaberAccounting\\logs\\saber.log).", error=True)
        return 1
    finally:
        instance.release()


if __name__ == "__main__":
    sys.exit(run())
