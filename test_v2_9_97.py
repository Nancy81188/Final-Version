"""2.9.97: money is added exactly (no floating-point drift) in the trial balance and the ledger reports."""
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from database import Database


class ExactMoneyTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory(ignore_cleanup_errors=True); self.addCleanup(folder.cleanup)
        self.db = Database(Path(folder.name) / "m.db"); self.db.initialize("secret12345"); self.addCleanup(self.db.release)
        self.db.save_exchange_rate({"date_from": "01-01-2026", "date_to": "31-12-2026", "from_currency": "USD", "to_currency": "LBP", "rate": "89500"}, 1)

    def test_many_small_amounts_add_exactly(self):
        # 3,000 vouchers of USD 0.10 / 0.20 / 0.30 on different days: the float sum would be 1199.9999999998 or 1200.0000000002
        for i in range(3000):
            amount = ("0.10", "0.20", "0.30")[i % 3]
            self.db.save_journal_voucher({"entry_date": f"{i % 28 + 1:02d}-{i % 12 + 1:02d}-2026", "description": "small", "currency": "USD", "voucher_type": "01"},
                                         [{"account_code": "531", "debit": amount}, {"account_code": "101", "credit": amount}], 1)
        rows = {r["code"]: r for r in self.db.trial_balance(to_date="31-12-2026")}
        self.assertEqual(rows["531"]["debit"], 600.0)            # exactly, not 599.9999999999
        self.assertEqual(rows["531"]["closing_balance"], 600.0)
        self.assertEqual(rows["101"]["credit"], 600.0)
        self.assertEqual(rows["531"]["lbp_debit"], 600 * 89500.0)
        self.assertEqual(sum(Decimal(str(r["debit"])) - Decimal(str(r["credit"])) for r in rows.values()), Decimal("0"))
        with self.db.connect() as db:  # the exact sum is available to every query
            self.assertEqual(db.execute("SELECT DSUM(debit) FROM journal_lines").fetchone()[0], 600.0)
            self.assertEqual(db.execute("SELECT DSUM(1) FROM journal_lines").fetchone()[0], 6000)  # whole numbers stay whole
            self.assertIsNone(db.execute("SELECT DSUM(debit) FROM journal_lines WHERE 0").fetchone()[0])  # like SUM on no rows


