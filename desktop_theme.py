"""2.9.94: the look of every screen in one place (it was inside desktop.py).

A calmer, more modern look: flat tabs with a gold line under the open one, soft blue selection, striped table rows
(added by the table helper in desktop.py), flat inputs with a gold focus line and buttons that light up under the
mouse. Colours stay the Saber navy / gold, so printed reports and the logo still match."""
from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk

from desktop_common import GOLD, LIGHT, NAVY

FONT = "Segoe UI"
HEADING = "#23405E"        # table headings
HEADING_ACTIVE = "#2E5277"
SELECTED = "#D3E5F5"       # selected table row
STRIPE = "#F3F6F9"         # every second table row
BORDER = "#C9D3DD"
TAB_IDLE = "#E5ECF2"
TAB_HOVER = "#D6E4ED"


def apply_theme(root: tk.Misc) -> ttk.Style:
    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure("TNotebook", background=LIGHT, borderwidth=0, tabmargins=(6, 6, 6, 0))
    style.configure("TNotebook.Tab", padding=(14, 8), font=(FONT, 9, "bold"), background=TAB_IDLE, foreground=NAVY, borderwidth=0)
    style.map("TNotebook.Tab", background=[("selected", "white"), ("active", TAB_HOVER)], foreground=[("selected", NAVY)],
              lightcolor=[("selected", GOLD)], expand=[("selected", (0, 2, 0, 0))])
    style.configure("Treeview", rowheight=27, font=(FONT, 10), background="white", fieldbackground="white", foreground=NAVY,
                    borderwidth=0, bordercolor=BORDER)  # 2.9.59: 10 pt text in tables
    style.map("Treeview", background=[("selected", SELECTED)], foreground=[("selected", NAVY)])
    style.configure("Treeview.Heading", background=HEADING, foreground="white", font=(FONT, 10, "bold"), relief="flat", padding=(4, 6))
    style.map("Treeview.Heading", background=[("active", HEADING_ACTIVE)])
    style.configure("Sales.Treeview", rowheight=28, font=(FONT, 10))
    style.configure("TCombobox", padding=4, arrowsize=13, bordercolor=BORDER, lightcolor="white", darkcolor="white")
    style.map("TCombobox", bordercolor=[("focus", GOLD)], fieldbackground=[("readonly", "white")])
    style.configure("TEntry", padding=4, bordercolor=BORDER); style.map("TEntry", bordercolor=[("focus", GOLD)])
    style.configure("TLabelframe", background=LIGHT, bordercolor=BORDER)
    style.configure("TLabelframe.Label", background=LIGHT, foreground=NAVY, font=(FONT, 9, "bold"))
    style.configure("TCheckbutton", background=LIGHT, foreground=NAVY); style.map("TCheckbutton", background=[("active", LIGHT)])
    style.configure("TRadiobutton", background=LIGHT, foreground=NAVY); style.map("TRadiobutton", background=[("active", LIGHT)])
    style.configure("Vertical.TScrollbar", arrowsize=12, troughcolor=LIGHT, borderwidth=0, background="#D5DDE5")
    style.configure("Horizontal.TScrollbar", arrowsize=12, troughcolor=LIGHT, borderwidth=0, background="#D5DDE5")
    style.map("Vertical.TScrollbar", background=[("active", "#B8C6D3")]); style.map("Horizontal.TScrollbar", background=[("active", "#B8C6D3")])
    style.configure("TProgressbar", background=GOLD, troughcolor="#E5ECF2", borderwidth=0)
    root.option_add("*Font", (FONT, 9))
    root.option_add("*Entry.relief", "solid"); root.option_add("*Entry.borderWidth", 1)
    root.option_add("*Entry.highlightThickness", 1); root.option_add("*Entry.highlightColor", GOLD); root.option_add("*Entry.highlightBackground", BORDER)
    root.option_add("*LabelFrame.foreground", NAVY); root.option_add("*LabelFrame.font", (FONT, 9, "bold"))
    root.option_add("*Button.cursor", "hand2"); root.option_add("*Button.relief", "flat")
    root.option_add("*Listbox.selectBackground", SELECTED); root.option_add("*Listbox.selectForeground", NAVY)
    root.option_add("*Text.highlightColor", GOLD); root.option_add("*Text.highlightBackground", BORDER)

    def hover(event, entering):  # buttons light up under the mouse
        widget = event.widget
        try:
            if entering:
                widget._saber_bg = widget.cget("background"); color = widget._saber_bg.lstrip("#")
                if len(color) == 6:
                    lighter = "#" + "".join(f"{min(255, int(color[i:i + 2], 16) + 28):02x}" for i in (0, 2, 4)); widget._saber_hover = lighter; widget.configure(background=lighter)
            elif getattr(widget, "_saber_bg", None) and str(widget.cget("background")).lower() == str(getattr(widget, "_saber_hover", "")).lower():
                widget.configure(background=widget._saber_bg)  # only undo our own highlight
        except Exception: logging.getLogger("saber.ignored").debug("Ignored error", exc_info=True)
    root.bind_class("Button", "<Enter>", lambda e: hover(e, True), add="+"); root.bind_class("Button", "<Leave>", lambda e: hover(e, False), add="+")
    return style


def restripe(tree: ttk.Treeview) -> None:
    """Every second row of a table gets a light background (the row's own colours, e.g. red for an error, win)."""
    for index, item in enumerate(tree.get_children("")):
        tags = tree.item(item, "tags")
        tags = [t for t in ((tags.split() if isinstance(tags, str) else tags) or ()) if t != "stripe"]
        if index % 2: tags.append("stripe")
        tree.item(item, tags=tags)
