"""Chart of Accounts tools (2.9.66): delete the selected accounts, find and delete accounts without transactions,
move an account's transactions to another account, or transfer its balance."""
from __future__ import annotations

from desktop_common import *  # noqa: F401,F403

SCOPE_LABELS = {"All accounts": "all", "Clients (411)": "clients", "Suppliers (401 / 403 / 404 / 408)": "suppliers", "Expenses (class 6)": "expenses",
                "Income (class 7)": "income", "Cash & banks (class 5)": "cash_bank", "Other payables (46)": "other_payables"}


class AccountToolsMixin:
    def account_tool_buttons(self, parent):
        tk.Button(parent, text="Delete Selected", command=self.delete_selected_accounts, bg="#8B1E1E", fg="white", border=0, padx=10, pady=6).pack(side="left", padx=4)
        self.action_button(parent, "Delete Unused Accounts...", self.unused_accounts_dialog).pack(side="left", padx=4)
        self.action_button(parent, "Move / Transfer...", self.move_account_dialog).pack(side="left", padx=4)

    def selected_account_codes(self):
        return [str(self.accounts_tree.item(iid, "values")[0]) for iid in self.accounts_tree.selection()]

    def _after_account_change(self):
        self._account_cache = None; self.__dict__.pop("_all_accounts", None)
        try: self.client.clear_cache()
        except Exception: pass
        self.load_accounts()
        for loader in ("load_parties", "load_trial"):
            try: getattr(self, loader)()
            except Exception: pass

    def _delete_account_codes(self, codes, title="Delete Accounts"):
        if not codes: return messagebox.showwarning(title, "Select the accounts first (Ctrl / Shift or drag the mouse for several)")
        shown = "\n".join(codes[:15]) + (f"\n... and {len(codes) - 15} more" if len(codes) > 15 else "")
        if not messagebox.askyesno(title, f"Delete {len(codes)} account(s)?\n\n{shown}\n\nOnly accounts without any transaction are deleted; "
                                   "a customer / supplier file that only holds that account is deleted with it."): return None
        try: result = self.client.delete_accounts(codes)
        except Exception as exc: return messagebox.showerror(title, str(exc))
        self._after_account_change()
        lines = [f'Deleted: {len(result["deleted"])}']
        lines += [f'  {d["code"]} {d["name"]}' + (f' (and {", ".join(d["parties"])})' if d["parties"] else "") for d in result["deleted"][:12]]
        if result["kept"]:
            lines += ["", f'Kept: {len(result["kept"])}'] + [f'  {k["code"]}: {k["reason"]}' for k in result["kept"][:12]]
        messagebox.showinfo(title, "\n".join(lines))
        return result

    def delete_selected_accounts(self):
        return self._delete_account_codes(self.selected_account_codes())

    def unused_accounts_dialog(self):
        window = tk.Toplevel(self); window.title("Accounts without transactions"); window.configure(bg=LIGHT); window.transient(self); self.fit_dialog(window, 820, 520)
        scope = tk.StringVar(value="All accounts")
        bar = tk.Frame(window, bg=LIGHT); bar.pack(fill="x", padx=10, pady=8)
        tk.Label(bar, text="Show", bg=LIGHT, font=("Segoe UI", 9, "bold")).pack(side="left")
        box = ttk.Combobox(bar, textvariable=scope, values=list(SCOPE_LABELS), state="readonly", width=32); box.pack(side="left", padx=6)
        info = tk.Label(window, text="", bg=LIGHT, fg=NAVY, anchor="w"); info.pack(fill="x", padx=12)
        frame = tk.Frame(window, bg=LIGHT); frame.pack(fill="both", expand=True, padx=10, pady=6)
        tree = ttk.Treeview(frame, columns=("code", "name", "type", "party"), show="headings", selectmode="extended")
        for key, label, width in (("code", "Account", 110), ("name", "Name", 330), ("type", "Type", 90), ("party", "Customer / Supplier", 220)):
            tree.heading(key, text=label); tree.column(key, width=width)
        scroll = ttk.Scrollbar(frame, orient="vertical", command=tree.yview); tree.configure(yscrollcommand=scroll.set)
        tree.pack(side="left", fill="both", expand=True); scroll.pack(side="right", fill="y"); enable_drag_select(tree)
        def load(_e=None):
            try: rows = self.client.unused_accounts(SCOPE_LABELS[scope.get()])
            except Exception as exc: return messagebox.showerror("Accounts", str(exc), parent=window)
            tree.delete(*tree.get_children())
            for r in rows: tree.insert("", "end", iid=r["code"], values=(r["code"], r["name"], r["type"], r.get("party") or ""))
            info.config(text=f"{len(rows)} account(s) without any transaction, sub-account or document (official chart accounts are never listed).")
        def delete(selected_only=True):
            codes = list(tree.selection()) if selected_only else list(tree.get_children())
            if self._delete_account_codes(codes, "Accounts without transactions"): load()
        box.bind("<<ComboboxSelected>>", load)
        buttons = tk.Frame(window, bg=LIGHT); buttons.pack(fill="x", padx=10, pady=8)
        tk.Button(buttons, text="Delete Selected", command=delete, bg="#8B1E1E", fg="white", border=0, padx=12, pady=6).pack(side="left")
        tk.Button(buttons, text="Delete All Listed", command=lambda: delete(False), bg="#6B1010", fg="white", border=0, padx=12, pady=6).pack(side="left", padx=6)
        tk.Button(buttons, text="Select All", command=lambda: tree.selection_set(tree.get_children()), bg=NAVY, fg="white", border=0, padx=12, pady=6).pack(side="left", padx=6)
        tk.Button(buttons, text="Close", command=window.destroy, bg=NAVY, fg="white", border=0, padx=12, pady=6).pack(side="right")
        load(); return window

    def move_account_dialog(self):
        selected = self.selected_account_codes()
        window = tk.Toplevel(self); window.title("Move / Transfer an account"); window.configure(bg=LIGHT); window.transient(self); self.fit_dialog(window, 720, 400)
        v = {"from": tk.StringVar(value=selected[0] if selected else ""), "to": tk.StringVar(), "mode": tk.StringVar(value="move"),
             "merge": tk.BooleanVar(value=True), "date": tk.StringVar(value=self.fiscal_today()), "description": tk.StringVar()}
        grid = tk.Frame(window, bg=LIGHT); grid.pack(fill="x", padx=14, pady=10)
        for row, (label, key) in enumerate((("From account", "from"), ("To account", "to"))):
            tk.Label(grid, text=label, bg=LIGHT, font=("Segoe UI", 9, "bold")).grid(row=row, column=0, sticky="w", pady=4)
            self.account_search_box(grid, v[key], 40).grid(row=row, column=1, sticky="w", padx=6, pady=4)
        modes = tk.LabelFrame(window, text="What to do", bg=LIGHT, padx=8, pady=6); modes.pack(fill="x", padx=14, pady=4)
        tk.Radiobutton(modes, text="Move ALL its transactions to the other account (history is reclassified; documents follow)", variable=v["mode"], value="move", bg=LIGHT).pack(anchor="w")
        tk.Checkbutton(modes, text="   and merge the customer / supplier of the From account into the one of the To account", variable=v["merge"], bg=LIGHT).pack(anchor="w")
        balance = tk.Frame(modes, bg=LIGHT); balance.pack(anchor="w", fill="x")
        tk.Radiobutton(balance, text="Transfer its BALANCE on", variable=v["mode"], value="balance", bg=LIGHT).pack(side="left")
        self.date_entry(balance, v["date"], 11).pack(side="left", padx=4)
        tk.Label(balance, text="with a journal voucher (history stays). Details", bg=LIGHT).pack(side="left")
        tk.Entry(balance, textvariable=v["description"], width=22).pack(side="left", padx=4)
        def run():
            source = v["from"].get().split(" - ", 1)[0].strip(); target = v["to"].get().split(" - ", 1)[0].strip()
            if not source or not target: return messagebox.showwarning("Move / Transfer", "Choose both accounts", parent=window)
            try:
                if v["mode"].get() == "move":
                    if not messagebox.askyesno("Move / Transfer", f"Move every transaction of {source} to {target}?\nA backup is advised first.", parent=window): return
                    result = self.client.move_account(source, target, bool(v["merge"].get()))
                    text = (f'{result["lines"]} journal line(s) and {result["documents"]} document field(s) moved from {source} to {target}.' +
                            (f'\n{result["merged_party"]} merged into the customer / supplier of {target}.' if result.get("merged_party") else "") +
                            f"\n\n{source} has no transactions now: delete it with Delete Selected if you no longer need it.")
                else:
                    result = self.client.transfer_account_balance(source, target, v["date"].get(), v["description"].get())
                    text = "\n".join(f'{x["voucher"]}: {abs(x["amount"]):,.2f} {x["currency"]} from {source} to {target}' for x in result["vouchers"])
            except Exception as exc: return messagebox.showerror("Move / Transfer", str(exc), parent=window)
            self._after_account_change()
            for loader in ("load_journal",):
                try: getattr(self, loader)()
                except Exception: pass
            messagebox.showinfo("Move / Transfer", text, parent=window); window.destroy()
        buttons = tk.Frame(window, bg=LIGHT); buttons.pack(fill="x", padx=14, pady=10)
        tk.Button(buttons, text="Run", command=run, bg=GOLD, fg=NAVY, border=0, padx=20, pady=6, font=("Segoe UI", 9, "bold")).pack(side="left")
        tk.Button(buttons, text="Cancel", command=window.destroy, bg=NAVY, fg="white", border=0, padx=14, pady=6).pack(side="left", padx=6)
        return window