class VatByPartyTest(unittest.TestCase):
    """Lebanese practice (as in the user's VAT 140 utility): every customer / supplier has its own VAT account, closed at the
    quarter end into the closing account of its ledger."""

    def setUp(self):
        folder = tempfile.TemporaryDirectory(ignore_cleanup_errors=True); self.addCleanup(folder.cleanup)
        self.db = Database(Path(folder.name) / "v.db"); self.db.initialize("secret12345"); self.addCleanup(self.db.release)
        self.db.save_exchange_rate({"date_from": "01-01-2026", "date_to": "31-12-2026", "from_currency": "USD", "to_currency": "LBP", "rate": "89500"}, 1)
        import vat_ledgers
        self.vat_ledgers = vat_ledgers
        self.old_supplier = self.db.save_party({"name": "Old Supplier", "account_category": "supplier", "currency": "USD"}, 1)  # before the rule
        vat_ledgers.save_settings(self.db, {"enabled": True})

    def balance(self, code, to_date="31-03-2026"):
        rows = [r for r in self.db.trial_balance(to_date=to_date, account_code=code, include_subaccounts=False)]
        return sum(Decimal(str(r["lbp_debit"])) - Decimal(str(r["lbp_credit"])) for r in rows)

    def test_own_vat_account_and_closing(self):
        made = self.vat_ledgers.create_vat_accounts(self.db)
        self.assertEqual(made, 1)  # the supplier saved before the rule
        supplier = self.db.save_party({"name": "Diwan", "account_category": "supplier", "currency": "USD"}, 1)
        client = self.db.save_party({"name": "Client A", "account_category": "client", "currency": "USD"}, 1)
        assets = self.db.save_party({"name": "PC Shop", "account_category": "asset_supplier", "currency": "USD"}, 1)
        own = lambda p, prefix: prefix + p["account_number"][5:]
        sup_vat, cli_vat, ast_vat = own(supplier, "44210"), own(client, "44270"), own(assets, "44213")
        self.assertEqual((supplier["account_number"][:5], sup_vat[:5], len(sup_vat)), ("40110", "44210", 9))
        sale = self.db.create_manual_invoice({"invoice_date": "10-02-2026", "party_name": "Client A", "kind": "sales", "currency": "USD", "status": "posted"},
                                             [{"description": "Service", "quantity": 1, "unit_price": 1000, "vat_rate": 11}], 1)
        self.db.create_manual_invoice({"invoice_date": "12-02-2026", "party_name": "Diwan", "kind": "purchases", "currency": "USD", "status": "posted"},
                                      [{"description": "Paper", "quantity": 1, "unit_price": 400, "vat_rate": 11}], 1)
        self.db.create_manual_invoice({"invoice_date": "15-02-2026", "party_name": "PC Shop", "kind": "assets", "currency": "USD", "status": "posted",
                                       "supplier_account": assets["account_number"], "expense_account": "2245"},
                                      [{"description": "Laptop", "quantity": 1, "unit_price": 200, "vat_rate": 11}], 1)
        self.assertEqual(self.balance(cli_vat), Decimal(-110 * 89500))   # output VAT on the client's own account
        self.assertEqual(self.balance(sup_vat), Decimal(44 * 89500))     # input VAT on the supplier's own account
        self.assertEqual(self.balance(ast_vat), Decimal(22 * 89500))     # VAT on the asset supplier's own account
        self.assertEqual(self.balance("4427"), 0); self.assertEqual(self.balance("44210"), 0)  # nothing on the general accounts
        self.assertTrue(self.vat_ledgers.test_vat_accounts(self.db)["ok"])
        # quarter end: saving the return closes the VAT automatically (closing by ledger, then the settlement)
        import vat_return
        saved = vat_return.save_return(self.db, 2026, 1, 1)
        self.assertTrue(saved["settlement"]["closing_voucher"])
        for code in (cli_vat, sup_vat, ast_vat, "44270", "44210", "44263"):
            self.assertEqual(self.balance(code), 0, code)  # every VAT account of the quarter is closed
        self.assertEqual(self.balance("4425"), Decimal(-(110 - 44 - 22) * 89500))  # VAT payable to the Ministry of Finance
        closing = [l for l in saved["settlement"]["closing_lines"] if l["account_code"] == "44270"]
        self.assertEqual(closing[0]["amount"], str(110 * 89500))
        rows = self.db.trial_balance(to_date="31-03-2026")  # one row per account and currency
        self.assertEqual(sum(Decimal(str(r["lbp_debit"])) - Decimal(str(r["lbp_credit"])) for r in rows), 0)

    def test_rule_off_keeps_the_general_account_and_test_finds_gaps(self):
        report = self.vat_ledgers.test_vat_accounts(self.db)
        self.assertFalse(report["ok"]); self.assertEqual(report["problems"][0]["type"], "missing")  # the old supplier has no VAT account yet
        self.vat_ledgers.save_settings(self.db, {"enabled": False})
        self.db.create_manual_invoice({"invoice_date": "10-02-2026", "party_name": "Client B", "kind": "sales", "currency": "USD", "status": "posted"},
                                      [{"description": "S", "quantity": 1, "unit_price": 100, "vat_rate": 11}], 1)
        self.assertEqual(self.balance("4427"), Decimal(-11 * 89500))
        with self.assertRaises(ValueError): self.vat_ledgers.save_settings(self.db, {"ledgers": [{"ledger": "40110", "vat": "4421"}]})


