"""Chart of accounts tools (2.9.66): which accounts are used, delete accounts that have no transactions (one or many,
any kind: clients, suppliers, expenses...), move all the transactions of an account to another one, or transfer its
balance with a journal voucher.

Part of the Database class: Database inherits from AccountsStore."""
from __future__ import annotations

import re

from database_common import *  # noqa: F401,F403
from database_common import _soft_iso  # noqa: F401

# text columns that hold an account code (table, column)
ACCOUNT_COLUMNS = (
    ("invoices", "supplier_account"), ("invoices", "vat_account"), ("invoices", "expense_account"), ("invoices", "expense_no_vat_account"), ("invoices", "payment_account"),
    ("document_cases", "supplier_account"), ("document_cases", "expense_account"), ("document_cases", "vat_account"),
    ("inventory_items", "cost_account"),
    ("payments", "cash_account"), ("payments", "party_account"), ("payments", "commission_account"), ("payments", "exchange_account"),
    ("expenses", "expense_account"), ("expenses", "expense_without_vat_account"), ("expenses", "vat_account"), ("expenses", "payment_account"),
    ("employees", "salary_account"), ("employees", "payable_account"),
    ("payroll_settings", "salary_account"), ("payroll_settings", "salary_payable_account"), ("payroll_settings", "payroll_tax_account"), ("payroll_settings", "nssf_payable_account"),
    ("budgets", "account_code"), ("fixed_assets", "asset_account"), ("fixed_assets", "depreciation_account"), ("fixed_assets", "accumulated_account"),
    ("bank_statement_lines", "account_code"),
)
LABELS = {"invoices": "invoice", "document_cases": "document case", "inventory_items": "inventory item", "payments": "payment", "expenses": "expense",
          "employees": "employee", "payroll_settings": "payroll setting", "budgets": "budget", "fixed_assets": "fixed asset", "bank_statement_lines": "bank statement line"}
# tables that make a customer / supplier "used"
PARTY_TABLES = (("invoices", "party_id"), ("payments", "party_id"), ("journal_lines", "party_id"), ("stock_documents", "party_id"),
                ("party_documents", "party_id"), ("projects", "party_id"))
SCOPES = {"all": (), "clients": ("411",), "suppliers": ("401", "403", "404", "408"), "expenses": ("6",), "income": ("7",),
          "cash_bank": ("5",), "other_payables": ("46",)}


def _code(value):
    return str(value or "").split(" - ", 1)[0].strip()


