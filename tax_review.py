"""2.9.98: "Rules for the tax adviser" - every payroll and VAT rule the program applies, with the value in THIS company's
settings on a date, its source and whether it is law already confirmed or still to confirm. Print it (PDF / Excel), give it
to the tax adviser, and correct any value in Payroll > Tax & NSSF Settings (or Accounting Setup for VAT)."""
from __future__ import annotations

from decimal import Decimal

from database_common import display_date, iso_date

CONFIRMED, CONFIRM, PENDING = "Law / decree - confirmed", "To confirm with the tax adviser", "Announced, not law - not applied"


def _money(value):
    try: return f"{Decimal(str(value)):,.0f}"
    except Exception: return str(value or "")


def build(db, date):
    day = iso_date(date, "Date")
    s = db.payroll_settings_for(day) or {}
    brackets = s.get("tax_brackets") or []
    previous = 0; bands = []
    for limit, rate in brackets:
        bands.append(f"{rate * 100:g}% {'above ' + _money(previous) if limit is None else 'to ' + _money(limit)}")
        previous = limit or previous
    try: vat = db.settings().get("vat_rate") or "11"
    except Exception: vat = "11"
    rows = [
        ["Salary tax", "Annual brackets", "; ".join(bands) or "-", "Budget Law 324/2024", CONFIRM],
        ["Salary tax", "Personal (single) deduction / year", _money(s.get("single_allowance")), "Law 324/2024", CONFIRM],
        ["Salary tax", "Spouse deduction / year (dependent spouse)", _money(s.get("spouse_allowance")), "Law 324/2024", CONFIRM],
        ["Salary tax", "Child deduction / year, maximum children", f"{_money(s.get('child_allowance'))} x max {s.get('max_children_deduction') or 5}", "Law 324/2024", CONFIRM],
        ["Salary tax", "Rounding of the tax", f"up to LBP {_money(s.get('tax_rounding'))}" if Decimal(str(s.get("tax_rounding") or 0)) else "none", "MoF Decision 1195 (25-11-2024)", CONFIRM],
        ["Salary tax", "Family changes during the year", "spouse from the month of marriage, child from the month of birth", "Practice (program 2.9.96)", CONFIRM],
        ["Exemptions", "Transport allowance exempt / working day", _money(s.get("transport_daily_exempt")), "Decree 12966/2024", CONFIRM],
        ["Exemptions", "Food allowance exempt / working day (from 10-02-2026)", "300,000", "Budget Law 2026 Art. 26 (program reading)", CONFIRM],
        ["Exemptions", "Schooling allowance exempt / year", _money(s.get("schooling_annual_exempt")), "MoF practice", CONFIRM],
        ["NSSF", "Employee sickness & maternity rate", f"{Decimal(str(s.get('employee_nssf_rate') or 0)) * 100:g}%", "CNSS decrees", CONFIRMED],
        ["NSSF", "Employer sickness & maternity rate", f"{Decimal(str(s.get('medical_rate') or 0)) * 100:g}%", "CNSS decrees", CONFIRMED],
        ["NSSF", "Family allowances rate", f"{Decimal(str(s.get('family_rate') or 0)) * 100:g}%", "CNSS decrees", CONFIRMED],
        ["NSSF", "End-of-service rate", f"{Decimal(str(s.get('end_service_rate') or 0)) * 100:g}%", "Social Security Law", CONFIRMED],
        ["NSSF", "Sickness & maternity ceiling / month", _money(s.get("medical_ceiling")), "Decree 887 (14-08-2025); Memo 801 said 140M", CONFIRM],
        ["NSSF", "Family allowances ceiling / month", _money(s.get("family_ceiling")), "Decree 2923 / Memo 831", CONFIRMED],
        ["NSSF", "Family allowance: spouse / child / cap per month",
         f"{_money(s.get('family_allowance_spouse'))} / {_money(s.get('family_allowance_child'))} / {_money(s.get('family_allowance_cap'))}", "Decree 2923 / Memo 831", CONFIRMED],
        ["Minimum wage", "Minimum wage / month", _money(s.get("minimum_wage")), "CNSS Memo 801 (01-08-2025)", CONFIRMED],
        ["VAT", "Standard rate", f"{vat}%", "VAT Law 379/2001 as amended", CONFIRMED],
        ["VAT", "Return and payment", "quarterly, within one month after the quarter", "VAT Law", CONFIRMED],
        ["VAT", "Utilities (electricity, water, telephone) - input VAT", "not recovered from 10-02-2026", "Budget Law 2026 Art. 30 (program reading)", CONFIRM],
        ["VAT", "Passenger cars - input VAT", "recovered on the first USD 30,000 of the price only", "Budget Law 2026 Art. 30 (program reading)", CONFIRM],
        ["VAT", "Partial deduction (mixed use)", "taxable / total revenue, per quarter", "VAT Law Art. 31", CONFIRMED],
        ["VAT", "VAT account per customer / supplier, closing at quarter end", "4421 / 4427 / 44216 / 44213 sub-accounts", "Lebanese practice (VAT 140)", CONFIRMED],
        ["Pending", "VAT at 12%", "not applied", "Announced", PENDING],
        ["Pending", "Transport allowance LBP 500,000 - 800,000 / day", "not applied", "Announced", PENDING],
    ]
    to_confirm = sum(1 for row in rows if row[4] == CONFIRM)
    return {"title": "Rules for the Tax Adviser", "date": display_date(day), "to_confirm": to_confirm,
            "meta": [f"Values in this company's settings on {display_date(day)}", f"{to_confirm} rule(s) to confirm with the tax adviser",
                     "Correct a value in Payroll > Tax & NSSF Settings (VAT: Accounting Setup); every later payslip and return uses it."],
            "sections": [{"heading": "Payroll and VAT rules applied by the program", "headers": ["Area", "Rule", "Value used", "Source", "Status"], "rows": rows},
                         {"heading": "Adviser sign-off", "headers": ["Item", "Answer"],
                          "rows": [["Reviewed by (name, licence)", ""], ["Date", ""], ["Values to change (rule -> correct value)", ""], ["Signature", ""]]}]}