class AuditTrailTest(unittest.TestCase):
    """Tamper-evident audit trail and the audit report."""

    def setUp(self):
        import os
        folder = tempfile.TemporaryDirectory(ignore_cleanup_errors=True); self.addCleanup(folder.cleanup)
        self.folder = Path(folder.name)
        old = os.environ.get("SABER_AUDIT_KEY"); os.environ["SABER_AUDIT_KEY"] = str(self.folder / "audit.key")
        self.addCleanup(lambda: os.environ.__setitem__("SABER_AUDIT_KEY", old) if old else os.environ.pop("SABER_AUDIT_KEY", None))
        self.db = Database(self.folder / "a.db"); self.db.initialize("secret12345")
        self.db.save_exchange_rate({"date_from": "01-01-2026", "date_to": "31-12-2026", "from_currency": "USD", "to_currency": "LBP", "rate": "89500"}, 1)

    def test_chain_refuses_changes_and_detects_outside_edits(self):
        import sqlite3, audit_chain
        for name in ("A", "B", "C"): self.db.save_party({"name": name, "account_category": "client", "currency": "USD"}, 1)
        self.assertTrue(audit_chain.verify(self.db)["ok"])
        with self.db.connect() as c:
            with self.assertRaises(sqlite3.DatabaseError): c.execute("UPDATE audit_log SET details='x'")
            with self.assertRaises(sqlite3.DatabaseError): c.execute("DELETE FROM audit_log")
        self.db.release()
        raw = sqlite3.connect(str(self.folder / "a.db"))  # someone edits the file with another tool
        raw.execute("DROP TRIGGER audit_log_no_delete"); raw.execute("DELETE FROM audit_log WHERE id=(SELECT MIN(id)+1 FROM audit_log)"); raw.commit(); raw.close()
        result = audit_chain.verify(Database(self.folder / "a.db"))
        self.assertFalse(result["ok"]); self.assertIn("removed or inserted", result["broken"][0]["problem"])

    def test_audit_report(self):
        import audit_report, sqlite3
        self.db.save_journal_voucher({"entry_date": "05-01-2026", "description": "Cash withdrawal", "currency": "USD", "voucher_type": "01"},
                                     [{"account_code": "6262", "debit": "500"}, {"account_code": "531", "credit": "500"}], 1)
        with self.db.connect() as c:  # an entry dated January but entered in March (back-dated), on a Sunday night
            entry = c.execute("SELECT id FROM journal_entries ORDER BY id DESC LIMIT 1").fetchone()["id"]
            c.execute("UPDATE journal_entries SET created_at='2026-03-01T21:30:00+00:00' WHERE id=?", (entry,))
        report = audit_report.build(self.db, "01-01-2026", "31-03-2026")
        s = report["summary"]
        self.assertTrue(s["integrity_ok"]); self.assertEqual((s["late"], s["admin"], s["outside_hours"], s["manual_cash"]), (1, 1, 1, 1))
        late = report["sections"][3]["rows"][0]; self.assertEqual(late[-1], 55)  # 55 days after its date
        self.assertEqual(report["sections"][5]["rows"][0][-1], "Sun 23:30")  # Beirut winter time (UTC+2) of 21:30 UTC on Sunday 1 March



class AttachmentViewerTest(unittest.TestCase):
    """2.9.97: an attached PDF is seen inside the program (pages, next / previous)."""

    def pdf(self, pages=2):
        from reportlab.pdfgen import canvas
        import io
        buffer = io.BytesIO(); c = canvas.Canvas(buffer)
        for page in range(pages): c.drawString(100, 750, f"Invoice page {page + 1}"); c.showPage()
        c.save(); return buffer.getvalue()

    def test_view_pdf_pages(self):
        try:
            import tkinter as tk
            root = tk.Tk()
        except Exception as exc: self.skipTest(f"no screen: {exc}")
        self.addCleanup(root.destroy)
        import desktop_attachments
        content = self.pdf(2)
        window = desktop_attachments.show_document(root, "SJ20251714.pdf", content)
        root.update()
        self.assertEqual(len(window._pages), 2)
        window._go(1); root.update()
        self.assertTrue(window._label.cget("text").startswith("Page 2 of 2"))
        items = [{"id": 1, "file_name": "a.pdf", "size": len(content)}, {"id": 2, "file_name": "b.pdf", "size": len(content)}]
        opened = []
        listing = desktop_attachments.attachments_window(root, "PUR-1", items, lambda record: opened.append(record["id"]) or content)
        listing._view(); root.update()
        self.assertEqual(opened, [1])  # the selected (first) document is shown
        with self.assertRaises(ValueError): desktop_attachments.page_images("notes.txt", b"hello")



