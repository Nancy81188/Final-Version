"""Runtime plumbing for the installed program (2.9.41).

- Where the data lives, and the one-time safe rename of the main data file
  (saber_accounting_v0_7.db -> saber_accounting.db).
- The private link between the window and its built-in data service: a free port chosen by
  Windows and a secret key generated at every start, so no other program can use the service.
- Only one copy of Saber open per Windows user (a second start brings the first window forward).
- An error log in <data folder>/logs/saber.log, so problems on a client PC can be found.
"""
from __future__ import annotations

import json
import logging
import logging.handlers
import os
import sqlite3
import sys
import threading
from contextlib import closing
from pathlib import Path

log = logging.getLogger("saber")

MAIN_DATABASE_NAME = "saber_accounting.db"
OLD_MAIN_DATABASE_NAME = "saber_accounting_v0_7.db"
KEY_HEADER = "X-Saber-Key"

# Filled in by run_desktop.py once the private data service is running.
LOCAL_URL: str | None = None
LOCAL_KEY: str | None = None


def data_dir() -> Path:
    override = os.environ.get("SABER_DATA_DIR")
    return Path(override) if override else Path.home() / "SaberAccounting"


# ------------------------------------------------------------------ logging
def setup_logging(folder: Path | None = None) -> Path:
    """Write warnings and errors (with the full details) to logs/saber.log; 5 x 1 MB kept."""
    folder = Path(folder or data_dir()) / "logs"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "saber.log"
    root = logging.getLogger()
    if not any(getattr(h, "_saber", False) for h in root.handlers):
        handler = logging.handlers.RotatingFileHandler(path, maxBytes=1_000_000, backupCount=5, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [%(threadName)s] %(name)s: %(message)s"))
        handler._saber = True
        root.addHandler(handler)
        root.setLevel(logging.INFO)

    def excepthook(kind, value, tb):
        log.critical("Unhandled error", exc_info=(kind, value, tb))
        sys.__excepthook__(kind, value, tb)

    def thread_hook(args):
        log.error("Unhandled error in thread %s", getattr(args.thread, "name", "?"),
                  exc_info=(args.exc_type, args.exc_value, args.exc_traceback))

    sys.excepthook = excepthook
    threading.excepthook = thread_hook
    return path


# ------------------------------------------------------------------ main data file
def _registry_points_to(registry: Path, old: Path, new: Path) -> bool:
    """Make companies/companies.json use the new main file name. Returns True when it changed."""
    if not registry.is_file():
        return False
    data = json.loads(registry.read_text(encoding="utf-8"))
    changed = False
    old_resolved = old.resolve()
    for company in data.get("companies", []):
        for year in company.get("years", []):
            value = year.get("database")
            if value and Path(value).resolve() == old_resolved:
                year["database"] = str(new.resolve()); changed = True
    if changed:
        backup = registry.with_name(registry.name + ".before-2.9.41")
        if not backup.exists():
            backup.write_bytes(registry.read_bytes())
        temporary = registry.with_name(registry.name + ".tmp")
        temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporary, registry)
    return changed


def main_database_path(folder: Path | None = None) -> Path:
    """The main data file, renamed once from the old 0.7 name without any risk to the data.

    The old file is copied with SQLite's own backup (safe even with an open WAL), the copy is
    checked, and only then is it put in place. The old file is kept as
    saber_accounting_v0_7.db.before-2.9.41. If anything fails, the old file keeps being used.
    """
    folder = Path(folder or data_dir())
    new, old = folder / MAIN_DATABASE_NAME, folder / OLD_MAIN_DATABASE_NAME
    registry = folder / "companies" / "companies.json"
    if not new.exists() and not old.exists():
        return new
    if new.exists():
        # Finish an interrupted rename: the company list must not point at the old name.
        try: _registry_points_to(registry, old, new)
        except Exception: log.exception("Could not update the company list to %s", new.name)
        if old.exists(): _retire_old_file(old)
        return new
    temporary = folder / (MAIN_DATABASE_NAME + ".copying")
    try:
        if temporary.exists(): temporary.unlink()
        # Connections are closed explicitly: Windows cannot rename a file that is still open.
        with closing(sqlite3.connect(old)) as source, closing(sqlite3.connect(temporary)) as target:
            source.backup(target)
            result = target.execute("PRAGMA integrity_check").fetchone()[0]
            if result != "ok": raise RuntimeError(f"copy check failed: {result}")
            copied = target.execute("SELECT COUNT(*) FROM sqlite_master").fetchone()[0]
            original = source.execute("SELECT COUNT(*) FROM sqlite_master").fetchone()[0]
            if copied != original: raise RuntimeError("copy is missing tables")
            target.execute("PRAGMA journal_mode=DELETE")  # one self-contained file before it is put in place
        os.replace(temporary, new)
        _registry_points_to(registry, old, new)
        log.info("Main data file renamed: %s -> %s", old.name, new.name)
    except Exception:
        log.exception("Main data file was not renamed; the old file %s is still used", old.name)
        try:
            if temporary.exists(): temporary.unlink()
        except OSError: pass
        if new.exists():
            # The copy is complete but the company list could not be updated: keep using the old file.
            try: new.replace(folder / (MAIN_DATABASE_NAME + ".unused"))
            except OSError: pass
        return old
    _retire_old_file(old)
    return new


def _retire_old_file(old: Path) -> None:
    """Keep the old file under a name nothing opens any more (best effort: it may still be open)."""
    target = old.with_name(old.name + ".before-2.9.41")
    try:
        if not target.exists():
            old.replace(target)
            for suffix in ("-wal", "-shm"):
                extra = old.with_name(old.name + suffix)
                if extra.exists():
                    try: extra.unlink()
                    except OSError: pass
    except OSError:
        log.warning("Old data file %s is still in use; it will be set aside next time", old.name)


# ------------------------------------------------------------------ one copy open
class SingleInstance:
    """Hold an OS file lock for as long as the program runs. A second copy cannot take it."""

    def __init__(self, folder: Path | None = None):
        self.folder = Path(folder or data_dir()); self.folder.mkdir(parents=True, exist_ok=True)
        self.lock_path = self.folder / ".saber.lock"
        self.window_path = self.folder / ".saber.window"
        self._handle = None

    def acquire(self) -> bool:
        handle = open(self.lock_path, "a+b")
        try:
            if sys.platform == "win32":
                import msvcrt
                handle.seek(0); msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            handle.close(); return False
        self._handle = handle
        return True

    def release(self) -> None:
        if self._handle is not None:
            try: self._handle.close()
            finally: self._handle = None
            try: self.window_path.unlink()
            except OSError: pass

    def remember_window(self, tk_root) -> None:
        """Note the main window so a second start can bring it to the front."""
        try: self.window_path.write_text(str(int(tk_root.wm_frame(), 16)), encoding="ascii")
        except Exception: log.warning("Could not note the main window", exc_info=True)

    def bring_existing_to_front(self) -> bool:
        if sys.platform != "win32": return False
        try:
            import ctypes
            hwnd = int(self.window_path.read_text(encoding="ascii").strip())
            user32 = ctypes.windll.user32
            if not user32.IsWindow(hwnd): return False
            user32.ShowWindow(hwnd, 9)  # SW_RESTORE
            return bool(user32.SetForegroundWindow(hwnd))
        except Exception:
            return False


INSTANCE: SingleInstance | None = None