class AccountsStore:
    def _system_account_codes(self):
        """Accounts of the official Lebanese chart and the ones the program needs: never deleted."""
        import chart_extra
        codes = {row[0] for row in LEBANESE_ACCOUNTS} | {str(v) for v in DEFAULT_LEBANESE_ACCOUNTS.values()}
        codes |= {row[0] for row in getattr(chart_extra, "EXTRA_ACCOUNTS", ())}
        codes |= {EXPENSE_ACCOUNT_9, VAT_ACCOUNT_9, EXPENSE_NO_VAT_ACCOUNT_9}
        def collect(code):
            for constant in code.co_consts:
                if isinstance(constant, str) and re.fullmatch(r"\d{3,9}(\.\d+)?", constant): codes.add(constant)
                elif hasattr(constant, "co_consts"): collect(constant)
        collect(type(self)._initialize.__code__)
        return codes

    def _existing_columns(self, db):
        result = []
        tables = {row["name"] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        for table, column in ACCOUNT_COLUMNS:
            if table in tables and column in {r["name"] for r in db.execute(f"PRAGMA table_info({table})")}: result.append((table, column))
        return result

    def _party_used(self, db, party_id):
        tables = {row["name"] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        for table, column in PARTY_TABLES:
            if table in tables and column in {r["name"] for r in db.execute(f"PRAGMA table_info({table})")}:
                if db.execute(f"SELECT 1 FROM {table} WHERE {column}=? LIMIT 1", (party_id,)).fetchone(): return table
        if db.execute("SELECT 1 FROM inventory_items WHERE CAST(supplier_id AS INTEGER)=? LIMIT 1", (party_id,)).fetchone(): return "inventory_items"
        return None

    def account_usage(self, codes=None):
        """{code: {"name", "type", "lines", "children", "references": [...], "party": name or None, "system": bool, "free": bool}}"""
        system = self._system_account_codes()
        with self.connect() as db:
            accounts = {r["code"]: dict(r) for r in db.execute("SELECT a.id,a.code,a.name_en,a.type,(SELECT COUNT(*) FROM accounts c WHERE c.parent_id=a.id) children FROM accounts a")}
            wanted = [c for c in (codes or accounts) if c in accounts]
            lines = {r["account_id"]: r["n"] for r in db.execute("SELECT account_id,COUNT(*) n FROM journal_lines GROUP BY account_id")}
            references = {}
            for table, column in self._existing_columns(db):
                for row in db.execute(f"SELECT {column} code,COUNT(*) n FROM {table} WHERE {column} IS NOT NULL AND {column}<>'' GROUP BY {column}"):
                    code = _code(row["code"])
                    if code: references.setdefault(code, []).append(f'{row["n"]} {LABELS[table]}(s)')
            parties = {}
            for row in db.execute("SELECT id,name,account_number FROM parties WHERE account_number IS NOT NULL AND account_number<>''"):
                parties.setdefault(row["account_number"], []).append(dict(row))
            result = {}
            for code in wanted:
                account = accounts[code]; owners = parties.get(code, [])
                used_party = next((f'{p["name"]} has {self._party_used(db, p["id"])} records' for p in owners if self._party_used(db, p["id"])), None)
                info = {"code": code, "name": account["name_en"], "type": account["type"], "lines": lines.get(account["id"], 0), "children": account["children"],
                        "references": references.get(code, []), "party": ", ".join(p["name"] for p in owners) or None, "system": code in system}
                reasons = []
                if info["system"]: reasons.append("official chart account")
                if info["lines"]: reasons.append(f'{info["lines"]} journal line(s)')
                if info["children"]: reasons.append(f'{info["children"]} sub-account(s)')
                if info["references"]: reasons.append("used by " + ", ".join(info["references"]))
                if used_party: reasons.append(used_party)
                info["reasons"] = reasons; info["free"] = not reasons
                result[code] = info
        return result

    def unused_accounts(self, scope="all"):
        prefixes = SCOPES.get(scope, (str(scope),) if str(scope).isdigit() else ())
        return [info for code, info in sorted(self.account_usage().items())
                if info["free"] and (not prefixes or any(code.startswith(p) for p in prefixes))]

    def delete_accounts(self, codes, user_id):
        """Delete accounts without transactions. A customer / supplier file that only holds that account is deleted with it."""
        codes = [_code(c) for c in codes or [] if _code(c)]
        if not codes: raise ValueError("Choose the accounts to delete")
        usage = self.account_usage(codes); deleted = []; kept = []
        with self.connect() as db:
            for code in codes:
                info = usage.get(code)
                if not info: kept.append({"code": code, "reason": "not found"}); continue
                if not info["free"]: kept.append({"code": code, "reason": "; ".join(info["reasons"])}); continue
                parties = [dict(r) for r in db.execute("SELECT id,name FROM parties WHERE account_number=?", (code,))]
                for party in parties: db.execute("DELETE FROM parties WHERE id=?", (party["id"],))
                db.execute("DELETE FROM accounts WHERE code=?", (code,))
                db.execute("INSERT INTO audit_log(user_id,action,entity,details,created_at) VALUES(?,?,?,?,?)",
                           (user_id, "delete", "account", json.dumps({"code": code, "name": info["name"], "parties": [p["name"] for p in parties]}, ensure_ascii=False), utcnow()))
                deleted.append({"code": code, "name": info["name"], "parties": [p["name"] for p in parties]})
        return {"deleted": deleted, "kept": kept}

    def _account_row(self, db, code, label):
        row = db.execute("SELECT * FROM accounts WHERE code=?", (_code(code),)).fetchone()
        if not row: raise ValueError(f"{label} account {_code(code) or '(empty)'} was not found")
        return row

    def move_account(self, source, target, user_id, merge_party=False):
        """Every transaction of `source` moves to `target` (journal lines and the documents that name the account).
        With merge_party, the customer / supplier of `source` is merged into the one of `target` and deleted."""
        with self.connect() as db:
            old = self._account_row(db, source, "From"); new = self._account_row(db, target, "To")
            if old["id"] == new["id"]: raise ValueError("Choose two different accounts")
            if db.execute("SELECT 1 FROM accounts WHERE parent_id=? LIMIT 1", (new["id"],)).fetchone() and len(new["code"]) < 9:
                raise ValueError(f"{new['code']} is a heading account (it has sub-accounts): choose a detail account")
            days = [r["entry_date"] for r in db.execute("SELECT DISTINCT e.entry_date FROM journal_lines j JOIN journal_entries e ON e.id=j.entry_id WHERE j.account_id=?", (old["id"],))]
        for day in days: self._assert_period_open(day)
        with self.connect() as db:
            moved = db.execute("UPDATE journal_lines SET account_id=? WHERE account_id=?", (new["id"], old["id"])).rowcount
            documents = 0
            for table, column in self._existing_columns(db):
                documents += db.execute(f"UPDATE {table} SET {column}=? WHERE {column}=? OR {column} LIKE ?", (new["code"], old["code"], old["code"] + " - %")).rowcount
            merged = None
            old_party = db.execute("SELECT * FROM parties WHERE account_number=? ORDER BY id LIMIT 1", (old["code"],)).fetchone()
            new_party = db.execute("SELECT * FROM parties WHERE account_number=? ORDER BY id LIMIT 1", (new["code"],)).fetchone()
            if merge_party and old_party and new_party and old_party["id"] != new_party["id"]:
                tables = {row["name"] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                for table, column in PARTY_TABLES:
                    if table in tables: db.execute(f"UPDATE {table} SET {column}=? WHERE {column}=?", (new_party["id"], old_party["id"]))
                db.execute("UPDATE inventory_items SET supplier_id=? WHERE CAST(supplier_id AS INTEGER)=?", (str(new_party["id"]), old_party["id"]))
                db.execute("DELETE FROM parties WHERE id=?", (old_party["id"],)); merged = old_party["name"]
            elif old_party:
                db.execute("UPDATE parties SET account_number=? WHERE account_number=?", (new["code"], old["code"]))
            db.execute("INSERT INTO audit_log(user_id,action,entity,details,created_at) VALUES(?,?,?,?,?)",
                       (user_id, "move", "account", json.dumps({"from": old["code"], "to": new["code"], "lines": moved, "documents": documents, "merged_party": merged}, ensure_ascii=False), utcnow()))
        return {"from": old["code"], "to": new["code"], "lines": moved, "documents": documents, "merged_party": merged}

    def transfer_balance(self, source, target, date, user_id, description=""):
        """Transfer the balance of `source` (on `date`, per currency) to `target` with a journal voucher; history stays."""
        day = iso_date(date, "Transfer date")
        with self.connect() as db:
            old = self._account_row(db, source, "From"); new = self._account_row(db, target, "To")
            if old["id"] == new["id"]: raise ValueError("Choose two different accounts")
            balances = [dict(r) for r in db.execute("""SELECT e.currency,SUM(CAST(j.debit AS REAL))-SUM(CAST(j.credit AS REAL)) balance
                FROM journal_lines j JOIN journal_entries e ON e.id=j.entry_id WHERE j.account_id=? AND
                (CASE WHEN e.entry_date GLOB '??-??-????' THEN substr(e.entry_date,7,4)||'-'||substr(e.entry_date,4,2)||'-'||substr(e.entry_date,1,2) ELSE e.entry_date END)<=?
                GROUP BY e.currency""", (old["id"], day))]
        vouchers = []
        for row in balances:
            amount = Decimal(str(row["balance"] or 0)).quantize(Decimal("0.01"))
            if not amount: continue
            side_new, side_old = ("D", "C") if amount > 0 else ("C", "D")
            text = description or f"Transfer of balance {old['code']} -> {new['code']}"
            saved = self.save_journal_voucher({"entry_date": display_date(day), "description": text, "currency": row["currency"], "voucher_type": "06"},
                                              [{"account_code": new["code"], "side": side_new, "amount": str(abs(amount))},
                                               {"account_code": old["code"], "side": side_old, "amount": str(abs(amount))}], user_id)
            vouchers.append({"currency": row["currency"], "amount": float(amount), "voucher": saved["voucher"]["entry_number"]})
        if not vouchers: raise ValueError(f"{old['code']} has no balance on {display_date(day)}")
        return {"from": old["code"], "to": new["code"], "vouchers": vouchers}