class CancelPurchaseTest(unittest.TestCase):
    """2.9.97: a purchase saved with a wrong total is cancelled from the Purchases screen (reversing entry, kept for the audit)."""

    def test_cancel_wrong_purchase(self):
        folder = tempfile.TemporaryDirectory(ignore_cleanup_errors=True); self.addCleanup(folder.cleanup)
        db = Database(Path(folder.name) / "p.db"); db.initialize("secret12345"); self.addCleanup(db.release)
        db.save_exchange_rate({"date_from": "01-01-2026", "date_to": "31-12-2026", "from_currency": "USD", "to_currency": "LBP", "rate": "89500"}, 1)
        wrong = db.create_manual_invoice({"invoice_date": "12-02-2026", "party_name": "Diwan", "kind": "purchases", "currency": "USD", "status": "posted"},
                                         [{"description": "Paper", "quantity": 10, "unit_price": 400, "vat_rate": 11}], 1)  # 10 instead of 1
        wrong_id = wrong if isinstance(wrong, int) else wrong["invoice_id"]
        db.cancel_invoice(wrong_id, "Wrong total", 1)
        invoice = next(i for i in db.list_invoices() if i["id"] == wrong_id)
        self.assertEqual(invoice["status"], "cancelled")
        rows = db.trial_balance(to_date="31-12-2026")
        self.assertTrue(all(abs(r["closing_balance"]) < 0.005 for r in rows))  # the purchase and its reversal cancel out
        self.assertTrue(any(e["entry_number"].startswith("REV-") for e in db.journal()))  # the reversing entry is kept
        try:
            import desktop_purchases
        except ImportError as exc: self.skipTest(f"tkinter not available: {exc}")
        self.assertTrue(callable(getattr(desktop_purchases.PurchasesMixin, "cancel_purchase", None)))



class PdfReadingTest(unittest.TestCase):
    """2.9.97: owner's PDFs - a proforma with '$' after the amounts and a weight 'TOTAL', and a scanned two-copy invoice."""

    def test_proforma_with_dollar_after_amounts(self):
        import pdf_import
        text = ("TRADING OF FROZEN FOOD\nDATE: 2/5/2025\nPROFORMA#:PF.HO.25.0000005\nITEM CODE ITEM DESCRIPTION NET WEIGHT / KG UNIT PRICE TOTAL AMOUNT\n"
                "6116 BEEF RUMP BONELESS FROZEN 1350 7.10$    9,585.00$\n1169 FISH FINGERS FROZEN 1250 4.25$   5,312.50$\n"
                "2126 BREADCRUMBS DRY 75 2.65$    198.75$\n VAT 11% IN LBP 2.00$\n15,098.25$\nPROFORMA NO.5\nTOTAL4425\n")
        r = pdf_import._parse_invoice_text(Path("p.pdf"), text)
        self.assertEqual(r["invoice_number"], "PF.HO.25.0000005")
        self.assertEqual(len(r["items"]), 3)
        self.assertEqual((r["subtotal"], r["vat"], r["total"]), (15096.25, 2.0, 15098.25))  # not the weight 4,425

    def test_scanned_rows_and_copies(self):
        import pdf_import
        self.assertEqual(pdf_import._total_first_row("264.00 0.00 0.00 % 44 60 2KG 1105 BEANS RED KIDNEY")["unit_price"], 4.4)  # lost dot
        row = pdf_import._total_first_row("37.75 415 0.00% 0.755 50 100GR 4146 ROSEMARY")
        self.assertEqual((row["unit_price"], row["vat"]), (0.755, 4.15))
        self.assertEqual(pdf_import._fix_ocr_text("Invoice #: $J20252445 Curreney:USD"), "Invoice #: SJ20252445 Currency:USD")
        page = "Invoice #: SJ20252445\n" + "\n".join(f"{n}.50 0.00 item {n}" for n in range(10, 20))
        copy = page.replace("SJ20252445", "SJ 20252445").replace("19.50", "19.30")  # OCR reads one digit differently
        second_page = "Invoice #: SJ20252445\n" + "\n".join(f"{n}.50 0.00 item {n}" for n in range(40, 50))
        self.assertEqual(len(pdf_import._without_copies([page, copy])), 1)
        self.assertEqual(len(pdf_import._without_copies([page, second_page])), 2)  # a real page 2 is kept
        self.assertEqual(pdf_import._trim_ocr_name("DIWAN GROUP C.S. LS GF Sl gall ASE"), "DIWAN GROUP C.S.")

    def test_table_lines_removed(self):
        from PIL import Image, ImageDraw
        import numpy as np, pdf_import
        image = Image.new("RGB", (400, 200), "white"); draw = ImageDraw.Draw(image)
        draw.line((0, 50, 399, 50), fill="black", width=2); draw.line((100, 0, 100, 199), fill="black", width=2)
        draw.rectangle((200, 100, 210, 110), fill="black")  # a "letter" stays
        clean = np.array(pdf_import._remove_table_lines(image))
        self.assertTrue((clean[50, :] == 255).all()); self.assertTrue((clean[:, 100] == 255).all()); self.assertEqual(clean[105, 205], 0)



