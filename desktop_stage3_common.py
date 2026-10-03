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


def resolve_item(app, name, unit="unit", code=None, supplier_id=None):
    """2.9.51: the inventory item for a purchase line. The same name written differently is matched by the service;
    when only a CLOSE name exists (e.g. 'HPL Panel 4mm Wht' and 'HPL Panel 4mm White'), the user chooses once:
    use the existing item or create a new one. The answer is remembered for the rest of the session."""
    client = app.client
    if code or not isinstance(app, tk.Misc):
        return client.find_or_create_item(name, unit, code, supplier_id)
    memory = getattr(app, "_item_choices", None)
    if memory is None:
        memory = {}
        try: app._item_choices = memory
        except Exception: pass
    key = str(name or "").strip().casefold()
    if key in memory:
        chosen = memory[key]
        return chosen if chosen else client.find_or_create_item(name, unit, None, supplier_id)
    try: candidates = client.similar_items(name)
    except Exception: candidates = []
    if not isinstance(candidates, list) or not candidates or candidates[0].get("score", 0) >= 1:
        return client.find_or_create_item(name, unit, None, supplier_id)
    chosen = choose_similar_item(app, name, candidates)
    memory[key] = chosen
    return chosen if chosen else client.find_or_create_item(name, unit, None, supplier_id)


def choose_similar_item(app, name, candidates):
    """Small window: use one of the close items, or create a new item. Returns the chosen item or None (create)."""
    window = tk.Toplevel(app); window.title("Same item?"); window.transient(app); window.grab_set()
    tk.Label(window, text=f"The invoice line\n\"{name}\"\nlooks like an item you already have:", justify="left", font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=14, pady=(12, 6))
    choice = tk.IntVar(master=window, value=0)
    for index, item in enumerate(candidates):
        tk.Radiobutton(window, text=f'Use {item["sku"]} - {item["name"]} ({item.get("unit") or ""}, {item["score"] * 100:.0f}% alike)', variable=choice, value=index,
                       anchor="w").pack(fill="x", padx=20)
    tk.Radiobutton(window, text="Create a new item with this name", variable=choice, value=-1, anchor="w").pack(fill="x", padx=20, pady=(4, 0))
    result = {"item": None}
    def ok(_e=None):
        result["item"] = candidates[choice.get()] if choice.get() >= 0 else None; window.destroy()
    tk.Button(window, text="OK", command=ok, width=10).pack(pady=12)
    window.bind("<Return>", ok); window.protocol("WM_DELETE_WINDOW", ok)
    app.wait_window(window)
    return result["item"]
