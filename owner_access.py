"""2.9.101: the owner of Saber Accounting (the seller) - a hidden account and the licence of each installation.

- The owner signs in on any installation with OWNER_USERNAME and the owner password. The account is not in the client's
  list of users, the client's administrator cannot change, disable or delete it, and it never expires.
- The owner sets the licence of the installation (valid until a date). When the licence has expired, only the owner can
  sign in, to renew it; the client sees "The licence expired on ... - contact Saber for Audit".
- The owner password is kept only as a one-way fingerprint (scrypt); the owner can change it on an installation.
The owner's own entries still appear in the audit trail - an audit trail without gaps is the point of it."""
from __future__ import annotations

import json

from database_common import display_date, hash_password, iso_date, utcnow, verify_password

OWNER_USERNAME = "saber-owner"
OWNER_HASH = "a1c69c4121b5808a566b1776cbab18ef:1b2e6064c313785f4170e872556baa1b54b0661d68965a8b76902f49aec2973550b26752b14b9ef4868281d6cada081c34ff1bafae21382d08f26f0b66126a9c"
SELLER = "Saber for Audit"
HASH_KEY, LICENCE_KEY = "owner_password_hash", "licence_valid_until"


def is_owner_name(username):
    return str(username or "").strip().casefold() == OWNER_USERNAME


def is_owner(user):
    try: return bool(user) and is_owner_name(user["username"]) and bool(user["hidden"])
    except (KeyError, IndexError, TypeError): return False


def migrate(connection):
    columns = {row[1] for row in connection.execute("PRAGMA table_info(users)")}
    if columns and "hidden" not in columns: connection.execute("ALTER TABLE users ADD COLUMN hidden INTEGER NOT NULL DEFAULT 0")


def _setting(connection, key):
    row = connection.execute("SELECT value FROM app_settings WHERE key=?", (key,)).fetchone()
    return row[0] if row else None


def _put(connection, key, value):
    connection.execute("INSERT INTO app_settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))


def check_password(connection, password):
    try: return verify_password(str(password or ""), _setting(connection, HASH_KEY) or OWNER_HASH)
    except (ValueError, AttributeError): return False


def owner_row(connection):
    """The hidden owner user (made the first time the owner signs in on this installation)."""
    migrate(connection)
    row = connection.execute("SELECT * FROM users WHERE lower(username)=?", (OWNER_USERNAME,)).fetchone()
    if row is None:
        connection.execute("INSERT INTO users(username,password_hash,role,language,active,expires_at,hidden,created_at) VALUES(?,?,?,?,1,NULL,1,?)",
                           (OWNER_USERNAME, "!", "admin", "en", utcnow()))
    else:
        connection.execute("UPDATE users SET role='admin',active=1,expires_at=NULL,hidden=1 WHERE id=?", (row["id"],))
    return connection.execute("SELECT * FROM users WHERE lower(username)=?", (OWNER_USERNAME,)).fetchone()


def licence(connection):
    """{"valid_until": ISO date or None, "expired": bool, "days": days left or None}."""
    from datetime import date
    until = _setting(connection, LICENCE_KEY)
    if not until: return {"valid_until": None, "expired": False, "days": None}
    days = (date.fromisoformat(until) - date.today()).days
    return {"valid_until": until, "expired": days < 0, "days": days}


def licence_message(connection):
    info = licence(connection)
    if info["expired"]: return f"The licence of Saber Accounting expired on {display_date(info['valid_until'])} - contact {SELLER} to renew it."
    return None


def set_licence(connection, valid_until, owner_id):
    value = iso_date(valid_until, "Licence valid until") if str(valid_until or "").strip() else ""
    _put(connection, LICENCE_KEY, value)
    connection.execute("INSERT INTO audit_log(user_id,action,entity,details,created_at) VALUES(?,?,?,?,?)",
                       (owner_id, "licence", "installation", json.dumps({"valid_until": value or None}), utcnow()))
    return licence(connection)


def set_password(connection, current, new, owner_id):
    if not check_password(connection, current): raise PermissionError("The current owner password is not correct")
    if len(str(new or "")) < 10: raise ValueError("The owner password must have at least 10 characters")
    _put(connection, HASH_KEY, hash_password(str(new)))
    connection.execute("INSERT INTO audit_log(user_id,action,entity,details,created_at) VALUES(?,?,?,?,?)",
                       (owner_id, "change", "owner_password", "{}", utcnow()))
    return True