class ExpensePdfTest(unittest.TestCase):
    """2.9.97: expense documents - category by score, 9-digit account, the issuer from its e-mail, no-VAT totals, utility bills."""

    def test_categories_and_supplier(self):
        import pdf_import
        ticket = ("1234\nAcme Trading (FZC)\nSVC TRAVELLER CLS DEP AMOUNT\nTICKET J.DOE Eco 10-Apr 930.00\nTICKET J.DOE Eco 20-Apr 870.00\n"
                  "INS. J.DOE 25.00\nEK-007 DXB/BCN-IST/DXB\nXO3538 TRAVEL INSURANCE\nbookings@skytours.com\n1825.00")
        self.assertEqual(pdf_import.expense_category(ticket)[:3], ("Travel", "6264.2", "626420000"))  # not insurance
        self.assertEqual(pdf_import.supplier_from_email(ticket), "Bookings")
        commission = "Email: support@northgroup.co\nNORTH Group Affiliate Expenses\nAffiliate Name Commission Amount\nA 52.00\n"
        self.assertEqual(pdf_import.expense_category(commission)[2], "626520000")
        self.assertEqual(pdf_import.supplier_from_email(commission), "NORTH Group")
        bill = "TOTAL TRANCHES 921850\nBRANCHEMENT\n1816850\nTVA 11% 199854\nTIMBRE 100000\n296\n2117000\nKWH 103\nwww edi qov Ib"
        self.assertEqual(pdf_import.expense_category(bill)[2], "626340000")
        self.assertEqual(pdf_import._utility_bill(bill), {"subtotal": 1816850.0, "vat": 199854.0, "total": 2117000.0, "taxable_subtotal": 1816850.0,
                                                          "exempt_subtotal": 100296.0, "acquisition_cost": 1816850.0})
        r = pdf_import._parse_invoice_text(Path("edl.pdf"), "23/09/2026\n" + bill)
        self.assertEqual((r["currency"], r["total"], r["supplier_hint"]), ("LBP", 2117000.0, "Electricité du Liban (EDL)"))

    def test_expense_form_amounts(self):
        try:
            from desktop_expenses import ExpensesMixin
        except ImportError as exc: self.skipTest(f"tkinter not available: {exc}")
        amounts = ExpensesMixin.expense_amounts_from_pdf
        self.assertEqual(amounts({"total": 3650.0, "vat": None}), {"with_vat": None, "without_vat": 3650.0, "vat": 0.0})  # ticket: no VAT
        self.assertEqual(amounts({"total": 2117000.0, "vat": 199854.0, "subtotal": 1816850.0, "taxable_subtotal": 1816850.0, "exempt_subtotal": 100296.0}),
                         {"with_vat": 1816850.0, "without_vat": 100296.0, "vat": 199854.0})
        self.assertEqual(amounts({"total": 111.0, "vat": 11.0}), {"with_vat": 100.0, "without_vat": None, "vat": 11.0})

    def test_nine_digit_account_opened(self):
        folder = tempfile.TemporaryDirectory(ignore_cleanup_errors=True); self.addCleanup(folder.cleanup)
        db = Database(Path(folder.name) / "e.db"); db.initialize("secret12345"); self.addCleanup(db.release)
        account = db.save_account({"code": "626420000", "name_en": "Travel & Accommodation Expenses", "type": "expense", "parent_code": "6264.2"}, 1)
        self.assertEqual(account["code"] if isinstance(account, dict) else account, "626420000")


if __name__ == "__main__":
    unittest.main()
