"""Chart of accounts and settings screens. (moved out of desktop.py in 2.9.41, unchanged)."""
from __future__ import annotations

from desktop_common import *  # noqa: F401,F403


class SettingsMixin:
    def build_accounts(self):
        controls=tk.Frame(self.accounts_tab,bg=LIGHT); controls.pack(fill="x",padx=10,pady=(10,0))
        self.new_account_code=tk.StringVar(); self.new_account_name=tk.StringVar(); self.new_account_parent=tk.StringVar(); self.new_account_type=tk.StringVar(value="expense")
        tk.Label(controls,text="Account (4-digit prefix = automatic):",bg=LIGHT,font=("Segoe UI",9,"bold"),fg=NAVY).pack(side="left",padx=(0,4))
        self.new_account_code_entry=tk.Entry(controls,textvariable=self.new_account_code,width=11); self.new_account_code_entry.pack(side="left",padx=3)
        self.new_account_code_entry.bind("<FocusOut>",self.preview_new_account_number); self.new_account_code_entry.bind("<Return>",self.preview_new_account_number)
        tk.Entry(controls,textvariable=self.new_account_name,width=22).pack(side="left",padx=3)
        tk.Entry(controls,textvariable=self.new_account_parent,width=9).pack(side="left",padx=3)
        ttk.Combobox(controls,textvariable=self.new_account_type,values=["asset","liability","equity","income","expense"],state="readonly",width=9).pack(side="left",padx=3)
        self.action_button(controls,"Create Account",self.save_new_account).pack(side="left",padx=5)
        self.action_button(controls,"Edit Selected Name",self.rename_selected_account).pack(side="left",padx=5)
        self.action_button(controls,tr(self.language.get(),"refresh"),self.load_accounts).pack(side="right")
        self.accounts_tree=self.table(self.accounts_tab,[
            ("code","Account",100),("parent","Parent",80),("english","English",270),
            ("french","French",270),("arabic","Arabic",270),("type","Type",90)])
        self.accounts_tree.bind("<Double-1>",lambda _event:self.load_selected_account_name())
        self.load_accounts()

    def save_new_account(self):
        try: account=self.client.save_account({"code":self.new_account_code.get(),"name_en":self.new_account_name.get(),"parent_code":self.new_account_parent.get(),"type":self.new_account_type.get()})
        except Exception as exc: return messagebox.showerror("Chart of Accounts",str(exc))
        self._account_cache=None
        if hasattr(self,"_all_accounts"): self._all_accounts[account["code"]]=account["name_en"]
        self.new_account_code.set(""); self.new_account_name.set(""); self.new_account_parent.set(""); self.load_accounts()
        messagebox.showinfo("Chart of Accounts",f'Account {account["code"]} created successfully')

    def preview_new_account_number(self,_event=None):
        prefix=self.new_account_code.get().strip()
        if len(prefix)!=4 or not prefix.isdigit(): return
        try: number=self.client.next_account_number(prefix)
        except Exception as exc: return messagebox.showwarning("Chart of Accounts",str(exc))
        self.new_account_parent.set(prefix); self.new_account_code.set(number)

    def load_selected_account_name(self):
        selected=self.accounts_tree.selection()
        if not selected: return
        values=self.accounts_tree.item(selected[0],"values"); self.new_account_code.set(values[0]); self.new_account_name.set(values[2])

    def rename_selected_account(self):
        selected=self.accounts_tree.selection()
        if not selected: return messagebox.showwarning("Chart of Accounts","Select an account first")
        code=str(self.accounts_tree.item(selected[0],"values")[0]); name=self.new_account_name.get().strip()
        try: self.client.rename_account(code,name)
        except Exception as exc: return messagebox.showerror("Chart of Accounts",str(exc))
        self.load_accounts(); messagebox.showinfo("Chart of Accounts",f"Account {code} name updated")

    def load_accounts(self):
        try:
            rows=self.client.accounts()
        except Exception as exc:
            return messagebox.showerror("Error",str(exc))
        self._all_accounts={str(row["code"]):row["name_en"] for row in rows}
        self.accounts_tree.delete(*self.accounts_tree.get_children())
        for row in rows:
            self.accounts_tree.insert("","end",values=(row["code"],row.get("parent_code") or "",
                row["name_en"],row.get("name_fr") or "",row.get("name_ar") or "",row["type"]))

    def build_settings(self):
        nested=ttk.Notebook(self.settings_tab); nested.pack(fill="both",expand=True,padx=10,pady=10)
        users=tk.Frame(nested,bg=LIGHT); backups=tk.Frame(nested,bg=LIGHT); rates=tk.Frame(nested,bg=LIGHT); branches=tk.Frame(nested,bg=LIGHT); general=tk.Frame(nested,bg=LIGHT)
        is_admin=(self.current_user or {}).get("role")=="admin"
        if is_admin: nested.add(users,text="Users & Permissions")
        is_viewer=(self.current_user or {}).get("role")=="viewer"
        if not is_viewer: nested.add(backups,text="Backup & Restore" if is_admin else "My Backups")
        nested.add(rates,text="Exchange Rates"); nested.add(branches,text="Branches"); nested.add(general,text="General Settings"); self.build_dimensions_pages(nested)
        if is_admin: self.build_users_page(users)
        if not is_viewer:
            backup_controls=tk.Frame(backups,bg=LIGHT); backup_controls.pack(fill="x",padx=10,pady=10)
            self.backup_scope=tk.Label(backups,text="",bg=LIGHT,fg=NAVY,font=("Segoe UI",10,"bold"),anchor="w"); self.backup_scope.pack(fill="x",padx=14,before=backup_controls)
            tk.Button(backup_controls,text="Create Backup Now",command=self.create_backup,bg=GOLD,fg=NAVY,border=0,padx=15,pady=7,font=("Segoe UI",9,"bold")).pack(side="left",padx=4)
            self.action_button(backup_controls,"Save Backup As... (USB / Drive)",self.save_backup_as).pack(side="left",padx=4)
            self.action_button(backup_controls,"Open Backup Folder",self.open_backup_folder).pack(side="left",padx=4)
            self.action_button(backup_controls,"Open Log Folder",self.open_log_folder).pack(side="left",padx=4)
            if is_admin: tk.Button(backup_controls,text="Restore Selected",command=self.restore_selected_backup,bg="#8B1E1E",fg="white",border=0,padx=15,pady=7).pack(side="left",padx=4)
            if is_admin:
                lock_bar=tk.LabelFrame(backups,text="Close the books (period lock)",bg=LIGHT,padx=8,pady=6); lock_bar.pack(fill="x",padx=10,pady=(0,6))
                self.books_lock_date=tk.StringVar()
                tk.Label(lock_bar,text="Lock up to (DD-MM-YYYY)",bg=LIGHT).pack(side="left",padx=(2,4))
                self.date_entry(lock_bar,self.books_lock_date,12).pack(side="left",padx=4)
                tk.Button(lock_bar,text="Lock",command=self.lock_books,bg=GOLD,fg=NAVY,border=0,padx=14,pady=5,font=("Segoe UI",9,"bold")).pack(side="left",padx=4)
                self.action_button(lock_bar,"Unlock",self.unlock_books).pack(side="left",padx=4)
                self.books_lock_label=tk.Label(lock_bar,text="",bg=LIGHT,fg=NAVY,font=("Segoe UI",9,"bold")); self.books_lock_label.pack(side="left",padx=12)
            tk.Label(backups,text="An automatic backup of this company and year is made every day when you open it (the newest 30 automatic copies are kept; manual and safety copies are never deleted). Keep a copy outside the computer too: Save Backup As... (USB / Drive).",bg=LIGHT,fg="#5f6b76",wraplength=1050,justify="left").pack(fill="x",padx=14)
            self.backups_tree=self.table(backups,[("name","Backup File",400),("kind","Type",100),("checked","Checked",90),("size","Size",100),("modified","Created",170)])
        rate_controls=tk.Frame(rates,bg=LIGHT); rate_controls.pack(fill="x",padx=10,pady=10)
        self.rate_date=tk.StringVar(value=datetime.now().strftime("%d-%m-%Y")); self.rate_date_to=tk.StringVar(value=datetime.now().strftime("%d-%m-%Y")); self.rate_from=tk.StringVar(value="USD"); self.rate_to=tk.StringVar(value="LBP"); self.rate_value=tk.StringVar(value="1")
        tk.Label(rate_controls,text="Date From",bg=LIGHT).pack(side="left"); self.date_entry(rate_controls,self.rate_date,12).pack(side="left",padx=4)
        tk.Label(rate_controls,text="Date To",bg=LIGHT).pack(side="left"); self.date_entry(rate_controls,self.rate_date_to,12).pack(side="left",padx=4)
        self.rate_from_box=ttk.Combobox(rate_controls,textvariable=self.rate_from,values=self.currency_codes,state="readonly",width=7); self.rate_from_box.pack(side="left",padx=4)
        tk.Label(rate_controls,text="to",bg=LIGHT).pack(side="left")
        self.rate_to_box=ttk.Combobox(rate_controls,textvariable=self.rate_to,values=self.currency_codes,state="readonly",width=7); self.rate_to_box.pack(side="left",padx=4)
        tk.Entry(rate_controls,textvariable=self.rate_value,width=14).pack(side="left",padx=4)
        self.action_button(rate_controls,"Add Daily Rate",self.save_exchange_rate).pack(side="left",padx=5)
        self.action_button(rate_controls,"Restore EUR Rates 2024-Today",self.restore_euro_rates).pack(side="left",padx=5)
        currency_controls=tk.Frame(rates,bg=LIGHT); currency_controls.pack(fill="x",padx=12,pady=(0,6))
        self.new_currency_code=tk.StringVar(); self.new_currency_name=tk.StringVar()
        tk.Label(currency_controls,text="Create currency",bg=LIGHT,font=("Segoe UI",9,"bold")).pack(side="left",padx=(0,6))
        tk.Entry(currency_controls,textvariable=self.new_currency_code,width=7).pack(side="left")
        tk.Label(currency_controls,text="Code (3 letters)",bg=LIGHT).pack(side="left",padx=(3,12))
        tk.Entry(currency_controls,textvariable=self.new_currency_name,width=22).pack(side="left")
        tk.Label(currency_controls,text="Name",bg=LIGHT).pack(side="left",padx=(3,8))
        self.action_button(currency_controls,"Add Currency",self.create_currency).pack(side="left",padx=4)
        tk.Label(currency_controls,text="Set a rate before using it in another currency's report.",bg=LIGHT,fg="#5f6b76").pack(side="left",padx=8)
        self.rates_tree=self.table(rates,[("date","Date",110),("from","From",80),("to","To",80),("rate","Daily Average",150),("samples","Entries",75),("created","Saved",180)])
        self.rates_tree.bind("<Double-1>",lambda _event:self.edit_selected_exchange_rate())
        branch_controls=tk.Frame(branches,bg=LIGHT); branch_controls.pack(fill="x",padx=10,pady=10)
        self.new_branch_name=tk.StringVar(); tk.Label(branch_controls,text="New Branch Name",bg=LIGHT).pack(side="left"); tk.Entry(branch_controls,textvariable=self.new_branch_name,width=32).pack(side="left",padx=6)
        self.action_button(branch_controls,"Save Branch",self.save_branch).pack(side="left",padx=4)
        self.branches_tree=self.table(branches,[("id","ID",80),("name","Branch Name",320),("active","Active",90)])
        self.base_currency=tk.StringVar(value="USD"); self.backup_hours=tk.StringVar(value="24")
        self.company_fields={key:tk.StringVar() for key in ("company_name","company_address","company_phone","company_mof","company_nssf","company_email","company_website","company_logo")}
        tk.Label(general,text="Base Currency",bg=LIGHT).grid(row=0,column=0,padx=14,pady=14,sticky="w")
        self.base_currency_box=ttk.Combobox(general,textvariable=self.base_currency,values=self.currency_codes,state="readonly",width=15); self.base_currency_box.grid(row=0,column=1,padx=14,pady=14)

        for row,(key,label) in enumerate((("company_name","Company Name"),("company_address","Address"),("company_phone","Phone"),("company_mof","MOF / VAT Number"),("company_nssf","NSSF Employer Number"),("company_email","Email"),("company_website","Website"),("company_logo","Logo File Path")),2):
            tk.Label(general,text=label,bg=LIGHT).grid(row=row,column=0,padx=14,pady=7,sticky="w")
            tk.Entry(general,textvariable=self.company_fields[key],width=42).grid(row=row,column=1,padx=14,pady=7,sticky="w")
        self.company_vat_registered=tk.StringVar(value="Yes"); self.company_vat_date=tk.StringVar()
        tk.Label(general,text="Registered in VAT",bg=LIGHT).grid(row=10,column=0,padx=14,pady=7,sticky="w")
        ttk.Combobox(general,textvariable=self.company_vat_registered,values=["Yes","No"],state="readonly",width=15).grid(row=10,column=1,padx=14,pady=7,sticky="w")
        tk.Label(general,text="VAT Registration Date",bg=LIGHT).grid(row=11,column=0,padx=14,pady=7,sticky="w")
        self.date_entry(general,self.company_vat_date,42).grid(row=11,column=1,padx=14,pady=7,sticky="w")
        self.action_button(general,"Save Settings",self.save_general_settings).grid(row=12,column=0,columnspan=2,pady=14)
        self.load_settings_pages()

    def load_settings_pages(self):
        if not hasattr(self,"rates_tree"): return
        try:
            settings=self.client.settings(); rates=self.client.exchange_rates()
            self.refresh_books_lock()
            self.base_currency.set(settings.get("base_currency","USD")); self.backup_hours.set(settings.get("backup_interval_hours","24"))
            for key,var in self.company_fields.items(): var.set(settings.get(key,"Saber for Audit" if key=="company_name" else ""))
            self.company_vat_registered.set(settings.get("company_vat_registered","Yes") or "Yes"); self.company_vat_date.set(settings.get("company_vat_date","") or "")
        except Exception as exc: return messagebox.showerror("Settings",str(exc))
        self.rates_tree.delete(*self.rates_tree.get_children())
        for row in rates: self.rates_tree.insert("","end",values=(row["rate_date"],row["from_currency"],row["to_currency"],row["rate"],row.get("samples",0),row["created_at"][:19]))
        try: branch_rows=self.client.branches()
        except Exception: branch_rows=[]
        self.branches_tree.delete(*self.branches_tree.get_children())
        for row in branch_rows: self.branches_tree.insert("","end",values=(row["id"],row["name"],"Yes" if row["active"] else "No"))
        backups=[]
        if hasattr(self,"backups_tree"):
            try: backups=self.client.backups()
            except Exception: backups=[]
            self.backups_tree.delete(*self.backups_tree.get_children())
        if (self.current_user or {}).get("role")=="admin":
            try: users=self.client.users()
            except Exception: users=[]
            self.users_tree.delete(*self.users_tree.get_children()); self.fill_users_tree(users)
        if hasattr(self,"backups_tree"):
            for row in backups: self.backups_tree.insert("","end",iid=row["name"],values=(row["name"],row.get("kind","backup"),row.get("checked","not checked"),f'{row["size"]/1024/1024:,.2f} MB',row["modified"][:19].replace("T"," ")))
        if hasattr(self,"backup_scope"): self.backup_scope.config(text=f'Backups of {getattr(self,"current_company",{}).get("name","")} - fiscal year {getattr(self,"current_fiscal_year","")}')

    def save_branch(self):
        try: branch=self.client.save_branch(self.new_branch_name.get().strip())
        except Exception as exc: return messagebox.showerror("Branches",str(exc))
        self.new_branch_name.set(""); self.load_settings_pages(); messagebox.showinfo("Branches",f'Branch {branch["name"]} saved successfully')

    def create_backup(self):
        try: result=self.client.create_backup()
        except Exception as exc: return messagebox.showerror("Backup",str(exc))
        self.load_settings_pages(); messagebox.showinfo("Backup",f'Backup created:\n{result["path"]}')

    def save_backup_as(self):
        selected=self.backups_tree.selection()
        if not selected:
            if not messagebox.askyesno("Save Backup As","No backup is selected. Create a new backup now and save a copy?"): return
            try: name=Path(self.client.create_backup()["path"]).name
            except Exception as exc: return messagebox.showerror("Backup",str(exc))
            self.load_settings_pages()
        else: name=selected[0]
        path=filedialog.asksaveasfilename(initialfile=name,defaultextension=".db",filetypes=[("Saber backup","*.db")])
        if not path: return
        try: Path(path).write_bytes(self.client.download_backup(name)["content"])
        except Exception as exc: return messagebox.showerror("Save Backup As",str(exc))
        messagebox.showinfo("Save Backup As",f"Backup copied to:\n{path}")

    def open_backup_folder(self):
        try: folder=self.client.backup_folder(); Path(folder).mkdir(parents=True,exist_ok=True)
        except Exception as exc: return messagebox.showerror("Backups",str(exc))
        try:
            if os.name=="nt": os.startfile(folder)
            else: raise RuntimeError
        except Exception: messagebox.showinfo("Backups",f"Backup folder:\n{folder}")

    def open_log_folder(self):
        """Error log of this computer (logs/saber.log in the Saber data folder) - send it when reporting a problem."""
        import app_runtime
        folder=app_runtime.data_dir()/"logs"; folder.mkdir(parents=True,exist_ok=True)
        try:
            if os.name=="nt": os.startfile(folder)
            else: raise RuntimeError
        except Exception: messagebox.showinfo("Log",f"Log folder:\n{folder}")

    def restore_selected_backup(self):
        selected=self.backups_tree.selection()
        if not selected: return messagebox.showwarning("Restore","Select one backup")
        if not messagebox.askyesno("Restore Database","Restore this backup? A safety backup of current data will be created first."): return
        try: self.client.restore_backup(selected[0])
        except Exception as exc: return messagebox.showerror("Restore",str(exc))
        messagebox.showinfo("Restore","Database restored successfully. Refreshing all pages."); self.load_dashboard(); self.load_invoices(); self.load_journal(); self.load_trial(); self.load_settings_pages(); self.load_payroll(); self.load_transactions(); self.load_vat_return()

    def save_exchange_rate(self):
        try: self.client.save_exchange_rate({"date_from":self.rate_date.get(),"date_to":self.rate_date_to.get(),"from_currency":self.rate_from.get(),"to_currency":self.rate_to.get(),"rate":self.rate_value.get()})
        except Exception as exc: return messagebox.showerror("Exchange Rates",str(exc))
        self.load_settings_pages(); messagebox.showinfo("Exchange Rates","Rate added. The daily rate is the average of all entered rates for this date and currency pair.")

    def create_currency(self):
        try: item=self.client.save_currency(self.new_currency_code.get(),self.new_currency_name.get())
        except Exception as exc: return messagebox.showerror("Currencies",str(exc))
        previous=set(self.currency_codes)
        self.currency_codes=[row["code"] for row in self.client.currencies()]
        def refresh(widget):
            if isinstance(widget,ttk.Combobox):
                choices=list(widget["values"])
                existing=set(choices)
                if existing==previous: widget["values"]=self.currency_codes
                elif existing==previous|{"All Currencies"}: widget["values"]=["All Currencies"]+self.currency_codes
                elif existing==previous|{"account"}: widget["values"]=["account"]+self.currency_codes
                elif existing==previous|{"account","none"}: widget["values"]=["account"]+self.currency_codes+["none"]
            for child in widget.winfo_children(): refresh(child)
        refresh(self)
        for state in (getattr(self,"trial_state",None),getattr(self,"statement_state",None)):
            if state and item["code"] not in state["currencies"]:
                var=tk.BooleanVar(value=True); state["currencies"][item["code"]]=var
                tk.Checkbutton(state["dimension_row"],text=item["code"],variable=var,bg=LIGHT).pack(side="left")
        self.new_currency_code.set(""); self.new_currency_name.set("")
        messagebox.showinfo("Currencies",f'{item["code"]} added. Set its exchange rate before using cross-currency reports.')

    def edit_selected_exchange_rate(self):
        selected=self.rates_tree.selection()
        if not selected: return
        values=self.rates_tree.item(selected[0],"values")
        self.rate_date.set(values[0]); self.rate_date_to.set(values[0]); self.rate_from.set(values[1]); self.rate_to.set(values[2]); self.rate_value.set(values[3])

    def restore_euro_rates(self):
        if not messagebox.askyesno("Exchange Rates","Restore daily EUR to USD and EUR to LBP rates from 01-01-2024 until today?"): return
        try: result=self.client.restore_euro_rates()
        except Exception as exc: return messagebox.showerror("Exchange Rates",str(exc))
        self.load_settings_pages(); messagebox.showinfo("Exchange Rates",f'Restored {result.get("days",0)} days from 01-01-2024 until today')

    def refresh_books_lock(self):
        label=getattr(self,"books_lock_label",None)
        if label is None or not label.winfo_exists(): return
        try: lock=self.client.books_lock()
        except Exception: return
        label.config(text=f"Books are LOCKED up to {lock['display']}: nothing dated on or before it can be posted, changed or deleted." if lock.get("display")
                     else "Books are open: no period is locked.", fg="#8B1E1E" if lock.get("display") else NAVY)
        if lock.get("display"): self.books_lock_date.set(lock["display"])

    def lock_books(self):
        date=self.books_lock_date.get().strip()
        if not date: return messagebox.showwarning("Close the books","Enter the last date to lock (for example the last day of the month or quarter you filed)")
        if not messagebox.askyesno("Close the books",f"Lock the books up to {date}?\n\nNo invoice, expense, payment, payroll or journal entry dated on or before {date} can be added, changed or deleted until an administrator unlocks it. A safety backup is made first."): return
        try: self.client.set_books_lock(date)
        except Exception as exc: return messagebox.showerror("Close the books",str(exc))
        self.refresh_books_lock(); self.load_settings_pages()

    def unlock_books(self):
        if not messagebox.askyesno("Close the books","Unlock all periods? Closed months can then be changed again. A safety backup is made first."): return
        try: self.client.set_books_lock("")
        except Exception as exc: return messagebox.showerror("Close the books",str(exc))
        self.books_lock_date.set(""); self.refresh_books_lock(); self.load_settings_pages()

    def save_general_settings(self):
        payload={"base_currency":self.base_currency.get(),"backup_interval_hours":self.backup_hours.get()}
        payload.update({key:var.get().strip() for key,var in self.company_fields.items()})
        payload["company_vat_registered"]=self.company_vat_registered.get(); payload["company_vat_date"]=self.company_vat_date.get().strip()
        try: self.client.save_settings(payload)
        except Exception as exc: return messagebox.showerror("Settings",str(exc))
        messagebox.showinfo("Settings","Settings saved successfully")
