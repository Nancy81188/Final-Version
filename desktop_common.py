"""Shared imports, colours and small helpers used by every Saber desktop screen."""
from __future__ import annotations

import os
import logging
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
from multi_select import MultiSelect, chosen_values  # 2.9.50: pick any combination in filters

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
    if value is None or str(value).strip().lower() in ("", "none", "null", "nan"): return ""
    try: return formatted_user_date(value)
    except (ValueError, TypeError): return str(value)

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


# ---------------------------------------------------------------- 2.9.59: tidier screens
import re as _re

_AMOUNT_WORDS = ("debit", "credit", "balance", "total", "amount", "subtotal", "deductible", "vat", "paid", "outstanding",
                 "inflow", "outflow", "net", "value", "price", "cost", "salary", "eq.", "qty", "quantity", "rate", "variance",
                 "current", "prior", "opening", "closing", "budget", "actual", "lbp", "usd", "eur")
_NOT_AMOUNT = ("account", "name", "date", "status", "method", "type", "description", "currency", "number", "no.", "party", "vat status",
               "deductible?", "category", "code", "kind")


def is_amount_column(key, label=""):
    """True for a column that holds amounts (shown on the right, like a spreadsheet)."""
    text = f"{key} {label}".strip().casefold()
    if any(word in text for word in ("vat_status", "vat deductible", "vat treatment", "currency", "date", "rate date")): return False
    words = str(key).casefold().replace("_", " ").split() + str(label).casefold().split()
    if any(w in _NOT_AMOUNT for w in words) and not any(w in ("debit", "credit", "balance", "total", "amount") for w in words): return False
    return any(word in text for word in _AMOUNT_WORDS)


_ISO_DAY = _re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")


def display_cells(values):
    """Dates are shown DD-MM-YYYY everywhere: a cell holding a YYYY-MM-DD date is turned around (data is unchanged)."""
    if isinstance(values, str) or not isinstance(values, (list, tuple)): return values
    shown = []
    for value in values:
        if isinstance(value, str):
            match = _ISO_DAY.match(value.strip())
            if match: value = f"{match.group(3)}-{match.group(2)}-{match.group(1)}"
        shown.append(value)
    return type(values)(shown) if isinstance(values, tuple) else shown


def _iso_to_shown(value):
    if isinstance(value, str):
        match = _ISO_DAY.match(value.strip())
        if match: return f"{match.group(3)}-{match.group(2)}-{match.group(1)}"
    return None


