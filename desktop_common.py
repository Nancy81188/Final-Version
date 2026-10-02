"""Shared imports, colours and small helpers used by every Saber desktop screen."""
from __future__ import annotations

import os
import ctypes
import tkinter as tk
import sys
import threading
import traceback
import mimetypes
import time
import json
import uuid
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from client import ApiClient
from i18n import tr
from report_export import export_excel, export_invoice_pdf, export_pdf, print_rows
from party_similarity import similar_parties

NAVY, GOLD, LIGHT = "#102A43", "#B78B45", "#F4F7FA"
SALE_TREATMENTS={"Taxable 11%":"standard","Zero-rated (export)":"zero_rated","Exempt (Art. 16-17)":"exempt","Out of scope":"out_of_scope"}
PURCHASE_USES={"Mixed (partial deduction)":"mixed","Taxable sales only (100%)":"taxable","Exempt sales only (0%)":"exempt"}

def resource_path(relative_path):
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    path = base / relative_path
    if not path.exists() and relative_path.startswith("assets/"):
        alternative = base / "Assets" / relative_path[len("assets/"):]
        if alternative.exists(): return alternative
    return path

def row_matches_search(values, query):
    """Return True when every search term appears somewhere in the row.

    Amounts match with or without thousands separators (1250 finds 1,250.00) and dates match
    with or without dashes (31122024 finds 31-12-2024)."""
    terms = str(query or "").casefold().split()
    if not terms:
        return True
    searchable = " ".join("" if value is None else str(value) for value in values).casefold()
    searchable = f"{searchable} {searchable.replace(',', '')} {searchable.replace('-', '').replace('/', '')}"
    return all(term in searchable or term.replace(",", "") in searchable for term in terms)

def auto_dash_date(text):
    """Turn typed digits into DD-MM-YYYY as the user types: 3112 -> 31-12, 31122024 -> 31-12-2024."""
    digits = "".join(ch for ch in str(text or "") if ch.isdigit())[:8]
    if len(digits) <= 2: return digits
    if len(digits) <= 4: return f"{digits[:2]}-{digits[2:]}"
    return f"{digits[:2]}-{digits[2:4]}-{digits[4:]}"

def sortable_date(value):
    text=str(value or "").strip()
    for pattern in ("%d-%m-%Y","%Y-%m-%d"):
        try: return datetime.strptime(text,pattern)
        except ValueError: pass
    return datetime.min

def initial_window_size(screen_width, screen_height, dpi_scale=1.0):
    """Keep the initial window and its minimum size inside compact displays."""
    available_width=max(1,screen_width-32)
    available_height=max(1,screen_height-72)
    width=min(round(1180*dpi_scale),available_width)
    height=min(round(720*dpi_scale),available_height)
    return width,height,min(round(760*dpi_scale),width),min(round(480*dpi_scale),height)

def parse_user_date(value):
    text=str(value or "").strip()
    for pattern in ("%d-%m-%Y","%d%m%Y","%Y-%m-%d","%Y%m%d"):
        try: return datetime.strptime(text,pattern)
        except ValueError: pass
    raise ValueError("Date must contain 8 digits: DDMMYYYY")

def formatted_user_date(value):
    return parse_user_date(value).strftime("%d-%m-%Y")

def safe_display_date(value):
    """Show a saved date as DD-MM-YYYY; keep the original text if it is in another format."""
    try: return formatted_user_date(value)
    except (ValueError, TypeError): return "" if value is None else str(value)

def natural_sort_value(value):
    text=str(value or "").strip()
    try: return (0,float(text.replace(",","")))
    except ValueError: return (1,text.casefold())

def _enable_windows_dpi_awareness():
    """Let Windows report real monitor dimensions before Tk chooses the initial window size."""
    if sys.platform!="win32": return
    try:
        if ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)): return
    except (AttributeError,OSError):
        pass
    try: ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (AttributeError,OSError): pass
