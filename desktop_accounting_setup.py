"""2.9.81: Settings > Accounting Settings - what the company uses, what I see, the default posting accounts,
and the Year-End Check (also run before closing a year)."""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

import accounting_setup as rules
from desktop_common import account_code, account_label, accounting_setup

NAVY, GOLD, LIGHT = "#102A43", "#B78B45", "#F4F7FA"
RED, MUTED, GREEN, AMBER = "#8B1E1E", "#5f6b76", "#2E7D5B", "#8a5a00"


class AccountingSetupMixin:
    # ------------------------------------------------------------ Settings > Accounting Settings
    def build_accounting_setup_page(self, page):
        values = accounting_setup(self, refresh=True)
        is_admin = (self.current_user or {}).get("role") == "admin"
        tk.Label(page, text="Choose what this company uses and what you see. Hidden screens and reports leave the menu; nothing is deleted, "
                 "and users' permissions (payroll, VAT, delete) still apply.", bg=LIGHT, fg=MUTED, anchor="w", justify="left", wraplength=1100).pack(fill="x", padx=12, pady=(8, 4))
        top = tk.Frame(page, bg=LIGHT); top.pack(fill="x", padx=8)
        keys = [m["key"] for m in values.get("modules") or []] + [f"report:{r}" for r in values.get("reports") or []]
        labels = {m["key"]: m["label"] for m in values.get("modules") or []}; labels.update({f"report:{r}": f"Report: {r}" for r in values.get("reports") or []})
        company_hidden = set(values.get("hidden") or []); mine = set(values.get("user_hidden") or [])
        self.setup_company_vars = {key: tk.BooleanVar(value=key not in company_hidden) for key in keys}
        self.setup_user_vars = {key: tk.BooleanVar(value=key not in mine) for key in keys}
        for title, variables, editable, note in (("This company uses (administrator)", self.setup_company_vars, is_admin, "Untick what the company does not use."),
                                                  ("I see (only for me)", self.setup_user_vars, True, "Untick what you do not need; the company's choice comes first.")):
            box = tk.LabelFrame(top, text=title, bg=LIGHT, padx=8, pady=4); box.pack(side="left", fill="both", expand=True, padx=4, pady=4)
            tk.Label(box, text=note, bg=LIGHT, fg=MUTED).grid(row=0, column=0, columnspan=2, sticky="w")
            for index, key in enumerate(keys):
                check = tk.Checkbutton(box, text=labels[key], variable=variables[key], bg=LIGHT, anchor="w", state="normal" if editable else "disabled")
                check.grid(row=1 + index % 12, column=index // 12, sticky="w", padx=(0, 12))
        buttons = tk.Frame(page, bg=LIGHT); buttons.pack(fill="x", padx=12, pady=4)
        if is_admin: tk.Button(buttons, text="Save for the Company", command=self.save_company_view, bg=GOLD, fg=NAVY, border=0, padx=14, pady=6, font=("Segoe UI", 9, "bold")).pack(side="left", padx=3)
        self.action_button(buttons, "Save for Me", self.save_my_view).pack(side="left", padx=3)
        accounts = tk.LabelFrame(page, text="Default posting accounts - used when a document does not name an account", bg=LIGHT, padx=8, pady=6)
        accounts.pack(fill="x", padx=8, pady=6)
        self.setup_default_vars = {}
        for row, item in enumerate(values.get("defaults") or []):
            tk.Label(accounts, text=item["label"], bg=LIGHT, anchor="w").grid(row=row, column=0, sticky="w", pady=1)
            variable = tk.StringVar(value=account_label(self, item["account"])); self.setup_default_vars[item["key"]] = variable
            box = self.account_search_box(accounts, variable, 44); box.grid(row=row, column=1, sticky="w", padx=8, pady=1)
            if not is_admin: box.configure(state="disabled")
            default = f'default {item["default"]}' + (f' - {item["default_name"]}' if item.get("default_name") else "")
            tk.Label(accounts, text=f'{item["used_for"]}  ({default})', bg=LIGHT, fg=MUTED, anchor="w").grid(row=row, column=2, sticky="w")
        tk.Label(accounts, text=values.get("payroll_note") or "", bg=LIGHT, fg=NAVY, anchor="w", justify="left", wraplength=1000).grid(row=len(self.setup_default_vars), column=0, columnspan=3, sticky="w", pady=(6, 0))
        if is_admin:
            bar = tk.Frame(accounts, bg=LIGHT); bar.grid(row=len(self.setup_default_vars) + 1, column=0, columnspan=3, sticky="w", pady=(6, 0))
            tk.Button(bar, text="Save Default Accounts", command=self.save_default_accounts, bg=GOLD, fg=NAVY, border=0, padx=14, pady=6, font=("Segoe UI", 9, "bold")).pack(side="left", padx=3)
            self.action_button(bar, "Program Defaults", self.restore_default_accounts).pack(side="left", padx=3)
        alerts = tk.LabelFrame(page, text="Dashboard", bg=LIGHT, padx=8, pady=6); alerts.pack(fill="x", padx=8, pady=6)  # 2.9.82
        self.setup_alert_percent = tk.StringVar(value=str(values.get("budget_alert_percent") or "10"))
        tk.Label(alerts, text="Show the accounts off budget (costs above / revenue below) by more than", bg=LIGHT).pack(side="left")
        tk.Entry(alerts, textvariable=self.setup_alert_percent, width=6, state="normal" if is_admin else "disabled").pack(side="left", padx=4)
        tk.Label(alerts, text="% (year to date, the company budget in the main currency)", bg=LIGHT).pack(side="left")
        if is_admin: self.action_button(alerts, "Save", self.save_alert_percent).pack(side="left", padx=8)
        check = tk.LabelFrame(page, text="Year-End Check", bg=LIGHT, padx=8, pady=6); check.pack(fill="x", padx=8, pady=6)
        tk.Label(check, text="The points an auditor checks before the books are closed. It runs again by itself when you close the year (Profit & Loss).", bg=LIGHT, fg=MUTED).pack(side="left")
        tk.Button(check, text="Run Year-End Check", command=self.show_year_end_check, bg=NAVY, fg="white", border=0, padx=14, pady=6).pack(side="left", padx=8)

    def _view_choice(self, variables):
        return [key for key, variable in variables.items() if not variable.get()]

    def save_company_view(self):
        try: self.client.save_accounting_setup({"hidden": self._view_choice(self.setup_company_vars)})
        except Exception as exc: return messagebox.showerror("Accounting Settings", str(exc))
        self._apply_new_view("Saved for the company.")

    def save_my_view(self):
        try: self.client.save_my_hidden(self._view_choice(self.setup_user_vars))
        except Exception as exc: return messagebox.showerror("Accounting Settings", str(exc))
        self._apply_new_view("Saved for you.")

    def _apply_new_view(self, message):
        accounting_setup(self, refresh=True)
        messagebox.showinfo("Accounting Settings", message + " The menu and the reports are rebuilt now.")
        self.main_screen()

    def save_default_accounts(self):
        payload = {key: account_code(variable.get()) for key, variable in self.setup_default_vars.items()}
        try: self.client.save_accounting_setup({"defaults": payload})
        except Exception as exc: return messagebox.showerror("Accounting Settings", str(exc))
        accounting_setup(self, refresh=True)
        messagebox.showinfo("Accounting Settings", "Default accounts saved. New documents use them from now on; documents already saved are not changed.")

    def save_alert_percent(self):
        try: self.client.save_accounting_setup({"budget_alert_percent": self.setup_alert_percent.get()})
        except Exception as exc: return messagebox.showerror("Accounting Settings", str(exc))
        accounting_setup(self, refresh=True); messagebox.showinfo("Accounting Settings", "Saved. The Dashboard uses it from now on.")

    def restore_default_accounts(self):
        if not messagebox.askyesno("Accounting Settings", "Put back the program's default accounts?"): return
        for key, variable in self.setup_default_vars.items(): variable.set(account_label(self, rules.DEFAULT_ACCOUNTS[key][1]))
        self.save_default_accounts()

    # ------------------------------------------------------------ Year-End Check
    def show_year_end_check(self, before_closing=False):
        """Shows the check; before closing, returns True when the user goes on."""
        year = int(getattr(self, "current_fiscal_year", 0) or 0)
        try: check = self.client.year_end_check(year)
        except Exception as exc:
            messagebox.showerror("Year-End Check", str(exc)); return False
        window = tk.Toplevel(self); window.title(f"Year-End Check {year}"); window.configure(bg=LIGHT); window.transient(self)
        self.fit_dialog(window, 1100, 560)
        colour = GREEN if not check["errors"] and not check["warnings"] else RED if check["errors"] else AMBER
        tk.Label(window, text=f"Year-End Check {year}: {check['summary']}", bg=LIGHT, fg=colour, font=("Segoe UI", 12, "bold"), anchor="w").pack(fill="x", padx=12, pady=(10, 4))
        frame = tk.Frame(window, bg=LIGHT); frame.pack(fill="both", expand=True, padx=12, pady=4)
        tree = ttk.Treeview(frame, columns=("status", "check", "result", "fix"), show="headings")
        for key, label, width in (("status", "Status", 80), ("check", "Check", 230), ("result", "Result", 470), ("fix", "What to do", 330)):
            tree.heading(key, text=label); tree.column(key, width=width, anchor="w", stretch=key in ("result", "fix"))
        scroll = ttk.Scrollbar(frame, orient="vertical", command=tree.yview); tree.configure(yscrollcommand=scroll.set)
        tree.pack(side="left", fill="both", expand=True); scroll.pack(side="right", fill="y")
        for status, tint in (("ERROR", "#f8d7d7"), ("WARNING", "#fdf0d5"), ("OK", "#e3f2ea")): tree.tag_configure(status, background=tint)
        for item in check["results"]: tree.insert("", "end", values=(item["status"], item["check"], item["detail"], item["fix"]), tags=(item["status"],))
        detail = tk.Label(window, text="Select a line to read it in full.", bg=LIGHT, fg=NAVY, anchor="w", justify="left", wraplength=1050); detail.pack(fill="x", padx=12)
        tree.bind("<<TreeviewSelect>>", lambda _e: detail.config(text="   ".join(str(v) for v in tree.item(tree.selection()[0], "values")) if tree.selection() else ""))
        answer = {"go": False}
        bar = tk.Frame(window, bg=LIGHT); bar.pack(fill="x", padx=12, pady=8)
        for label, fmt in (("Excel", "xlsx"), ("PDF", "pdf")):
            self.action_button(bar, label, lambda f=fmt: self.save_sections(f"Year-End Check {year}", [check["summary"]], check["sections"], f"Year_End_Check_{year}", f)).pack(side="left", padx=2)
        if before_closing:
            def go(): answer["go"] = True; window.destroy()
            if check["errors"]:
                tk.Label(bar, text="Correct the errors first (red lines).", bg=LIGHT, fg=RED, font=("Segoe UI", 9, "bold")).pack(side="left", padx=12)
            else:
                tk.Button(bar, text=f"Close {year} anyway" if check["warnings"] else f"Go on and close {year}", command=go, bg=RED, fg="white", border=0, padx=14, pady=6).pack(side="left", padx=12)
            self.action_button(bar, "Cancel", window.destroy).pack(side="left", padx=3)
            window.grab_set(); self.wait_window(window)
            return answer["go"]
        self.action_button(bar, "Close", window.destroy).pack(side="left", padx=12)
        return True