def _install_date_display():
    """Tables SHOW dates as DD-MM-YYYY, but the program still READS the original YYYY-MM-DD back from the table
    (item(..., "values"), set(...)), so editing, saving and exporting keep working with the real data."""
    if getattr(ttk.Treeview, "_saber_dates", False): return
    real_insert, real_item, real_set, real_delete = ttk.Treeview.insert, ttk.Treeview.item, ttk.Treeview.set, ttk.Treeview.delete

    def remember(tree, iid, values):
        store = tree.__dict__.setdefault("_saber_iso", {}); kept = {}; shown = list(values)
        for index, value in enumerate(values):
            text = _iso_to_shown(value)
            if text is not None: kept[index] = (text, value); shown[index] = text
        if kept: store[str(iid)] = kept
        else: store.pop(str(iid), None)
        return tuple(shown) if isinstance(values, tuple) else shown

    def original(tree, iid, values):
        kept = tree.__dict__.get("_saber_iso", {}).get(str(iid))
        if not kept or not isinstance(values, (list, tuple)): return values
        values = list(values)
        for index, (text, raw) in kept.items():
            if index < len(values) and str(values[index]) == text: values[index] = raw
        return tuple(values)

    def insert(self, parent, index, iid=None, **kw):
        values = kw.get("values")
        if not isinstance(values, (list, tuple)): return real_insert(self, parent, index, iid, **kw)
        kw["values"] = shown = display_cells(values)
        new_iid = real_insert(self, parent, index, iid, **kw)
        remember(self, new_iid, values); return new_iid

    def item(self, item_id, option=None, **kw):
        if isinstance(kw.get("values"), (list, tuple)): kw["values"] = remember(self, item_id, kw["values"])
        result = real_item(self, item_id, option, **kw)
        if kw: return result
        if option == "values": return original(self, item_id, result)
        if option is None and isinstance(result, dict) and "values" in result: result["values"] = original(self, item_id, result["values"])
        return result

    def set_(self, item_id, column=None, value=None):
        if column is None:
            result = real_set(self, item_id)
            kept = self.__dict__.get("_saber_iso", {}).get(str(item_id))
            if kept and isinstance(result, dict):
                names = list(self["columns"])
                for index, (text, raw) in kept.items():
                    if index < len(names) and str(result.get(names[index])) == text: result[names[index]] = raw
            return result
        names = list(self["columns"])
        try: index = names.index(column) if not isinstance(column, int) and not str(column).startswith("#") else (int(str(column).lstrip("#")) - (1 if str(column).startswith("#") else 0))
        except (ValueError, TypeError): index = None
        store = self.__dict__.setdefault("_saber_iso", {})
        if value is None:
            current = real_set(self, item_id, column)
            kept = store.get(str(item_id), {})
            if index in kept and str(current) == kept[index][0]: return kept[index][1]
            return current
        text = _iso_to_shown(value)
        if index is not None:
            kept = store.setdefault(str(item_id), {})
            if text is not None: kept[index] = (text, value)
            else: kept.pop(index, None)
        return real_set(self, item_id, column, text if text is not None else value)

    def delete(self, *items):
        store = self.__dict__.get("_saber_iso")
        if store:
            for iid in items: store.pop(str(iid), None)
        return real_delete(self, *items)

    ttk.Treeview.insert, ttk.Treeview.item, ttk.Treeview.set, ttk.Treeview.delete = insert, item, set_, delete
    ttk.Treeview._saber_dates = True


_install_date_display()


def flow_toolbar(frame, gap=4):
    """A row of buttons that wraps onto a second line when the window is narrow, instead of being cut off on the
    right. Works on a frame already filled with pack(side=left / right): the same widgets, same order.
    Can be called again after the frame's contents were rebuilt (the new packed widgets join the flow)."""
    slaves = frame.pack_slaves()
    if not slaves: return frame
    def padding(info, key):
        value = info.get(key, 0)
        parts = [int(float(p)) for p in str(value).split()] if not isinstance(value, (list, tuple)) else [int(p) for p in value]
        return (parts[0], parts[-1]) if parts else (0, 0)
    entries = []
    for widget in slaves:
        info = widget.pack_info(); entries.append((widget, info.get("side", "top"), padding(info, "padx"), padding(info, "pady")))
        widget.pack_forget()
    order = [e for e in entries if e[1] != "right"] + list(reversed([e for e in entries if e[1] == "right"]))
    first_time = not getattr(frame, "_saber_flow", False)
    frame._flow_order = [e for e in getattr(frame, "_flow_order", []) if e[0].winfo_exists()] + order
    frame._saber_flow = True; frame._flow_pending = False

    def layout():
        frame._flow_pending = False
        if not frame.winfo_exists(): return
        width = frame.winfo_width()
        if width <= 1: width = max(frame.winfo_reqwidth(), 600)
        x = y = 0; row = 0
        for widget, _side, (left, right), (top, bottom) in frame._flow_order:
            if not widget.winfo_exists() or getattr(widget, "_flow_hidden", False): continue
            w, h = widget.winfo_reqwidth(), widget.winfo_reqheight()
            if x > 0 and x + left + w + right > width: x = 0; y += row + gap; row = 0
            widget.place(x=x + left, y=y + top); x += left + w + right; row = max(row, top + h + bottom)
        height = max(1, y + row)
        if int(frame.cget("height") or 0) != height: frame.configure(height=height)

    def schedule(_event=None):
        if not getattr(frame, "_flow_pending", False) and frame.winfo_exists():
            frame._flow_pending = True
            frame.after_idle(layout)

    frame._flow_schedule = schedule
    if first_time:
        try: frame.pack_propagate(False)
        except tk.TclError: pass
        try:
            if frame.winfo_manager() == "pack": frame.pack_configure(fill="x")
        except tk.TclError: pass
        frame.bind("<Configure>", schedule, add="+")
    widest = max((w.winfo_reqwidth() + l + r for w, _s, (l, r), _p in frame._flow_order if w.winfo_exists()), default=100)
    frame.configure(width=widest)
    for widget, *_rest in order: widget.bind("<Configure>", lambda _e, f=frame: f._flow_schedule(), add="+")
    schedule()
    return frame


