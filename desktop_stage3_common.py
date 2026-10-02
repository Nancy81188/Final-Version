"""Shared imports and helpers of desktop_stage3.py (split in 2.9.42)."""
from __future__ import annotations

import mimetypes
import os
import subprocess
import sys
import tempfile
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from importer import read_customs_costs, read_expenses, read_invoices
from chart_extra import EXPENSE_VAT, PURCHASE_VAT, SALES_VAT
from pdf_import import asset_pdf_details, read_invoice_pdf, read_invoice_pdf_pages
from report_export import export_excel, export_pdf

NAVY, GOLD, LIGHT = "#071b2e", "#c9a96a", "#f3f6f8"
PURCHASE_USES = {"Mixed (partial deduction)": "mixed", "Taxable sales only (100%)": "taxable", "Exempt sales only (0%)": "exempt"}
RED, MUTED = "#8B1E1E", "#5f6b76"
TYPES = {"Purchases": ("purchase", "purchases"), "Sales": ("sale", "sales"), "Expenses": ("purchase", "expenses"), "Assets": ("purchase", "assets")}
METHODS = ["Cash", "Cheque", "Bank Transfer", "Card", "Other"]


def _num(value, default=0.0):
    try: return float(str(value).replace(",", "")) if str(value).strip() else default
    except ValueError: return None


def _dd(value):
    text = str(value or "").strip()
    for pattern in ("%d-%m-%Y", "%Y-%m-%d", "%d%m%Y"):
        try: return datetime.strptime(text, pattern).strftime("%d-%m-%Y")
        except ValueError: pass
    return text


def auto_upload_on(app):
    """2.9.50: 'Save automatically after upload' ticked (screens built without it keep the old manual flow)."""
    var = getattr(app, "auto_upload_var", None)
    try: return bool(var().get()) if callable(var) else False
    except Exception: return False
