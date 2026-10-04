from __future__ import annotations

from desktop_common import *  # noqa: F401,F403
from desktop_common import _enable_windows_dpi_awareness
import logging
import app_runtime

log = logging.getLogger("saber.desktop")
from desktop_final import FinalFeaturesMixin
from desktop_assets import AssetsMixin
from cnss_forms_ui import CNSSFormsMixin
from desktop_brains import BrainsScreensMixin
from desktop_dimensions import DimensionsMixin
from desktop_stage3 import Stage3Mixin
from desktop_inventory import InventoryMixin
from desktop_production import ProductionMixin
from desktop_account_tools import AccountToolsMixin
from desktop_v22 import V22Mixin
from desktop_invoices import InvoicesMixin
from desktop_parties import PartiesMixin
from desktop_payroll import PayrollMixin
from desktop_reports import ReportsMixin
from desktop_settings import SettingsMixin
from desktop_payroll_sheet import PayrollSheetMixin
from desktop_projection import ProjectionMixin

class SaberApp(ProjectionMixin, PayrollSheetMixin, InvoicesMixin, PartiesMixin, PayrollMixin, ReportsMixin, SettingsMixin, AssetsMixin, V22Mixin, InventoryMixin, ProductionMixin, AccountToolsMixin, Stage3Mixin, DimensionsMixin, BrainsScreensMixin, FinalFeaturesMixin, CNSSFormsMixin, tk.Tk):
    def __init__(self):
        _enable_windows_dpi_awareness()
        super().__init__()
        self._collect_garbage_on_screen_thread()
        self.title(f"Saber Accounting {app_runtime.APP_VERSION}")
        # Saber icon on the window and the taskbar (Windows): inside the program, or installed next to it (2.9.57)
        if sys.platform == "win32":
            for icon in (resource_path("assets/saber.ico"), Path(sys.executable).parent / "saber.ico", Path(__file__).resolve().parent / "Assets" / "saber.ico"):
                try:
                    if Path(icon).exists(): self.iconbitmap(default=str(icon)); break
                except tk.TclError: continue
        screen_width, screen_height = self.winfo_screenwidth(), self.winfo_screenheight()
        try: dpi_scale=max(1.0,min(2.0,self.winfo_fpixels("1i")/96.0))
        except tk.TclError: dpi_scale=1.0
        width,height,min_width,min_height=initial_window_size(screen_width,screen_height,dpi_scale)
        self.geometry(f"{width}x{height}")
        self.minsize(min_width,min_height)
        if sys.platform == "win32":
            try: self.state("zoomed")
            except tk.TclError: pass
        self.configure(bg=LIGHT)
        self.language = tk.StringVar(value="en")
        self.client = None
        self.current_user = None
        self.last_activity = time.monotonic()
        self.import_rows = []
        self.sales_items = []
        self.manual_items = []
        self.view_currency = tk.StringVar(value="All Currencies")
        self.dashboard_base_currency=tk.StringVar(value="All Currencies")
        self.dashboard_display_currency=tk.StringVar(value="Original")
        self.import_view_currency = tk.StringVar(value="All Currencies")
        self.trial_from_date = tk.StringVar()
        self.trial_to_date = tk.StringVar()
        self.trial_account = tk.StringVar(); self.trial_account_from=tk.StringVar(); self.trial_account_to=tk.StringVar(); self.trial_scope=tk.StringVar(value="Detailed Trial Balance"); self.trial_display_currency=tk.StringVar(value="USD + LBP")
        self.trial_posting_status=tk.StringVar(value="Posted Only")
        self.invoice_account_search=tk.StringVar()
        self.invoice_sort_by=tk.StringVar(value="Date"); self.invoice_sort_order=tk.StringVar(value="Descending")
        self.invoice_branch=tk.StringVar(value="All Branches"); self.manual_branch=tk.StringVar(value="Head Office"); self.trial_branch=tk.StringVar(value="All Branches"); self.statement_branch=tk.StringVar(value="All Branches")
        self.statement_party = tk.StringVar()
        self.statement_from_date = tk.StringVar()
        self.statement_to_date = tk.StringVar()
        self.statement_currency = tk.StringVar(value="All Currencies")
        self.statement_display_currency = tk.StringVar(value="Original")
        self.statement_include_opening = tk.BooleanVar(value=True)
        self.journal_from_date = tk.StringVar()
        self.journal_to_date = tk.StringVar()
        self.journal_view_year = tk.StringVar()
        self.journal_section = tk.StringVar(value="All Sections")
        self.journal_sort_by=tk.StringVar(value="Date"); self.journal_sort_order=tk.StringVar(value="Ascending")
        self.pnl_from_date = tk.StringVar(value=f"01-01-{datetime.now().year}")
        self.pnl_to_date = tk.StringVar(value=f"31-12-{datetime.now().year}")
        self.close_year = tk.StringVar(value=str(datetime.now().year))
        self.report_from_date = tk.StringVar(value=f"01-01-{datetime.now().year}")
        self.report_to_date = tk.StringVar(value=f"31-12-{datetime.now().year}")
        self.ageing_as_of=tk.StringVar(value=datetime.now().strftime("%d-%m-%Y"))
        self.ageing_from=tk.StringVar(); self.ageing_to=tk.StringVar()
        self.ledger_account = tk.StringVar()
        self.report_account_from=tk.StringVar(); self.report_account_to=tk.StringVar()
        self.active_account_variable=None
        self._style()
        self.report_callback_exception=self._report_callback_error
        self.bind_all("<F2>",self.open_active_account_lookup)
        self.install_mouse_wheel(); self.install_field_right_click(); self.install_date_dashes()
        self.bind_all("<Control-f>",self.focus_page_search); self.bind_all("<Control-F>",self.focus_page_search)
        self.login_screen()

    def start_update_check(self):
        """Look for a newer version in the background (at most once a day); show a small notice if found."""
        # Only the installed program checks (not when run from the source code or by the tests).
        if getattr(self,"_update_checked",False) or not getattr(sys,"frozen",False) or os.environ.get("SABER_NO_UPDATE_CHECK"): return
        self._update_checked=True; result={}
        def work():
            result["found"]=app_runtime.check_for_update()
        thread=threading.Thread(target=work,name="SaberUpdateCheck",daemon=True); thread.start()
        def poll():
            if thread.is_alive(): self.after(1000,poll); return
            if result.get("found"): self.show_update_notice(result["found"])
        self.after(1000,poll)

    def show_update_notice(self,found):
        bar=getattr(self,"update_notice_bar",None)
        if bar is None or not bar.winfo_exists(): return
        def open_page():
            import webbrowser
            if found.get("url"): webbrowser.open(found["url"])
            messagebox.showinfo("Update",f"Saber Accounting {found['version']} is available.\n\n1. Make a backup (Settings > Backup & Restore > Create Backup Now).\n2. Download SaberAccountingSetup.exe and run it; your data is kept.")
        tk.Button(bar,text=f"New version {found['version']} available",command=open_page,bg=GOLD,fg=NAVY,border=0,padx=10,font=("Segoe UI",9,"bold")).pack(side="right",padx=8)

    def open_user_guide(self):
        """The user guide (English and Arabic) that ships with the program."""
        path=resource_path("assets/user_guide.html")
        try:
            import webbrowser
            if not Path(path).exists(): raise FileNotFoundError(str(path))
            webbrowser.open(Path(path).resolve().as_uri())
        except Exception as exc:
            log.warning("User guide could not be opened", exc_info=True)
            messagebox.showerror("Help",f"The user guide could not be opened: {exc}")

    def _report_callback_error(self, kind, value, tb):
        """A button or screen action failed: write the details to the log and tell the user."""
        if kind.__name__ == "SessionExpired":  # the sign-in screen is already shown
            log.info("Session ended during a screen action"); return
        log.error("Screen action failed", exc_info=(kind, value, tb))
        try: messagebox.showerror("Saber Accounting", f"Something went wrong: {value}\n\nYour saved data is safe. The details were written to the log file (Settings > Backup & Restore > Open Log Folder).")
        except Exception: logging.getLogger("saber.ignored").debug("Ignored error", exc_info=True)

    def _style(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TNotebook", background=LIGHT, borderwidth=0)
        style.configure("TNotebook.Tab", padding=(12, 9), font=("Segoe UI", 9, "bold"), background="#E5ECF2", foreground=NAVY)
        style.map("TNotebook.Tab", background=[("selected", "white"), ("active", "#D6E4ED")], foreground=[("selected", NAVY)])
        style.configure("Treeview", rowheight=31, font=("Segoe UI", 10), background="white", fieldbackground="white", foreground=NAVY)
        style.map("Treeview", background=[("selected", "#D6E4ED")], foreground=[("selected", NAVY)])
        style.configure("Treeview.Heading", background=NAVY, foreground="white", font=("Segoe UI", 10, "bold"))
        style.map("Treeview.Heading", background=[("active", NAVY)])
        style.configure("TCombobox", padding=4)
        style.configure("Sales.Treeview", rowheight=28, font=("Segoe UI", 10))
        # lighter, calmer look: shorter rows (more lines on screen), soft heading, clean inputs
        style.configure("Treeview", rowheight=27)  # 2.9.59: 10 pt text in tables
        style.configure("Treeview.Heading", background="#23405E", relief="flat", padding=(4, 5))
        style.map("Treeview.Heading", background=[("active", "#2E5277")])
        style.configure("TLabelframe", background=LIGHT); style.configure("TLabelframe.Label", background=LIGHT, foreground=NAVY, font=("Segoe UI", 9, "bold"))
        style.configure("Vertical.TScrollbar", arrowsize=12); style.configure("Horizontal.TScrollbar", arrowsize=12)
        self.option_add("*Font", ("Segoe UI", 9))
        self.option_add("*Entry.relief", "solid"); self.option_add("*Entry.borderWidth", 1)
        self.option_add("*Entry.highlightThickness", 1); self.option_add("*Entry.highlightColor", GOLD); self.option_add("*Entry.highlightBackground", "#C9D3DD")
        self.option_add("*LabelFrame.foreground", NAVY); self.option_add("*LabelFrame.font", ("Segoe UI", 9, "bold"))
        self.option_add("*Button.cursor", "hand2"); self.option_add("*Button.relief", "flat")
        # buttons light up under the mouse
        def hover(event, entering):
            widget = event.widget
            try:
                if entering:
                    widget._saber_bg = widget.cget("background"); color = widget._saber_bg.lstrip("#")
                    if len(color) == 6:
                        lighter = "#" + "".join(f"{min(255, int(color[i:i + 2], 16) + 28):02x}" for i in (0, 2, 4)); widget._saber_hover = lighter; widget.configure(background=lighter)
                elif getattr(widget, "_saber_bg", None) and str(widget.cget("background")).lower() == str(getattr(widget, "_saber_hover", "")).lower():
                    widget.configure(background=widget._saber_bg)  # only undo our own highlight
            except Exception: logging.getLogger("saber.ignored").debug("Ignored error", exc_info=True)
        self.bind_class("Button", "<Enter>", lambda e: hover(e, True), add="+"); self.bind_class("Button", "<Leave>", lambda e: hover(e, False), add="+")

    # ------------------------------------------------------------ mouse wheel scrolling
    def install_mouse_wheel(self):
        """One wheel handler for the whole program: it scrolls whatever is under the mouse pointer.
        Tables, lists and text boxes scroll themselves; everywhere else the page scrolls. A drop-down
        list under the pointer no longer changes its value by accident, the page scrolls instead."""
        def steps(event):
            if getattr(event, "num", None) == 4: return -1
            if getattr(event, "num", None) == 5: return 1
            delta = getattr(event, "delta", 0) or 0
            if not delta: return 0
            return -int(delta / 120) if abs(delta) >= 120 else (-1 if delta > 0 else 1)
        def scrolls_itself(widget, horizontal):
            try:
                if widget.winfo_class() not in ("Treeview", "Text", "Listbox"): return False
                first, last = (widget.xview() if horizontal else widget.yview())
                return float(first) > 0.0 or float(last) < 1.0
            except Exception: return False
        def scroll_page(event, skip_self_scrolling=True):
            amount = steps(event)
            if not amount: return
            horizontal = bool(getattr(event, "state", 0) & 0x0001)  # Shift + wheel scrolls sideways
            try: widget = self.winfo_containing(event.x_root, event.y_root)
            except Exception: widget = None
            while widget is not None:
                if skip_self_scrolling and scrolls_itself(widget, horizontal): return  # its own binding scrolled it
                if getattr(widget, "_saber_scroll_page", False):
                    try:
                        view = widget.xview() if horizontal else widget.yview()
                        if float(view[0]) > 0.0 or float(view[1]) < 1.0:
                            (widget.xview_scroll if horizontal else widget.yview_scroll)(amount, "units")
                    except tk.TclError: pass
                    return "break"
                widget = getattr(widget, "master", None)
        self._scroll_page_under_pointer = scroll_page
        for sequence in ("<MouseWheel>", "<Shift-MouseWheel>", "<Button-4>", "<Button-5>", "<Shift-Button-4>", "<Shift-Button-5>"):
            self.bind_all(sequence, scroll_page, add="+")
            self.bind_class("TCombobox", sequence, lambda event: (scroll_page(event, False), "break")[1])

    def register_scroll_page(self, canvas):
        canvas._saber_scroll_page = True; return canvas

    # ------------------------------------------------------------ dates typed as digits get their dashes
    DATE_LABEL_WORDS=("date","expiry","issue","as of","birth","valid until","retro","period")
    DATE_LABEL_EXACT=("from","to","date from","date to","from date","to date","dob")

    def install_date_dashes(self):
        """Every date field (not only the ones built with date_entry) turns 31122025 into 31-12-2025 while
        typing. A field counts as a date when it was marked as one, when its label says Date / From / To /
        Expiry / Issue / Period ..., or when it already holds a DD-MM-YYYY date."""
        self.bind_class("Entry","<KeyRelease>",self._auto_dash_any_date,add="+")

    def _looks_like_date_field(self,widget):
        if getattr(widget,"_saber_date",None) is not None: return widget._saber_date
        try: current=widget.get().strip()
        except Exception: current=""
        if len(current)==10 and current[2]=="-" and current[5]=="-" and current.replace("-","").isdigit(): return True
        try:
            siblings=widget.master.winfo_children(); index=siblings.index(widget)
        except Exception: return False
        for sibling in reversed(siblings[:index]):
            if sibling.winfo_class()=="Label":
                text=str(sibling.cget("text") or "").strip().lower().rstrip(":")
                return text in self.DATE_LABEL_EXACT or any(word in text for word in self.DATE_LABEL_WORDS)
            if sibling.winfo_class() in ("Entry","TCombobox","Checkbutton","Button"): return False
        return False

    def _auto_dash_any_date(self,event):
        widget=event.widget
        if getattr(widget,"_saber_date_entry",False): return  # date_entry fields do this themselves
        if event.keysym in ("BackSpace","Delete","Left","Right","Home","End","Tab","Shift_L","Shift_R","Return","Escape"): return
        if len(event.keysym)!=1 or not event.keysym.isdigit(): return
        try: value=widget.get()
        except Exception: return
        if not value or any(ch.isalpha() for ch in value) or (len(value)>=5 and value[4]=="-"): return
        if not value.replace("-","").isdigit(): return
        if getattr(widget,"_saber_date",None) is None: widget._saber_date=self._looks_like_date_field(widget)
        if not widget._saber_date: return
        formatted=auto_dash_date(value)
        if formatted!=value:
            try: widget.delete(0,"end"); widget.insert(0,formatted); widget.icursor("end")
            except Exception: logging.getLogger("saber.ignored").debug("Ignored error", exc_info=True)

    # ------------------------------------------------------------ right-click search in any field
    def install_field_right_click(self):
        """Right-click inside a field opens the search that belongs to it (F2 does the same):
        account fields list the saved accounts, customer / supplier fields the saved parties, item
        cells the saved items. Other fields get a small menu to search accounts, parties or items
        and put the choice in the field, plus Cut / Copy / Paste."""
        for widget_class in ("Entry", "TEntry", "TCombobox", "Spinbox"):
            for sequence in (("<Button-3>", "<Button-2>") if sys.platform == "darwin" else ("<Button-3>",)):
                self.bind_class(widget_class, sequence, self.field_right_click, add="+")

    def field_right_click(self, event):
        widget = event.widget
        try: widget.focus_set()
        except Exception: logging.getLogger("saber.ignored").debug("Ignored error", exc_info=True)
        self.active_account_variable = getattr(widget, "_account_var", self.active_account_variable)
        # 1) a field that knows its own list (customers / suppliers, items, accounts)
        node = widget
        while node is not None:
            action = getattr(node, "_f2", None)
            if action: self.after_idle(action); return "break"
            if getattr(node, "_account_var", None) is not None:
                variable = node._account_var; self.after_idle(lambda: self.open_account_lookup(variable)); return "break"
            node = getattr(node, "master", None)
        # 2) a cell editor or field with its own F2 search (Journal Voucher account cell, ...)
        try: own_f2 = widget.bind("<F2>")
        except Exception: own_f2 = ""
        if own_f2: self.after_idle(lambda: widget.event_generate("<F2>")); return "break"
        # 3) any other field: offer the searches and the usual editing commands
        self.field_search_menu(widget, event)
        return "break"

    def field_search_menu(self, widget, event):
        try: state = str(widget.cget("state"))
        except Exception: state = "normal"
        editable = state not in ("disabled", "readonly")
        class _FieldValue:
            def __init__(self, target): self.target = target
            def get(self):
                try: return self.target.get()
                except Exception: return ""
            def set(self, value):
                try:
                    if isinstance(self.target, ttk.Combobox): self.target.set(value); self.target.event_generate("<<ComboboxSelected>>")
                    else: self.target.delete(0, "end"); self.target.insert(0, value)
                except Exception: logging.getLogger("saber.ignored").debug("Ignored error", exc_info=True)
        target = _FieldValue(widget)
        menu = tk.Menu(widget, tearoff=0)
        state_for = lambda allowed: "normal" if allowed else "disabled"
        menu.add_command(label="Search accounts…  (F2)", state=state_for(editable), command=lambda: self.open_account_lookup(target))
        menu.add_command(label="Search customers / suppliers…", state=state_for(editable), command=lambda: self.party_search_into(target))
        if hasattr(self, "item_picker"):
            menu.add_command(label="Search items…", state=state_for(editable), command=lambda: self.item_picker(lambda sku: target.set(sku)))
        menu.add_separator()
        for label, virtual, allowed in (("Cut", "<<Cut>>", editable), ("Copy", "<<Copy>>", True), ("Paste", "<<Paste>>", editable)):
            menu.add_command(label=label, state=state_for(allowed), command=lambda v=virtual: widget.event_generate(v))
        def select_all():
            try: widget.select_range(0, "end"); widget.icursor("end")
            except Exception: logging.getLogger("saber.ignored").debug("Ignored error", exc_info=True)
        menu.add_command(label="Select all", command=select_all)
        try: menu.tk_popup(event.x_root, event.y_root)
        finally: menu.grab_release()

    def party_search_into(self, target):
        """Customers / suppliers search whose choice is written into any field."""
        try: parties = self.client.parties()
        except Exception as exc: return messagebox.showerror("Customers / Suppliers", str(exc))
        window = tk.Toplevel(self); window.title("Customers / Suppliers - Search"); self.fit_dialog(window,700,420); window.configure(bg=LIGHT); window.transient(self); window.grab_set()
        search = tk.StringVar(); entry = tk.Entry(window, textvariable=search, width=40); entry.pack(padx=10, pady=8); entry.focus_set()
        tree = ttk.Treeview(window, columns=("name", "account", "kind", "currency"), show="headings"); tree.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        for key, label, width in (("name", "Name", 300), ("account", "Account", 110), ("kind", "Type", 90), ("currency", "Currency", 70)): tree.heading(key, text=label); tree.column(key, width=width)
        def fill(*_args):
            tree.delete(*tree.get_children()); text = search.get().casefold()
            for party in parties:
                if not text or text in f'{party["name"]} {party.get("account_number") or ""} {party.get("tax_number") or ""}'.casefold():
                    tree.insert("", "end", iid=str(party["id"]), values=(party["name"], party.get("account_number") or "", party["kind"], party.get("currency") or ""))
        def choose(_event=None):
            if not tree.selection(): return
            party = next(p for p in parties if str(p["id"]) == tree.selection()[0]); window.destroy(); target.set(party["name"])
        search.trace_add("write", fill); tree.bind("<Double-1>", choose); tree.bind("<Return>", choose)
        entry.bind("<Return>", lambda _event: (tree.selection_set(tree.get_children()[0]), choose()) if tree.get_children() else None); fill()

    def clear(self):
        for child in self.winfo_children(): child.destroy()

    def fiscal_today(self):
        today=datetime.now()
        year=int(getattr(self,"current_fiscal_year",today.year))
        return today.strftime("%d-%m-%Y") if year==today.year else f"01-01-{year}"

    def date_entry(self,parent,variable,width=13):
        entry=tk.Entry(parent,textvariable=variable,width=width); entry._saber_date_entry=True
        def dashes(event=None):
            if event is not None and event.keysym in ("BackSpace","Delete","Left","Right","Home","End","Tab","Shift_L","Shift_R"): return
            value=variable.get()
            if not value or any(ch.isalpha() for ch in value) or (len(value)==10 and value[4]=="-"): return
            formatted=auto_dash_date(value)
            if formatted!=value: variable.set(formatted); entry.icursor("end")
        entry.bind("<KeyRelease>",dashes,add="+")
        def normalize(_event=None):
            value=variable.get().strip()
            if not value: return
            try: variable.set(formatted_user_date(value))
            except ValueError: pass
        entry.bind("<FocusOut>",normalize); entry.bind("<Return>",normalize)
        return entry

    def login_screen(self):
        self.clear()
        card = tk.Frame(self, bg="white", padx=42, pady=36)
        card.place(relx=.5, rely=.5, anchor="center")
        try:
            try:  # 2.9.58: resized with filtering, sharp at any size
                import brand_images
                self.login_logo = brand_images.photo(brand_images.full_logo(resource_path("assets/Saber_for_Audit_logo.png"), 250), self)
            except Exception:
                self.login_logo = tk.PhotoImage(file=str(resource_path("assets/Saber_for_Audit_logo.png"))).subsample(6, 6)
            tk.Label(card, image=self.login_logo, bg="white").grid(row=0, column=0, columnspan=2, pady=(0, 14))
        except Exception:
            tk.Label(card, text="SABER FOR AUDIT", font=("Segoe UI", 24, "bold"), fg=NAVY, bg="white").grid(row=0, column=0, columnspan=2)
        tk.Label(card, text="PROFESSIONAL ACCOUNTING", font=("Segoe UI", 11, "bold"), fg=GOLD, bg="white").grid(row=1, column=0, columnspan=2, pady=(0,25))
        self.server = tk.StringVar(value=app_runtime.LOCAL_URL or "http://127.0.0.1:8765")
        self.username = tk.StringVar(value="admin")
        self.password = tk.StringVar()
        fields = [("server", self.server, False), ("username", self.username, False), ("password", self.password, True)]
        for row,(key,var,secret) in enumerate(fields, 2):
            tk.Label(card, text=tr("en",key), bg="white", anchor="w").grid(row=row,column=0,sticky="w",pady=7,padx=(0,14))
            entry=tk.Entry(card,textvariable=var,width=34,show="*" if secret else "")
            entry.grid(row=row,column=1,pady=7)
            if secret:
                entry.bind("<Return>",lambda _event:self.login())
        tk.Label(card,text="Language",bg="white").grid(row=5,column=0,sticky="w",pady=7)
        ttk.Combobox(card,textvariable=self.language,values=["en","ar","fr"],state="readonly",width=31).grid(row=5,column=1,pady=7)
        tk.Button(card,text="Sign in",command=self.login,bg=NAVY,fg="white",activebackground=GOLD,width=29,pady=8,border=0).grid(row=6,column=0,columnspan=2,pady=(22,0))

    def login(self):
        try:
            self.client = ApiClient(self.server.get(), on_unauthorized=self.session_ended)
            self.client.confirm_negative_stock=lambda text: messagebox.askyesno("Stock below zero | مخزون سالب",text,icon="warning")
            self.current_user=self.client.login(self.username.get(), self.password.get())
            self.last_activity=time.monotonic(); self.bind_all("<Any-KeyPress>",self.record_activity); self.bind_all("<Any-Button>",self.record_activity); self.after(60000,self.check_auto_logout)
            self.company_selection_screen()
        except Exception as exc: messagebox.showerror("Saber Accounting", str(exc))

    def company_selection_screen(self):
        try: companies=self.client.companies()
        except Exception as exc: return messagebox.showerror("Companies",str(exc))
        self.available_companies=companies; self.clear()
        card=tk.Frame(self,bg="white",padx=42,pady=34); card.place(relx=.5,rely=.5,anchor="center")
        tk.Label(card,text="Select Company & Fiscal Year",bg="white",fg=NAVY,font=("Segoe UI",18,"bold")).grid(row=0,column=0,columnspan=2,pady=(0,20))
        labels={f'{c["name"]} ({"Active" if c.get("active",True) else "Inactive"})':c for c in companies}; company_var=tk.StringVar(value=next(iter(labels),"")); year_var=tk.StringVar()
        tk.Label(card,text="Company",bg="white").grid(row=1,column=0,sticky="w",pady=8); company_box=ttk.Combobox(card,textvariable=company_var,values=list(labels),state="readonly",width=34); company_box.grid(row=1,column=1,pady=8)
        tk.Label(card,text="Fiscal Year",bg="white").grid(row=2,column=0,sticky="w",pady=8); year_box=ttk.Combobox(card,textvariable=year_var,state="readonly",width=34); year_box.grid(row=2,column=1,pady=8)
        def refresh_years(*_args):
            company=labels.get(company_var.get()); years=[str(y["year"]) for y in company.get("years",[])] if company else []
            year_box["values"]=years
            selected=str(getattr(self,"current_fiscal_year","")) if company and company.get("id")==getattr(self,"current_company",{}).get("id") else ""
            year_var.set(selected if selected in years else (years[-1] if years else ""))
        company_box.bind("<<ComboboxSelected>>",refresh_years); refresh_years()
        previous=getattr(self,"current_company",None)
        if previous:
            choice=next((label for label,entry in labels.items() if entry["id"]==previous.get("id")),None)
            if choice: company_var.set(choice); refresh_years()
        def open_company():
            company=labels.get(company_var.get())
            if not company or not year_var.get(): return messagebox.showwarning("Companies","Select a company and fiscal year")
            if not company.get("active",True): return messagebox.showwarning("Companies","This company is inactive")
            old_company,old_year=self.client.company_id,self.client.fiscal_year
            try:
                year=int(year_var.get())
                self.client.select_company_year(company["id"],year)
                self.client.dashboard()  # Verify the selected year's data before replacing the current screen.
                self.current_company=company; self.current_fiscal_year=year
                self.journal_view_year.set(str(year))
                for name in ("pnl_from_date", "report_from_date", "trial_from_date", "journal_from_date"):
                    variable=getattr(self,name,None)
                    if variable is not None: variable.set(f"01-01-{year}")
                for name in ("pnl_to_date", "report_to_date", "trial_to_date", "journal_to_date"):
                    variable=getattr(self,name,None)
                    if variable is not None: variable.set(f"31-12-{year}")
                self.close_year.set(str(year))
                self.main_screen()
            except Exception as exc:
                self.client.company_id,self.client.fiscal_year=old_company,old_year
                log.exception("Could not open company / year")
                messagebox.showerror("Switch Company / Year",f"Could not open {company['name']} · {year_var.get()}: {exc}")
        tk.Button(card,text="Open Company",command=open_company,bg=GOLD,fg=NAVY,font=("Segoe UI",10,"bold"),border=0,padx=25,pady=8).grid(row=3,column=0,columnspan=2,pady=(18,6))
        if self.current_user.get("role")=="admin":
            self.action_button(card,"Create Company",self.create_company_dialog).grid(row=4,column=0,padx=4,pady=5)
            self.action_button(card,"Manage Selected",lambda:self.manage_company_dialog(labels.get(company_var.get()))).grid(row=4,column=1,padx=4,pady=5)

    def create_company_dialog(self):
        window=tk.Toplevel(self); window.title("Create Company"); window.configure(bg=LIGHT); window.transient(self); window.grab_set()
        fields={key:tk.StringVar(value=str(datetime.now().year) if key=="year" else "") for key in ("name","year","address","phone","mof_number","email","website")}
        for row,(key,label) in enumerate((("name","Company Name"),("year","Opening Fiscal Year"),("address","Address"),("phone","Phone"),("mof_number","MOF / VAT Number"),("email","Email"),("website","Website"))):
            tk.Label(window,text=label,bg=LIGHT).grid(row=row,column=0,sticky="w",padx=14,pady=7); tk.Entry(window,textvariable=fields[key],width=38).grid(row=row,column=1,padx=14,pady=7)
        def save():
            try: self.client.create_company({key:var.get().strip() for key,var in fields.items()})
            except Exception as exc: return messagebox.showerror("Create Company",str(exc),parent=window)
            window.destroy(); self.company_selection_screen()
        self.action_button(window,"Create Company",save).grid(row=7,column=0,columnspan=2,pady=14)

    def manage_company_dialog(self,company):
        if not company: return
        window=tk.Toplevel(self); window.title("Manage Company"); window.configure(bg=LIGHT); window.transient(self); window.grab_set()
        name=tk.StringVar(value=company["name"]); new_year=tk.StringVar(value=str(max(int(y["year"]) for y in company.get("years",[]))+1)); active=tk.BooleanVar(value=company.get("active",True))
        tk.Label(window,text="Company Name",bg=LIGHT).grid(row=0,column=0,padx=14,pady=8); tk.Entry(window,textvariable=name,width=32).grid(row=0,column=1,padx=14,pady=8)
        tk.Checkbutton(window,text="Active",variable=active,bg=LIGHT).grid(row=1,column=0,columnspan=2,pady=5)
        tk.Label(window,text="New Fiscal Year",bg=LIGHT).grid(row=2,column=0,padx=14,pady=8); tk.Entry(window,textvariable=new_year,width=12).grid(row=2,column=1,padx=14,pady=8,sticky="w")
        def update():
            try: self.client.update_company(company["id"],{"name":name.get(),"active":active.get()})
            except Exception as exc: return messagebox.showerror("Company",str(exc),parent=window)
            window.destroy(); self.company_selection_screen()
        def create_year():
            if not messagebox.askyesno("Fiscal Year","Create this fiscal year as a separate open year? The previous year will remain open until you close it manually.",parent=window): return
            try: self.client.create_fiscal_year(company["id"],int(new_year.get()))
            except Exception as exc: return messagebox.showerror("Fiscal Year",str(exc),parent=window)
            window.destroy(); self.company_selection_screen()
        self.action_button(window,"Save Company",update).grid(row=3,column=0,padx=6,pady=14); self.action_button(window,"Create Separate Year",create_year).grid(row=3,column=1,padx=6,pady=14)

    def start_automatic_backup(self):
        """Daily automatic backup of the open company / year, made quietly in the background when the
        company is opened (at most once per backup interval, newest 30 kept)."""
        client=getattr(self,"client",None)
        if client is None: return
        def work():
            try: client.scheduled_backup()
            except Exception: logging.getLogger("saber.ignored").debug("Ignored error", exc_info=True)
        threading.Thread(target=work,daemon=True).start()

    def main_screen(self):
        # 2.9.66: pages of the previous company / year that were still waiting are dropped first (switching company
        # while they were being built opened them on removed frames: 17 "page could not be loaded" messages)
        self.__dict__["_pending_builders"]=[]; self._page_generation=getattr(self,"_page_generation",0)+1
        self.start_automatic_backup()
        if not hasattr(self, "show_department"): self.show_department=tk.BooleanVar(value=True)
        if not hasattr(self, "show_project"): self.show_project=tk.BooleanVar(value=True)
        self._dimension_groups=[]; self._dimension_sheets=[]
        # Forget the widgets of the previous screen (switching company / year rebuilds every page).
        for name in ("purchase_form","expense_form","payment_forms","trial_state","statement_state","voucher_sheet","budget_sheet","departments_tree","pr_tree","vat_summary_tree","_dimensions","_account_cache","items_tree","sd_find_box","warehouses_tree","ir_warehouse_box","ir_item_box","ir_category_box","stock_sheet","_cash_accounts","_expense_accounts",
                     "sio_sheet","pc_sheet","pc_find_box","sio_wh_box","pc_wh_box","cat_tree","item_boxes","ir_subcategory_box","ir_unit_box","ir_supplier_box","_all_accounts"):
            self.__dict__.pop(name,None)
        # Also forget every page widget of the previous screen: they are destroyed below, and a page that is
        # built later (in the background) must not be mistaken for one that already exists.
        for name,value in list(self.__dict__.items()):
            if isinstance(value,tk.Misc) and not isinstance(value,(tk.Tk,tk.Toplevel)) and not name.startswith("_") and name not in ("tk","master"):
                self.__dict__.pop(name,None)
        self.clear(); lang=self.language.get()
        try: self.currency_codes=[row["code"] for row in self.client.currencies()]
        except Exception: self.currency_codes=["USD","LBP","EUR","AED"]
        top=tk.Frame(self,bg=NAVY,height=58); top.pack(fill="x"); top.pack_propagate(False)
        try:
            try:  # 2.9.58: the SA mark alone, sharp, white and gold on the navy bar
                import brand_images
                self.header_logo = brand_images.photo(brand_images.header_mark(resource_path("assets/Saber_for_Audit_logo.png"), 46), self)
            except Exception:
                self.header_logo = tk.PhotoImage(file=str(resource_path("assets/Saber_for_Audit_logo.png"))).subsample(18, 18)
            tk.Label(top,image=self.header_logo,bg=NAVY).pack(side="left",padx=(18,8),pady=2)
        except Exception:
            log.warning("Header logo could not be shown", exc_info=True)
        tk.Label(top,text=tr(lang,"title"),bg=NAVY,fg="white",font=("Segoe UI",16,"bold")).pack(side="left",padx=8,pady=12)
        tk.Label(top,text="11% VAT  |  " + " · ".join(self.currency_codes[:5]),bg=NAVY,fg=GOLD,font=("Segoe UI",10,"bold")).pack(side="right",padx=28)
        tk.Button(top,text="Help / مساعدة",command=self.open_user_guide,bg=NAVY,fg="white",activebackground=GOLD,border=0,padx=10).pack(side="right",padx=4)
        self.update_notice_bar=top; self.start_update_check()
        tk.Button(top,text="Switch Company / Year",command=self.company_selection_screen,bg=GOLD,fg=NAVY,border=0,padx=10,pady=5).pack(side="right",padx=5)
        self.alerts_button=tk.Button(top,text="Document Alerts",command=self.show_document_alerts,bg=NAVY,fg="white",border=1,padx=10,pady=5)
        self.alerts_button.pack(side="right",padx=5)
        tk.Label(top,text=f'{getattr(self,"current_company",{}).get("name","")} · {getattr(self,"current_fiscal_year","")}',bg=NAVY,fg="white",font=("Segoe UI",9,"bold")).pack(side="right",padx=8)
        self.status_bar()
        import desktop_layout
        side_menu=desktop_layout.side_menu_on(); self.side_menu_mode=side_menu
        if side_menu:  # 2.9.60: grouped menu on the left instead of the grid of buttons above the pages
            body=tk.Frame(self,bg=LIGHT); body.pack(fill="both",expand=True)
            menu_holder=tk.Frame(body,bg=desktop_layout.MENU_BG,width=desktop_layout.MENU_WIDTH); menu_holder.pack(side="left",fill="y"); menu_holder.pack_propagate(False)
            host=tk.Frame(body,bg=LIGHT); host.pack(side="left",fill="both",expand=True)
            nav_buttons=[]; size_navigation=lambda _event=None:None
        else:
            host=self
            nav_outer=tk.Frame(self,bg=LIGHT); nav_outer.pack(fill="x",padx=8,pady=(4,0))
            nav_canvas=tk.Canvas(nav_outer,bg=LIGHT,highlightthickness=0,height=56)
            nav_canvas.pack(side="left",fill="x",expand=True)
            nav_vertical=ttk.Scrollbar(nav_outer,orient="vertical",command=nav_canvas.yview)
            nav_vertical.pack(side="right",fill="y")
            nav_scroll=ttk.Scrollbar(nav_outer,orient="horizontal",command=nav_canvas.xview)
            nav_scroll.pack(side="bottom",fill="x")
            nav_canvas.configure(xscrollcommand=nav_scroll.set,yscrollcommand=nav_vertical.set)
            tab_nav=tk.Frame(nav_canvas,bg=LIGHT)
            nav_window=nav_canvas.create_window((0,0),window=tab_nav,anchor="nw")
            nav_buttons=[]; navigation_columns=None
            def size_navigation(_event=None):
                nonlocal navigation_columns
                columns=min(8,max(2,nav_canvas.winfo_width()//155))
                if nav_buttons and columns!=navigation_columns:
                    navigation_columns=columns
                    for button in nav_buttons: button.grid_forget()
                    for column in range(8): tab_nav.grid_columnconfigure(column,weight=0,uniform="")
                    for row in range(8): tab_nav.grid_rowconfigure(row,weight=0,uniform="")
                    for column in range(columns): tab_nav.grid_columnconfigure(column,weight=1,uniform="main_tabs")
                    for row in range((len(nav_buttons)+columns-1)//columns):
                        tab_nav.grid_rowconfigure(row,weight=1,uniform="main_tab_rows")
                    for index,button in enumerate(nav_buttons):
                        button.grid(row=index//columns,column=index%columns,sticky="nsew",padx=4,pady=3)
                nav_canvas.itemconfigure(nav_window,width=max(nav_canvas.winfo_width(),tab_nav.winfo_reqwidth()))
                nav_canvas.configure(height=min(100,max(56,tab_nav.winfo_reqheight()+2)),scrollregion=nav_canvas.bbox("all"))
                if tab_nav.winfo_reqheight()>nav_canvas.winfo_height()+1:
                    if not nav_vertical.winfo_manager(): nav_vertical.pack(side="right",fill="y")
                elif nav_vertical.winfo_manager(): nav_vertical.pack_forget()
                if tab_nav.winfo_reqwidth()>nav_canvas.winfo_width()+1:
                    if not nav_scroll.winfo_manager(): nav_scroll.pack(side="bottom",fill="x")
                elif nav_scroll.winfo_manager(): nav_scroll.pack_forget()
            tab_nav.bind("<Configure>",size_navigation)
            nav_canvas.bind("<Configure>",size_navigation)
        ttk.Style(self).layout("Tabless.TNotebook.Tab",[])
        notebook=ttk.Notebook(host,style="Tabless.TNotebook"); self.main_notebook=notebook
        filter_bar=tk.Frame(host,bg=LIGHT); filter_bar.pack(fill="x",padx=28 if not side_menu else 14,pady=(6 if side_menu else 0,0))
        notebook.pack(fill="both",expand=True,padx=18 if not side_menu else 8,pady=(6,16 if not side_menu else 8))
        pages=[("dashboard_tab",tr(lang,"dashboard")),("invoices_tab",tr(lang,"invoices")),("sales_tab","Sales Invoice"),("manual_tab",tr(lang,"manual_entry")),
            ("import_tab",tr(lang,"import")),("parties_tab",tr(lang,"customers_suppliers")),("transactions_tab",tr(lang,"payments_expenses")),("purchases_tab","Purchases & Expenses"),("inventory_tab","Inventory")]
        if self.can_use("payroll"): pages.append(("payroll_tab","Payroll"))
        if self.can_use("vat"): pages.append(("vat_tab","Quarterly VAT"))
        pages+=[("journal_tab",tr(lang,"general_journal")),("account_reports_tab","Accounts & Statements"),("pnl_tab",tr(lang,"profit_loss")),("reports_tab",tr(lang,"financial_reports")),
            ("settings_tab",tr(lang,"security_backup_rates"))]
        self.main_tab_pages=[]
        for attribute,name in pages:
            container=tk.Frame(notebook,bg=LIGHT)
            container.grid_rowconfigure(0,weight=1)
            container.grid_columnconfigure(0,weight=1)
            canvas=tk.Canvas(container,bg=LIGHT,highlightthickness=0); canvas._saber_scroll_page=True  # scrolled by the mouse wheel
            vertical=ttk.Scrollbar(container,orient="vertical",command=canvas.yview)
            horizontal=ttk.Scrollbar(container,orient="horizontal",command=canvas.xview)
            canvas.configure(yscrollcommand=vertical.set,xscrollcommand=horizontal.set)
            canvas.grid(row=0,column=0,sticky="nsew")
            vertical.grid(row=0,column=1,sticky="ns")
            horizontal.grid(row=1,column=0,sticky="ew")
            frame=tk.Frame(canvas,bg=LIGHT)
            item=canvas.create_window((0,0),window=frame,anchor="nw")
            def resize_page(_event=None, *, page=frame, view=canvas, window=item, vbar=vertical, hbar=horizontal):
                if page.winfo_reqheight()>view.winfo_height()+1: vbar.grid()
                else: vbar.grid_remove()
                if page.winfo_reqwidth()>view.winfo_width()+1: hbar.grid()
                else: hbar.grid_remove()
                view.itemconfigure(window,width=max(view.winfo_width(),page.winfo_reqwidth()),
                                   height=max(view.winfo_height(),page.winfo_reqheight()))
                view.configure(scrollregion=view.bbox("all"))
            frame.bind("<Configure>",resize_page)
            canvas.bind("<Configure>",resize_page)
            setattr(self,attribute,frame); notebook.add(container,text=name); self.main_tab_pages.append(container)
        account_notebook=ttk.Notebook(self.account_reports_tab); account_notebook.pack(fill="both",expand=True,padx=8,pady=8)
        for attribute,name in (("trial_tab",tr(lang,"trial_balance")),("statement_tab",tr(lang,"statement_account")),("accounts_tab",tr(lang,"chart_accounts"))):
            frame=tk.Frame(account_notebook,bg=LIGHT); setattr(self,attribute,frame); account_notebook.add(frame,text=name)
        self.tab_names=[notebook.tab(tab,"text") for tab in notebook.tabs()]
        self.tab_choice=tk.StringVar(value=self.tab_names[0])
        self.tab_buttons=nav_buttons
        self._page_attributes=[attribute for attribute,_name in pages]
        if side_menu:
            nav_buttons.extend(desktop_layout.build_side_menu(self,menu_holder,self._page_attributes,self.main_tab_pages,self.tab_names))
        else:
            for index,(page,name) in enumerate(zip(self.main_tab_pages,self.tab_names)):
                button=tk.Button(tab_nav,text=name,command=lambda p=page:self.select_main_tab(p),bg=NAVY,fg="white",
                    activebackground=GOLD,activeforeground=NAVY,border=0,font=("Segoe UI",8,"bold"),pady=1,wraplength=120,cursor="hand2")
                nav_buttons.append(button)
        self.after_idle(size_navigation)
        notebook.bind("<<NotebookTabChanged>>",lambda _event:self.highlight_main_tab())
        self.highlight_main_tab()
        tk.Label(filter_bar,text="Show currency:",bg=LIGHT,font=("Segoe UI",10,"bold")).pack(side="left")
        currency_filter=ttk.Combobox(filter_bar,textvariable=self.view_currency,values=["All Currencies"]+self.currency_codes,state="readonly",width=16)
        currency_filter.pack(side="left",padx=8); currency_filter.bind("<<ComboboxSelected>>",lambda _event:self.currency_changed())
        builders=[self.build_dashboard,self.build_invoices,self.build_sales_invoice,self.build_manual,self.build_import,self.build_parties,self.build_transactions,self.build_purchases_expenses,self.build_inventory]
        if self.can_use("payroll"): builders.append(self.build_payroll)
        if self.can_use("vat"): builders.append(self.build_vat_return)
        builders+=[self.build_journal,self.build_trial,self.build_profit_loss,self.build_financial_reports,self.build_statement,self.build_accounts,self.build_settings]
        # Build the Dashboard now. Other pages wait until selected or explicitly needed;
        # expensive hidden reports must not compete with the first screen for the UI thread.
        self._page_generation=getattr(self,"_page_generation",0)+1
        self._pending_builders=list(builders[1:])
        self._run_page_builder(builders[0])
        self.update_idletasks()
        generation=self._page_generation
        self.after(700,lambda:self.show_document_alerts(startup=True)
                   if generation==self.__dict__.get("_page_generation") and self.client else None)

    def fit_dialog(self,window,width,height,min_width=None,min_height=None):
        """Scale a dialog for high-DPI screens while keeping it within the available display."""
        try: scale=max(1.0,min(2.0,self.winfo_fpixels("1i")/96.0))
        except tk.TclError: scale=1.0
        screen_width,screen_height=window.winfo_screenwidth(),window.winfo_screenheight()
        width=min(round(width*scale),screen_width); height=min(round(height*scale),screen_height)
        min_width=min(round((min_width if min_width is not None else width/scale)*scale),screen_width)
        min_height=min(round((min_height if min_height is not None else height/scale)*scale),screen_height)
        x=max(0,(screen_width-width)//2); y=max(0,(screen_height-height)//2)
        window.minsize(min_width,min_height)
        window.geometry(f"{width}x{height}+{x}+{y}")

    def _run_page_builder(self,build):
        self.__dict__["_building_depth"]=self.__dict__.get("_building_depth",0)+1
        try:
            build()
            # Bind newly created controls while missing widgets cannot trigger eager loading.
            self.setup_context_f2()
        except Exception as exc:
            log.exception("Page %s could not be loaded", build.__name__); messagebox.showerror("Saber Accounting",f"A page could not be loaded ({build.__name__.replace('build_','').replace('_',' ')}): {exc}\n\nThe other pages are still available.")
        finally: self.__dict__["_building_depth"]-=1

    def _build_next_page(self,generation):
        if generation!=getattr(self,"_page_generation",None): return  # the company / year was switched meanwhile
        pending=self.__dict__.get("_pending_builders")
        if pending:
            self._run_page_builder(pending.pop(0))
        if pending: self.after(30,lambda:self._build_next_page(generation))
        elif self.__dict__.get("_pages_finished_for")!=generation: self._pages_finished_for=generation; self._finish_pages()

    def build_pending_pages(self):
        """Build every page that is still waiting (called when a page or one of its widgets is needed now)."""
        pending=self.__dict__.get("_pending_builders")
        while pending:
            self._run_page_builder(pending.pop(0))
        if self.__dict__.get("_pages_finished_for")!=self.__dict__.get("_page_generation"):
            self._pages_finished_for=self.__dict__.get("_page_generation"); self._finish_pages()

    def _finish_pages(self):
        self.setup_context_f2()

    def __getattr__(self,name):
        # Only reached when normal lookup fails: a widget of a page that is not built yet.
        pending=self.__dict__.get("_pending_builders")
        # While a page is being built, a missing attribute means exactly what it meant before (not built yet).
        # 2.9.66: flags such as _update_checked are not page widgets: never build pages for them
        if pending and not name.startswith("_") and not self.__dict__.get("_building_depth",0):
            self.build_pending_pages()
            try: return object.__getattribute__(self,name)
            except AttributeError: pass
        return super().__getattr__(name)

    def record_activity(self,_event=None): self.last_activity=time.monotonic()

    def journal_document(self,mode):
        rows=getattr(self,"journal_rows",[])
        if not rows: return messagebox.showwarning("General Journal","Nothing to print: apply the filters or the Find first")
        headers=["Entry No.","Date","Description","Account","Account Name","Customer / Supplier","Currency","Debit","Credit"]
        body=[[r.get("entry_number"),r.get("entry_date"),r.get("description") or "",r.get("account_code"),r.get("account_name") or "",r.get("party_name") or "",r.get("currency"),
               float(r.get("debit") or 0),float(r.get("credit") or 0)] for r in rows]
        body.append(["TOTAL","","","","","","",round(sum(float(r.get("debit") or 0) for r in rows),2),round(sum(float(r.get("credit") or 0) for r in rows),2)])
        meta=[f"From {self.journal_from_date.get() or '-'} to {self.journal_to_date.get() or '-'}"]+([f"Voucher: {self.journal_find.get()}"] if self.journal_find.get().strip() else [])+([f"Details: {self.journal_find_details.get()}"] if self.journal_find_details.get().strip() else [])
        self.output_sections("General Journal",meta,[{"heading":f"{len(rows)} line(s)","headers":headers,"rows":body,"total_rows":[len(body)-1]}],"General_Journal",
                             {"preview":"preview","pdf":"pdf","print":"print"}[mode])

    def focus_page_search(self,_event=None):
        """Ctrl+F: put the cursor in the first visible Search box of the current page."""
        try: page=self.nametowidget(self.main_notebook.select())
        except Exception: return "break"
        stack=[page]
        while stack:
            widget=stack.pop(0)
            if getattr(widget,"_is_search_entry",False) and widget.winfo_ismapped():
                widget.focus_set(); widget.select_range(0,"end"); return "break"
            stack.extend(widget.winfo_children())
        return "break"

    def check_auto_logout(self):
        if self.client and time.monotonic()-self.last_activity>=1800:
            self.client=None; self.current_user=None; self.login_screen(); messagebox.showinfo("Saber Accounting","Signed out automatically after 30 minutes of inactivity"); return
        self.after(60000,self.check_auto_logout)

    def move_main_tab(self,direction):
        try: current_page=self.main_notebook.select(); current=self.main_tab_pages.index(self.nametowidget(current_page))
        except (ValueError,KeyError): current=self.visible_tab_start
        target=(current+direction)%len(self.main_tab_pages)
        start=self.visible_tab_start
        if target<start: start=target
        elif target>=start+6: start=target-5
        if direction>0 and current==len(self.main_tab_pages)-1: start=0
        elif direction<0 and current==0: start=max(0,len(self.main_tab_pages)-6)
        self.show_tab_window(start,target)

    def _ensure_main_tab(self,page):
        """Build only the requested tab; leave unrelated tabs waiting until needed."""
        try: index=self.main_tab_pages.index(page)
        except (AttributeError,ValueError): return
        names={"dashboard_tab": ("build_dashboard",), "invoices_tab": ("build_invoices",),
            "sales_tab": ("build_sales_invoice",), "manual_tab": ("build_manual",),
            "import_tab": ("build_import",), "parties_tab": ("build_parties",),
            "transactions_tab": ("build_transactions",), "purchases_tab": ("build_purchases_expenses",),
            "inventory_tab": ("build_inventory",), "payroll_tab": ("build_payroll",),
            "vat_tab": ("build_vat_return",), "journal_tab": ("build_journal",),
            "account_reports_tab": ("build_trial","build_statement","build_accounts"),
            "pnl_tab": ("build_profit_loss",), "reports_tab": ("build_financial_reports",),
            "settings_tab": ("build_settings",)}
        page_name=self.main_tab_pages[index]
        attribute=next((name for name in names if getattr(getattr(self.__dict__.get(name),"master",None),"master",None) is page_name),None)
        pending=self.__dict__.get("_pending_builders") or []
        for builder_name in names.get(attribute,()):
            builder=next((item for item in pending if item.__name__==builder_name),None)
            if builder is not None:
                pending.remove(builder)
                self._run_page_builder(builder)

    def _collect_garbage_on_screen_thread(self):
        """2.9.54: Python frees unused screen objects in cycles from whichever thread happens to run at that moment.
        When that is the data-service thread, Tk refuses it ('main thread is not in main loop') and can stop the
        program. Automatic collection is switched off and done here, on the screen thread, every 20 seconds."""
        import gc
        gc.disable()
        def collect():
            try: gc.collect()
            finally:
                try: self.after(20000, collect)
                except tk.TclError: pass
        self.after(20000, collect)
        self.bind("<Destroy>", lambda event: gc.collect() if event.widget is self else None, add="+")

    def main_tab_container(self,page):
        """The notebook page holding a screen. Screens live in a scrolled frame inside the page (2.9.54: opening
        an entry from the General Journal failed with '... is not in list' when given the inner frame)."""
        pages=getattr(self,"main_tab_pages",[]); widget=page
        while widget is not None and widget not in pages: widget=getattr(widget,"master",None)
        return widget if widget is not None else page

    def select_main_tab(self,page):
        page=self.main_tab_container(page)
        self._ensure_main_tab(page)
        self.main_notebook.select(page); self.highlight_main_tab()

    def highlight_main_tab(self):
        selected=self.main_notebook.select()
        if selected:
            page=next((item for item in getattr(self,"main_tab_pages",[]) if str(item)==selected),None)
            if page is not None: self._ensure_main_tab(page)
        side=getattr(self,"side_menu_mode",False)
        for page,button in zip(getattr(self,"main_tab_pages",[]),getattr(self,"tab_buttons",[])):
            if side:
                import desktop_layout
                if desktop_layout.colour_menu_button(button,str(page)==selected): continue
            button.config(bg=GOLD if str(page)==selected else NAVY,fg=NAVY if str(page)==selected else "white")

    def show_tab_window(self,start,selected_index=None):
        maximum=max(0,len(self.main_tab_pages)-6); self.visible_tab_start=max(0,min(start,maximum))
        for page in self.main_tab_pages:
            try: self.main_notebook.forget(page)
            except tk.TclError: pass
        end=min(len(self.main_tab_pages),self.visible_tab_start+6)
        for index in range(self.visible_tab_start,end):
            self.main_notebook.add(self.main_tab_pages[index],text=self.tab_names[index],padding=(8,4))
        target=selected_index if selected_index is not None and self.visible_tab_start<=selected_index<end else self.visible_tab_start
        self.main_notebook.select(self.main_tab_pages[target]); self.tab_choice.set(self.tab_names[target])

    def select_named_tab(self):
        try:
            index=self.tab_names.index(self.tab_choice.get()); self.show_tab_window(max(0,min(index,len(self.main_tab_pages)-6)),index)
        except ValueError: pass

    def currency_changed(self):
        self.load_dashboard(); self.load_invoices(); self.load_journal(); self.load_trial(); self.load_profit_loss(); self.load_financial_reports(); self.load_ageing_report()

    def table(self,parent,columns):
        search_bar=tk.Frame(parent,bg=LIGHT); search_bar.pack(fill="x",padx=10,pady=(10,0))
        search_var=tk.StringVar()
        tk.Label(search_bar,text="Search:",bg=LIGHT,font=("Segoe UI",9,"bold")).pack(side="left")
        search_entry=tk.Entry(search_bar,textvariable=search_var,width=36); search_entry._is_search_entry=True
        search_entry.pack(side="left",padx=8)
        hint=tk.Label(search_bar,text="Ctrl+F  |  searches every column; amounts and dates work with or without , and -",bg=LIGHT,fg="#5f6b76",font=("Segoe UI",8)); hint.pack(side="right")
        tk.Button(search_bar,text="Clear",command=lambda:search_var.set(""),bg=NAVY,fg="white",
                  border=0,padx=12,pady=3).pack(side="left")

        frame=tk.Frame(parent,bg=LIGHT); frame.pack(fill="both",expand=True,padx=10,pady=10)
        tree=ttk.Treeview(frame,columns=[c[0] for c in columns],show="headings")
        for key,label,width in columns:
            tree.heading(key,text=label); tree.column(key,width=width,anchor="e" if is_amount_column(key,label) else "w")  # 2.9.59: amounts on the right
        scroll=ttk.Scrollbar(frame,orient="vertical",command=tree.yview); tree.configure(yscrollcommand=scroll.set)
        tree.pack(side="left",fill="both",expand=True); scroll.pack(side="right",fill="y")
        # 2.9.60: the table fits the window (columns share the width, still resizable by dragging) instead of
        # making the whole page wider than the screen, which pushed the toolbars off to the right.
        frame.configure(width=320,height=max(240,int(tree.cget("height") or 10)*27+34)); frame.pack_propagate(False)
        planned={key:width for key,_label,width in columns}; fitted={"width":0}
        def fit_columns(event):
            if abs(event.width-fitted["width"])<4: return  # only when the window width changes, not after a column drag
            fitted["width"]=event.width; total=sum(planned.values()) or 1; factor=min(1.0,max(0.45,(event.width-4)/total))
            for key,width in planned.items(): tree.column(key,width=max(40,int(width*factor)))
        tree.bind("<Configure>",fit_columns,add="+")
        # 2.9.66: several rows with Ctrl / Shift or by dragging the mouse; their totals appear above the table
        tree.configure(selectmode="extended"); enable_drag_select(tree)
        totals=tk.Label(search_bar,text="",bg=LIGHT,fg=NAVY,font=("Segoe UI",9,"bold")); totals.pack(side="left",padx=12)
        tree._selection_totals=selection_totals(tree,columns,totals,hint)

        real_insert,real_delete=tree.insert,tree.delete
        tree._search_rows=[]
        tree._search_counter=0
        def tracked_insert(parent_id,index,*args,**kwargs):
            tree._search_counter+=1
            saved_kwargs=dict(kwargs)
            saved_kwargs.setdefault("iid",f"search-{id(tree)}-{tree._search_counter}")
            record=(parent_id,index,args,saved_kwargs)
            tree._search_rows.append(record)
            if row_matches_search(saved_kwargs.get("values",()),search_var.get()):
                real_insert(parent_id,index,*args,**saved_kwargs)
            return saved_kwargs["iid"]
        def tracked_delete(*item_ids):
            visible=set(tree.get_children(""))
            requested=set(item_ids)
            if requested==visible:
                tree._search_rows.clear()
            else:
                tree._search_rows=[
                    record for record in tree._search_rows
                    if str(record[3].get("iid")) not in requested
                ]
            if item_ids:
                real_delete(*item_ids)
        def apply_search(*_args):
            visible=tree.get_children("")
            if visible:
                real_delete(*visible)
            for parent_id,index,args,saved_kwargs in tree._search_rows:
                if row_matches_search(saved_kwargs.get("values",()),search_var.get()):
                    real_insert(parent_id,index,*args,**saved_kwargs)
        # Debounce: re-filtering rebuilds the whole Treeview, so on a big table
        # doing it on every keystroke feels laggy. Wait a beat after typing
        # stops, then filter once. The result is identical, just smoother.
        tree._search_after=None
        def schedule_search(*_args):
            pending=getattr(tree,"_search_after",None)
            if pending is not None:
                try: tree.after_cancel(pending)
                except Exception: logging.getLogger("saber.ignored").debug("Ignored error", exc_info=True)
            tree._search_after=tree.after(180,apply_search)
        tree.insert=tracked_insert
        tree.delete=tracked_delete
        tree.search_var=search_var
        tree._sort_reverse={}
        def sort_column(key):
            reverse=tree._sort_reverse.get(key,False)
            def sortable(value):
                clean=str(value).replace(",","").strip()
                try: return (0,float(clean))
                except ValueError: pass
                day=sortable_date(clean)
                if day!=datetime.min: return (0,float(day.toordinal()))  # 2.9.59: DD-MM-YYYY sorts by date, not by day number
                return (1,clean.casefold())
            ordered=sorted(tree.get_children(""),key=lambda item:sortable(tree.set(item,key)),reverse=reverse)
            for position,item in enumerate(ordered): tree.move(item,"",position)
            tree._sort_reverse[key]=not reverse
        for key,label,_width in columns: tree.heading(key,text=label,command=lambda column=key:sort_column(column))
        search_var.trace_add("write",schedule_search)
        search_entry.bind("<Escape>",lambda _event:search_var.set(""))
        context_menu=tk.Menu(tree,tearoff=0)
        def focus_search():
            search_entry.focus_set(); search_entry.select_range(0,"end")
        context_menu.add_command(label="Search…",command=focus_search)
        context_menu.add_command(label="Clear search",command=lambda:search_var.set(""))
        def show_context_menu(event):
            try: context_menu.tk_popup(event.x_root,event.y_root)
            finally: context_menu.grab_release()
        tree.bind("<Button-3>",show_context_menu)  # right-click on Windows/Linux
        tree.bind("<Button-2>",show_context_menu)  # right-click on macOS trackpads
        return tree

    def build_dashboard(self):
        actions=tk.Frame(self.dashboard_tab,bg=LIGHT); actions.pack(fill="x",padx=12,pady=(8,6))
        tk.Label(actions,text="Company overview",bg=LIGHT,fg=NAVY,font=("Segoe UI",12,"bold")).pack(side="left",padx=(0,16))
        self.action_button(actions,tr(self.language.get(),"refresh"),self.load_dashboard).pack(side="left",padx=4)
        tk.Label(actions,text="Base currency",bg=LIGHT).pack(side="left",padx=(10,3))
        ttk.Combobox(actions,textvariable=self.dashboard_base_currency,values=["All Currencies","USD","LBP","EUR","AED"],state="readonly",width=13).pack(side="left")
        tk.Label(actions,text="Convert to",bg=LIGHT).pack(side="left",padx=(10,3))
        ttk.Combobox(actions,textvariable=self.dashboard_display_currency,values=["Original","USD","LBP","EUR","AED"],state="readonly",width=9).pack(side="left")
        self.action_button(actions,"Apply",self.load_dashboard).pack(side="left",padx=4)
        self.action_button(actions,"Export Excel",lambda:self.export_report("dashboard","xlsx")).pack(side="left",padx=4)
        self.action_button(actions,"Export PDF",lambda:self.export_report("dashboard","pdf")).pack(side="left",padx=4)
        self.action_button(actions,"Print",lambda:self.export_report("dashboard","print")).pack(side="left",padx=4)
        flow_toolbars(actions)
        import desktop_layout; desktop_layout.build_today_panel(self,self.dashboard_tab)  # 2.9.60: quick actions + needs attention
        self.dashboard_cards=tk.Frame(self.dashboard_tab,bg=LIGHT); self.dashboard_cards.pack(fill="x",padx=12)
        self.dashboard_chart=tk.Canvas(self.dashboard_tab,height=105,bg="white",highlightthickness=0)
        # 2.9.60: the small monthly strip repeated the "by month" chart below; it is kept (exports use it) but not shown
        self.build_dashboard_charts(self.dashboard_tab)
        self.load_dashboard()

    def load_dashboard(self):
        try: data=self.client.professional_dashboard(); rows=data["metrics"]
        except Exception as exc: return messagebox.showerror("Error",str(exc))
        selected=self.dashboard_base_currency.get()
        rows=[r for r in rows if selected=="All Currencies" or r["currency"]==selected]
        target=self.dashboard_display_currency.get(); display_rows=[]
        date=datetime.now().strftime("%d-%m-%Y")
        for row in rows:
            item=dict(row)
            if target!="Original" and target!=row["currency"]:
                try: rate=float(self.client.dashboard_conversion(row["currency"],target,date)["rate"])
                except Exception as exc: return messagebox.showerror("Dashboard Exchange Rate",str(exc))
                for key in ("sales","purchases","expenses","profit","receivables","payables"): item[key]=float(item[key])*rate
                item["currency"]=f'{row["currency"]} → {target} (1 = {rate:,.4f}; {date})'
            display_rows.append(item)
        rows=display_rows
        self.dashboard_rows=rows
        for child in self.dashboard_cards.winfo_children(): child.destroy()
        if not rows:
            tk.Label(self.dashboard_cards,text="No activity for this currency yet.",bg=LIGHT,fg="#506274",font=("Segoe UI",10)).pack(anchor="w",padx=10,pady=12)
        labels=(("sales","Sales"),("purchases","Purchases"),("expenses","Expenses"),("profit","Net profit"),
                ("receivables","Receivables"),("payables","Payables"),("overdue","Overdue invoices"))
        for index,r in enumerate(rows):
            card=tk.LabelFrame(self.dashboard_cards,text=r["currency"],bg="white",fg=NAVY,font=("Segoe UI",10,"bold"),padx=10,pady=6)
            card.grid(row=index//2,column=index%2,sticky="ew",padx=4,pady=3)
            for col,(key,title) in enumerate(labels):
                line=tk.Frame(card,bg="white"); line.grid(row=col//4,column=col%4,sticky="ew",padx=5,pady=3)
                tk.Label(line,text=title,bg="white",fg="#506274",font=("Segoe UI",8)).pack(anchor="w")
                value=str(r[key]) if key=="overdue" else f'{r[key]:,.2f}'
                tk.Label(line,text=value,bg="white",fg=NAVY,font=("Segoe UI",10,"bold"),anchor="w").pack(anchor="w")
            for col in range(4): card.grid_columnconfigure(col,weight=1)
        for col in range(2): self.dashboard_cards.grid_columnconfigure(col,weight=1)
        chart_rows=[]; chart_rates={}
        for source_row in data.get("monthly",[]):
            if selected!="All Currencies" and source_row["currency"]!=selected: continue
            row=dict(source_row)
            if target!="Original" and target!=row["currency"]:
                if row["currency"] not in chart_rates:
                    chart_rates[row["currency"]]=float(self.client.dashboard_conversion(row["currency"],target,date)["rate"])
                row["amount"]=float(row["amount"])*chart_rates[row["currency"]]
            chart_rows.append(row)
        self.draw_dashboard_chart(chart_rows)
        self.load_dashboard_charts()
        try:
            import desktop_layout; desktop_layout.fill_today_panel(self,data.get("metrics",[]))
        except Exception: log.warning("Needs attention list could not be filled",exc_info=True)

    def draw_dashboard_chart(self,rows):
        canvas=self.dashboard_chart; canvas.delete("all"); canvas.update_idletasks(); width=max(canvas.winfo_width(),700); height=100
        values=[float(row["amount"] or 0) for row in rows[-12:]]; maximum=max([1,*values])
        canvas.create_text(10,10,anchor="nw",text="Monthly Sales / Purchases",fill=NAVY,font=("Segoe UI",10,"bold"))
        for index,row in enumerate(rows[-12:]):
            x=20+index*max(48,(width-40)//max(1,min(12,len(rows))))
            bar_height=(float(row["amount"] or 0)/maximum)*56
            color="#1F6E8C" if row["kind"]=="sale" else GOLD
            canvas.create_rectangle(x,height-25-bar_height,x+24,height-25,fill=color,outline="")
            canvas.create_text(x+12,height-12,text=str(row["month"])[5:],font=("Segoe UI",7))

    def action_button(self,parent,text,command):
        return tk.Button(parent,text=text,command=command,bg=NAVY,fg="white",border=0,padx=15,pady=7)

    def account_search_box(self,parent,variable,width=22,replace_on_focus=False):
        try: accounts=self.client.accounts() if self.client else []
        except Exception: accounts=[]
        accounts=[row for row in accounts if len(str(row.get("code") or ""))>=3 and str(row.get("code") or "").isdigit()]
        choices=[f'{row["code"]} - {row["name_en"]}' for row in accounts]
        box=ttk.Combobox(parent,textvariable=variable,values=choices,width=width)
        def matches(value):
            return [row for row in accounts if row_matches_search((row["code"],row["name_en"],row.get("name_ar"),row.get("name_fr")),value)]
        def search(event=None):
            if event and event.keysym in ("Tab","Return","Escape","Up","Down"): return
            typed=variable.get().strip()
            box["values"]=[f'{row["code"]} - {row["name_en"]}' for row in matches(typed)] if typed else choices
        def choose(event=None):
            value=variable.get().strip(); code=value.split(" - ",1)[0].strip()
            if not value: return
            if code.isdigit() and (code in {str(row["code"]) for row in accounts} or " - " in value):
                variable.set(code)
            elif code.isdigit():
                variable.set(code)  # allow an existing legacy code absent from the current chart
            else:
                found=matches(value)
                if len(found)==1: variable.set(str(found[0]["code"]))
                elif event and event.keysym in ("Tab","Return"):
                    box.bell(); return "break"
            if event and event.keysym=="Return":
                box.tk_focusNext().focus_set(); return "break"
        def refresh(_event=None):
            try: fresh=self.client.accounts()
            except Exception: fresh=[]
            if fresh:
                accounts[:]=[row for row in fresh if len(str(row.get("code") or ""))>=3 and str(row.get("code") or "").isdigit()]
                choices[:]=[f'{row["code"]} - {row["name_en"]}' for row in accounts]
            search()
            self.active_account_variable=variable
            if replace_on_focus:
                box.after_idle(lambda: box.select_range(0,"end") if box.winfo_exists() and box.focus_get()==box else None)
        box.bind("<KeyRelease>",search); box.bind("<<ComboboxSelected>>",choose)
        box.bind("<FocusOut>",choose); box.bind("<Return>",choose); box.bind("<Tab>",choose)
        if not replace_on_focus:
            box.bind("<Button-1>",lambda _event: box.after_idle(lambda: box.event_generate("<Down>")))
        box.bind("<FocusIn>",refresh)
        box._f2=lambda: self.open_account_lookup(variable,include_groups=True)
        box.bind("<F2>",lambda _event: (box._f2(),"break")[1])
        box._account_var=variable  # right-click opens the account search for this field
        return box

    def open_active_account_lookup(self,event=None):
        if self.active_account_variable is not None: self.open_account_lookup(self.active_account_variable)
        return "break"

    def create_account_in_lookup(self, parent_code, name, account_type, variable):
        parent_code=str(parent_code or "").split(" - ",1)[0].strip()
        name=str(name or "").strip()
        if len(parent_code)!=4 or not parent_code.isdigit():
            raise ValueError("Choose a 4-digit parent account before creating a new account")
        if not name:
            raise ValueError("Enter a name for the new account")
        if account_type not in ("asset","liability","equity","income","expense"):
            raise ValueError("Choose the new account type")
        account=self.client.save_account({"code":"","parent_code":parent_code,"name_en":name,"type":account_type})
        self._account_cache=None
        if hasattr(self,"_all_accounts"): self._all_accounts[account["code"]]=account["name_en"]
        variable.set(account["code"])
        if hasattr(self,"accounts_tree"): self.load_accounts()
        return account

    def open_account_lookup(self,variable,include_groups=False):
        try: all_accounts=self.client.accounts()
        except Exception as exc: return messagebox.showerror("Account Search",str(exc))
        accounts=[row for row in all_accounts if str(row.get("code") or "").isdigit() and len(str(row["code"])) >= (3 if include_groups else 9)]
        parents={str(row["code"]):row for row in all_accounts if len(str(row.get("code") or ""))==4 and str(row["code"]).isdigit()}
        previous_grab=self.grab_current()
        window=tk.Toplevel(self); window.title("Find or Create Account - F2")
        fit_dialog=getattr(self,"fit_dialog",None)
        if fit_dialog: fit_dialog(window,820,590,320,320)
        else: SaberApp.fit_dialog(self,window,820,590,320,320)
        window.configure(bg=LIGHT); window.transient(previous_grab or self); window.grab_set()
        def close_lookup():
            window.destroy()
            if previous_grab is not None and previous_grab.winfo_exists(): previous_grab.grab_set()
        window.protocol("WM_DELETE_WINDOW",close_lookup)
        window.bind("<Escape>",lambda _event:close_lookup())
        search_var=tk.StringVar(value=variable.get().split(" - ",1)[0].strip()); top=tk.Frame(window,bg=LIGHT); top.pack(fill="x",padx=10,pady=10)
        tk.Label(top,text="Find by number or name (English / Arabic / French):",bg=LIGHT,font=("Segoe UI",10,"bold")).pack(side="left")
        entry=tk.Entry(top,textvariable=search_var,width=38); entry.pack(side="left",padx=8); entry.focus_set(); entry.select_range(0,"end")
        frame=tk.Frame(window,bg=LIGHT); frame.pack(fill="both",expand=True,padx=10,pady=(0,10))
        tree=ttk.Treeview(frame,columns=("code","name","arabic","type"),show="headings")
        for column,label,width in (("code","Account Number",140),("name","Account Name",300),("arabic","Arabic Name",200),("type","Type",100)):
            tree.heading(column,text=label); tree.column(column,width=width)
        scroll=ttk.Scrollbar(frame,orient="vertical",command=tree.yview); tree.configure(yscrollcommand=scroll.set); tree.pack(side="left",fill="both",expand=True); scroll.pack(side="right",fill="y")
        def populate(*_args):
            tree.delete(*tree.get_children()); typed=search_var.get().strip()
            for row in accounts:
                if row_matches_search((row["code"],row["name_en"],row.get("name_ar"),row.get("name_fr"),row["type"]),typed):
                    tree.insert("","end",values=(row["code"],row["name_en"],row.get("name_ar") or "",row["type"]))
        def select(_event=None):
            selected=tree.selection()
            if not selected: return
            values=tree.item(selected[0],"values"); variable.set(str(values[0])); close_lookup()
        search_var.trace_add("write",populate); tree.bind("<Double-1>",select); tree.bind("<Return>",select); entry.bind("<Return>",lambda _event:(tree.selection_set(tree.get_children()[0]),select()) if tree.get_children() else None)
        tk.Label(window,text="Double-click an account or press Enter to select. If it does not exist, create it below.",bg=LIGHT,fg="#5f6b76").pack(pady=(0,5))
        create=tk.LabelFrame(window,text="Create account here (number assigned automatically)",bg=LIGHT,padx=10,pady=8)
        create.pack(fill="x",padx=10,pady=(0,10))
        parent_var=tk.StringVar(); name_var=tk.StringVar(); type_var=tk.StringVar()
        tk.Label(create,text="4-digit parent",bg=LIGHT).grid(row=0,column=0,sticky="w",padx=4)
        parent_box=ttk.Combobox(create,textvariable=parent_var,values=[f'{code} - {row["name_en"]}' for code,row in parents.items()],width=26)
        parent_box.grid(row=0,column=1,sticky="ew",padx=4)
        tk.Label(create,text="New account name",bg=LIGHT).grid(row=0,column=2,sticky="w",padx=4)
        tk.Entry(create,textvariable=name_var,width=30).grid(row=0,column=3,sticky="ew",padx=4)
        tk.Label(create,text="Type",bg=LIGHT).grid(row=1,column=0,sticky="w",padx=4,pady=(8,0))
        ttk.Combobox(create,textvariable=type_var,values=["asset","liability","equity","income","expense"],state="readonly",width=16).grid(row=1,column=1,sticky="w",padx=4,pady=(8,0))
        number_hint=tk.StringVar(value="Select a parent to assign the next number")
        tk.Label(create,textvariable=number_hint,bg=LIGHT,fg=NAVY).grid(row=1,column=2,sticky="w",padx=4,pady=(8,0))
        def preview_parent(_event=None):
            prefix=parent_var.get().split(" - ",1)[0].strip()
            if prefix in parents:
                type_var.set(parents[prefix]["type"])
                try: number_hint.set(f'Next number: {self.client.next_account_number(prefix)}')
                except Exception as exc: number_hint.set(str(exc))
            else: number_hint.set("Choose a listed 4-digit parent")
        parent_box.bind("<<ComboboxSelected>>",preview_parent); parent_box.bind("<FocusOut>",preview_parent)
        def create_and_select():
            prefix=parent_var.get().split(" - ",1)[0].strip()
            if not prefix:
                selected=tree.selection()
                if selected: prefix=str(tree.item(selected[0],"values")[0])[:4]
            if not prefix:
                typed=search_var.get().strip()
                if len(typed)>=4 and typed[:4].isdigit(): prefix=typed[:4]
            name=name_var.get().strip()
            if not name and search_var.get().strip() and not any(ch.isdigit() for ch in search_var.get()):
                name=search_var.get().strip()
            if prefix in parents and not type_var.get(): type_var.set(parents[prefix]["type"])
            try: self.create_account_in_lookup(prefix,name,type_var.get(),variable)
            except Exception as exc: return messagebox.showerror("Create Account",str(exc),parent=window)
            close_lookup()
        self.action_button(create,"Create & Select",create_and_select).grid(row=1,column=3,sticky="e",padx=4,pady=(8,0))
        create.columnconfigure(3,weight=1)
        populate()

    def branch_selector(self,parent,variable,width=18,include_all=False):
        try: branches=self.client.branches() if self.client else []
        except Exception: branches=[]
        values=(["All Branches"] if include_all else [])+[row["name"] for row in branches]
        if not values: values=["All Branches"] if include_all else ["Head Office"]
        if variable.get() not in values: variable.set(values[0])
        return ttk.Combobox(parent,textvariable=variable,values=values,state="readonly",width=width)

    def selected_branch_id(self,variable):
        if variable.get()=="All Branches": return None
        try: return next(row["id"] for row in self.client.branches() if row["name"]==variable.get())
        except Exception: return None

    def export_report(self,report,format_name):
        if report == "dashboard":
            title="Saber Accounting - Dashboard"; headers=["Currency","Sales","Purchases","Expenses","Net Profit","Receivables","Payables","Overdue"]
            rows=[[r["currency"],r["sales"],r["purchases"],r["expenses"],r["profit"],r["receivables"],r["payables"],r["overdue"]] for r in getattr(self,"dashboard_rows",[])]
        else:
            title="Saber Accounting - Trial Balance"
            if self.trial_from_date.get().strip() or self.trial_to_date.get().strip():
                title += f" ({self.trial_from_date.get().strip() or 'Beginning'} to {self.trial_to_date.get().strip() or 'Today'})"
            headers=["Currency","Account","Account Name","Opening Balance","Debit","Credit","Closing Balance"]
            rows=[[r["currency"],r["code"],r["name_en"],r.get("opening",0),r["debit"] or 0,r["credit"] or 0,r.get("closing_balance",0)] for r in getattr(self,"trial_rows",[])]
        if not rows: return messagebox.showwarning("Saber Accounting","No report data to export")
        try:
            if format_name == "print": print_rows(title,headers,rows); return
            extension=".xlsx" if format_name=="xlsx" else ".pdf"
            path=filedialog.asksaveasfilename(defaultextension=extension,filetypes=[("Excel workbook","*.xlsx")] if format_name=="xlsx" else [("PDF document","*.pdf")],initialfile=title.replace(" - ","_").replace(" ","_")+extension)
            if not path: return
            (export_excel if format_name=="xlsx" else export_pdf)(path,title,headers,rows)
            messagebox.showinfo("Saber Accounting",f"Saved successfully:\n{path}")
        except Exception as exc: messagebox.showerror("Saber Accounting",str(exc))

def main():
    app=SaberApp()
    if app_runtime.INSTANCE: app.after(500,lambda: app_runtime.INSTANCE.remember_window(app))
    app.mainloop()

if __name__ == "__main__": main()