def flow_toolbars(*frames):
    for frame in frames:
        try: flow_toolbar(frame)
        except Exception: logging.getLogger("saber.ignored").debug("Toolbar left as it was", exc_info=True)


# ---------------------------------------------------------------- 2.9.66: select several rows, see their totals
def enable_drag_select(tree):
    """Ctrl+click and Shift+click already select several rows; this adds: press the mouse on a row and drag over the
    rows below (or above) to select them all."""
    state = {"anchor": None}
    def press(event):
        state["anchor"] = None
        if event.state & 0x0005: return  # Shift / Ctrl: the Treeview's own multi-selection
        if tree.identify_region(event.x, event.y) in ("cell", "tree"): state["anchor"] = tree.identify_row(event.y) or None
    def drag(event):
        anchor = state["anchor"]
        if not anchor or not tree.exists(anchor): return
        row = tree.identify_row(event.y)
        if not row:  # dragged above / below the visible rows: scroll and take the edge row
            rows = tree.get_children("")
            if not rows: return
            if event.y < 0: tree.yview_scroll(-1, "units")
            elif event.y > tree.winfo_height(): tree.yview_scroll(1, "units")
            return
        rows = list(tree.get_children("")); a, b = rows.index(anchor), rows.index(row)
        tree.selection_set(rows[min(a, b):max(a, b) + 1]); tree.focus(row)
    tree.bind("<ButtonPress-1>", press, add="+"); tree.bind("<B1-Motion>", drag, add="+")
    return tree


def _amount(value):
    text = str(value if value is not None else "").replace(",", "").strip()
    if text.startswith("(") and text.endswith(")"): text = "-" + text[1:-1]
    try: return float(text)
    except ValueError: return None


def selection_totals(tree, columns, label, hint=None):
    """With 2 or more rows selected, the label shows how many and the total of every amount column (Debit, Credit,
    Total, VAT...): an automatic sum like the status bar of Excel."""
    amount_columns = [(index, key, title) for index, (key, title, *_rest) in enumerate(columns) if is_amount_column(key, title)]
    def update(_event=None):
        skip = getattr(tree, "_totals_skip", ())  # e.g. a running balance, whose sum means nothing
        try: selected = tree.selection()
        except tk.TclError: return
        if len(selected) < 2 or not amount_columns:
            label.config(text="")
            if hint is not None and not hint.winfo_manager(): hint.pack(side="right")
            return
        if hint is not None and hint.winfo_manager(): hint.pack_forget()  # room for the totals
        sums = {}
        for iid in selected:
            values = tree.item(iid, "values")
            for index, key, title in amount_columns:
                if key in skip: continue
                number = _amount(values[index]) if index < len(values) else None
                if number is not None: sums[title] = sums.get(title, 0.0) + number
        label.config(text=f"{len(selected)} selected   " + "   ".join(f"{title}: {total:,.2f}" for title, total in sums.items()))
    tree.bind("<<TreeviewSelect>>", update, add="+")
    return update
