"""Filters where any combination can be chosen (2.9.50): the 1st and the 3rd, two, five ... or All.

The variable keeps readable text: "All", one value, or several values separated by "; ". chosen_values() turns that
text back into the list of values (an empty list means All), so a filter that used to hold one value keeps working.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

SEPARATOR = "; "
ALL = "All"


def chosen_values(text):
    text = str(text or "").strip()
    if not text or text == ALL: return []
    return [part.strip() for part in text.split(SEPARATOR.strip()) if part.strip() and part.strip() != ALL]


def matches(value, text):
    wanted = chosen_values(text)
    return not wanted or str(value or "").strip().casefold() in {w.casefold() for w in wanted}


class MultiSelect(tk.Frame):
    """Looks like a drop-down; opens a list with tick boxes, a search box, All / Clear and OK."""

    def __init__(self, master, variable, values=(), width=16, on_change=None, title="Choose", **options):
        super().__init__(master, bg=options.pop("bg", master.cget("bg") if hasattr(master, "cget") else None))
        self.variable = variable; self.values = [v for v in values if v not in ("", ALL)]; self.on_change = on_change; self.title = title
        if not variable.get(): variable.set(ALL)
        self.entry = ttk.Entry(self, textvariable=variable, width=width, state="readonly", cursor="hand2")
        self.entry.pack(side="left")
        self.button = tk.Button(self, text="▾", command=self.open, border=0, padx=4, cursor="hand2")
        self.button.pack(side="left")
        for widget in (self.entry,):
            widget.bind("<Button-1>", lambda _e: self.open())
            widget.bind("<Return>", lambda _e: self.open()); widget.bind("<space>", lambda _e: self.open())
        self.popup = None

    # Combobox-like access: box["values"] = [...]
    def __setitem__(self, key, value):
        if key == "values": self.values = [str(v) for v in value if str(v) not in ("", ALL)]
        else: super().__setitem__(key, value)

    def __getitem__(self, key):
        if key == "values": return tuple([ALL] + self.values)
        return super().__getitem__(key)

    def set_choices(self, chosen):
        chosen = [c for c in chosen if c]
        self.variable.set(ALL if not chosen or len(chosen) == len(self.values) else SEPARATOR.join(chosen))
        if self.on_change: self.on_change()

    def open(self):
        if self.popup is not None and self.popup.winfo_exists(): self.popup.lift(); return "break"
        popup = tk.Toplevel(self); self.popup = popup; popup.title(self.title); popup.transient(self.winfo_toplevel())
        popup.geometry(f"+{self.winfo_rootx()}+{self.winfo_rooty() + self.winfo_height()}")
        chosen = {v.casefold() for v in chosen_values(self.variable.get())}
        flags = {value: tk.BooleanVar(master=popup, value=value.casefold() in chosen) for value in self.values}
        search = tk.StringVar(master=popup)
        top = tk.Frame(popup); top.pack(fill="x", padx=6, pady=(6, 2))
        tk.Label(top, text="Search").pack(side="left"); entry = ttk.Entry(top, textvariable=search, width=22); entry.pack(side="left", padx=4)
        holder = tk.Frame(popup); holder.pack(fill="both", expand=True, padx=6)
        canvas = tk.Canvas(holder, width=260, height=min(300, 24 * max(1, len(self.values))), highlightthickness=0)
        scroll = ttk.Scrollbar(holder, orient="vertical", command=canvas.yview); inner = tk.Frame(canvas)
        canvas.create_window((0, 0), window=inner, anchor="nw"); canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side="left", fill="both", expand=True); scroll.pack(side="right", fill="y")
        boxes = {}
        for value in self.values:
            boxes[value] = tk.Checkbutton(inner, text=value, variable=flags[value], anchor="w")
        def show(*_args):
            for widget in boxes.values(): widget.pack_forget()
            query = search.get().strip().casefold()
            for value, widget in boxes.items():
                if not query or query in value.casefold(): widget.pack(fill="x", anchor="w")
            inner.update_idletasks(); canvas.configure(scrollregion=canvas.bbox("all"))
        search.trace_add("write", show); show()
        if not self.values: tk.Label(inner, text="Nothing to choose yet").pack(padx=8, pady=8)
        def tick(state):
            query = search.get().strip().casefold()
            for value, flag in flags.items():
                if not query or query in value.casefold(): flag.set(state)
        def done(_event=None):
            self.set_choices([value for value in self.values if flags[value].get()]); popup.destroy()
        buttons = tk.Frame(popup); buttons.pack(fill="x", padx=6, pady=6)
        tk.Button(buttons, text="Tick all", command=lambda: tick(True)).pack(side="left")
        tk.Button(buttons, text="Clear", command=lambda: tick(False)).pack(side="left", padx=4)
        tk.Button(buttons, text="OK", command=done, width=8).pack(side="right")
        tk.Button(buttons, text="All (no filter)", command=lambda: (self.set_choices([]), popup.destroy())).pack(side="right", padx=4)
        popup.bind("<Escape>", lambda _e: popup.destroy()); popup.bind("<Return>", done)
        entry.focus_set()
        return "break"
