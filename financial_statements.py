"""Reviewable IAS 1 reporting pack from each company's separate fiscal-year books.

No ledger mutations or automatic audit opinion. Saved presentation mappings are
explicit; cash flow classifications and disclosures require accountant review.
"""
from collections import defaultdict
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import json
import re
from database import iso_date, utcnow

ZERO = Decimal('0')
KEY = 'financial_statement_draft'
GROUPS = {
    'ppe': 'Property, plant and equipment (net)',
    'intangible': 'Intangible assets (net)',
    'noncurrent_assets': 'Other non-current assets',
    'inventory': 'Inventories', 'receivables': 'Trade and other receivables',
    'cash': 'Cash and cash equivalents', 'current_assets': 'Other current assets',
    'capital': 'Share capital', 'reserves': 'Reserves', 'retained': 'Retained earnings / accumulated results',
    'noncurrent_liabilities': 'Non-current liabilities and provisions',
    'payables': 'Trade and other payables', 'current_liabilities': 'Other current liabilities',
    'revenue': 'Revenue (net of discounts)', 'other_income': 'Other income',
    'materials': 'Purchases and inventory movement', 'services': 'External services',
    'staff': 'Employee benefits expense', 'taxes': 'Other taxes and duties',
    'finance': 'Net finance costs', 'depreciation': 'Depreciation, amortisation and provisions',
    'other_expenses': 'Other expenses', 'income_tax': 'Income tax expense',
    'unmapped': 'Unmapped accounts - classification required',
}
ASSETS = ['ppe','intangible','noncurrent_assets','inventory','receivables','cash','current_assets']
EQUITY = ['capital','reserves','retained']
LIABILITIES = ['noncurrent_liabilities','payables','current_liabilities']
INCOME = ['revenue','other_income']
EXPENSES = ['materials','services','staff','taxes','finance','depreciation','other_expenses','income_tax']
NARRATIVES = {
 'Entity and activities': '{company} (the "Company") is registered in Lebanon{address_text}. [Complete: legal form, commercial register number, date of incorporation, shareholders and principal activities.]',
 'Basis of preparation': 'The financial statements have been prepared in accordance with International Financial Reporting Standards (IFRS) under the historical cost convention, and are presented in {basis}. Amounts recorded in other currencies are translated at the exchange rates recorded in the books. [Confirm the applicable framework, going concern and the date of authorisation for issue.]',
 'Material accounting policies': 'Revenue is recognised when control of the goods or services passes to the customer, net of discounts and value added tax.\nInventories are measured at the lower of cost and net realisable value; cost is determined using the {inventory_method} method.\nProperty, plant and equipment are stated at cost less accumulated depreciation; depreciation is charged on a straight-line basis over the useful lives of the assets.\nTrade receivables are stated at their invoiced amounts less an allowance for expected credit losses.\nCash and cash equivalents comprise cash on hand and balances with banks.\nTrade payables are stated at the amounts payable for goods and services received.\nTransactions in foreign currencies are recorded at the exchange rates of the transaction dates; monetary balances are translated at the rates recorded at the reporting date.\nValue added tax is accounted for in accordance with Lebanese VAT law; recoverable VAT is presented with receivables and VAT payable with payables.\nIncome tax is provided in accordance with Lebanese tax law.\nProvisions are recognised when the Company has a present obligation that can be measured reliably; end-of-service indemnities follow Lebanese labour law and NSSF regulations.',
 'Judgements and estimates': 'Preparing the financial statements requires management to make judgements and estimates, mainly for the expected credit losses on receivables, the net realisable value of inventories, the useful lives of property and equipment, and provisions. [Complete with entity-specific judgements.]',
 'Currency and inflation': 'The functional and presentation currency is {basis}. Balances in other currencies are translated using the rates recorded in the books. [Assess the effect of the Lebanese economic situation, multiple exchange rates and IAS 29 if relevant.]',
 'Related parties and commitments': '[List related parties (shareholders, directors, companies under common control), the transactions and balances with them, commitments and contingent liabilities.]',
 'Events and going concern': '[Describe events after the reporting date (IAS 10) and the going concern assessment.]',
 'Additional disclosures': '[Add other disclosures: financial risk management, taxation, leases, capital management.]',
}
AUDIT = {
 'Addressee': 'To the Shareholders of {company}',
 'Opinion': 'We have audited the financial statements of {company} (the "Company"), which comprise the statement of financial position as at {end_text}, and the statement of profit or loss and other comprehensive income, the statement of changes in equity and the statement of cash flows for the {period_text} then ended, and notes to the financial statements, including material accounting policy information.\nIn our opinion, the accompanying financial statements present fairly, in all material respects, the financial position of the Company as at {end_text}, and its financial performance and its cash flows for the {period_text} then ended in accordance with International Financial Reporting Standards (IFRS).',
 'Basis for opinion': 'We conducted our audit in accordance with International Standards on Auditing (ISAs). Our responsibilities under those standards are further described in the Auditor\'s Responsibilities for the Audit of the Financial Statements section of our report. We are independent of the Company in accordance with the International Ethics Standards Board for Accountants\' International Code of Ethics for Professional Accountants (IESBA Code), together with the ethical requirements that are relevant to our audit of the financial statements in Lebanon, and we have fulfilled our other ethical responsibilities in accordance with these requirements and the IESBA Code. We believe that the audit evidence we have obtained is sufficient and appropriate to provide a basis for our opinion.',
 'Going concern / key audit matters': '',
 'Other information': '',
 'Management and governance responsibilities': 'Management is responsible for the preparation and fair presentation of the financial statements in accordance with IFRS, and for such internal control as management determines is necessary to enable the preparation of financial statements that are free from material misstatement, whether due to fraud or error.\nIn preparing the financial statements, management is responsible for assessing the Company\'s ability to continue as a going concern, disclosing, as applicable, matters related to going concern and using the going concern basis of accounting unless management either intends to liquidate the Company or to cease operations, or has no realistic alternative but to do so.\nThose charged with governance are responsible for overseeing the Company\'s financial reporting process.',
 'Auditor responsibilities': 'Our objectives are to obtain reasonable assurance about whether the financial statements as a whole are free from material misstatement, whether due to fraud or error, and to issue an auditor\'s report that includes our opinion. Reasonable assurance is a high level of assurance, but is not a guarantee that an audit conducted in accordance with ISAs will always detect a material misstatement when it exists. Misstatements can arise from fraud or error and are considered material if, individually or in the aggregate, they could reasonably be expected to influence the economic decisions of users taken on the basis of these financial statements.\nAs part of an audit in accordance with ISAs, we exercise professional judgement and maintain professional scepticism throughout the audit. We identify and assess the risks of material misstatement, obtain an understanding of internal control relevant to the audit, evaluate the appropriateness of accounting policies used and the reasonableness of accounting estimates, conclude on the appropriateness of management\'s use of the going concern basis of accounting, and evaluate the overall presentation, structure and content of the financial statements.\nWe communicate with those charged with governance regarding, among other matters, the planned scope and timing of the audit and significant audit findings, including any significant deficiencies in internal control that we identify during our audit.',
 'Other legal and regulatory requirements': '',
 'Signature, address and report date': '[Audit firm name]\n[Partner name - License No.]\n[Address]\n[Date]',
}
# The placeholders of 2.9.68 and before: a section still holding one of them gets the full text above.
OLD_DEFAULTS = {
 '[Complete legal form, domicile, registered address, activities and ownership.]',
 '[Confirm applicable IFRS requirements, measurement basis, going concern and authorisation date. This draft does not assert compliance.]',
 '[Describe policies relevant to this entity: IFRS 15 revenue, IFRS 9 financial instruments, IFRS 16 leases, IAS 2 inventory, IAS 12 taxes, IAS 16 assets and IAS 19 employee benefits.]',
 '[Describe material judgements, estimation uncertainty and impairment assessments.]',
 '[Confirm functional and presentation currencies, IAS 21 translation and applicability of IAS 29. Recorded book equivalents are used; no automatic IAS 21/IAS 29 restatement is performed.]',
 '[Complete IAS 24 relationships, transactions, balances, commitments and contingencies; do not assume none.]',
 '[Complete IAS 10 events after the reporting period, going concern assessment and authorisation for issue.]',
 '[Add entity-specific IFRS disclosures, financial risks, leases, tax reconciliation, asset roll-forwards and other material information.]',
 '[Shareholders / appropriate addressee]',
 '[Auditor to insert the opinion after completing the audit. No opinion has been generated.]',
 '[Auditor to complete applicable ISAs, ethics and independence requirements, and evidence supporting the opinion.]',
 '[Auditor to assess applicable reporting requirements and complete or remove sections as appropriate.]',
 '[Auditor to assess ISA 720 applicability and insert appropriate wording.]',
 '[Complete responsibilities for preparation, internal control, going concern and oversight.]',
 '[Auditor to insert engagement-appropriate ISA reporting wording.]',
 '[Complete where applicable.]',
 '[Auditor name, signature, address and date - to be completed by the auditor.]',
}
SUPPLEMENTS = {
 'oci': 'Other comprehensive income (net of tax, signed)',
 'cf_operating': 'Net operating cash flows (signed)',
 'cf_investing': 'Net investing cash flows (signed)',
 'cf_financing': 'Net financing cash flows (signed)',
 'cf_fx': 'Exchange effect on cash (signed)',
}

def number(value):
    try:
        result = Decimal(str(value))
        if not result.is_finite(): raise ValueError()
        return result
    except (InvalidOperation, ValueError): raise ValueError('Enter a finite numeric amount')

def money(value):
    return value.quantize(Decimal('.01'), rounding=ROUND_HALF_UP) if value else ZERO

def years_from(value):
    parts = re.split(r'[,;\s]+', value.strip()) if isinstance(value, str) else value
    if not isinstance(parts, (list, tuple)) or not parts: raise ValueError('Choose one or two fiscal years, e.g. 2025 or 2024,2025')
    if any(not re.fullmatch(r'\d{4}', str(x)) for x in parts): raise ValueError('Years must be four digits')
    years = sorted({int(x) for x in parts}, reverse=True)
    if len(years) > 2 or any(y < 2000 or y > 2100 for y in years): raise ValueError('Choose one or two years between 2000 and 2100')
    return years

def config(db):
    return json.loads(db.settings().get(KEY) or '{}')

def save_config(db, data, user_id):
    if not isinstance(data, dict): raise ValueError('Invalid financial report settings')
    if data.get('basis','USD') not in ('USD','LBP'): raise ValueError('Choose USD or LBP')
    for field in ('mapping','supplements'):
        if not isinstance(data.get(field,{}),dict): raise ValueError('Invalid '+field)
    for code, group in data.get('mapping', {}).items():
        if not re.fullmatch(r'\d{1,12}', code) or group not in GROUPS: raise ValueError('Invalid account mapping')
    for name in ('notes', 'audit'):
        if not isinstance(data.get(name, {}), dict): raise ValueError('Invalid report text')
        for value in data.get(name, {}).values():
            if not isinstance(value, str) or len(value) > 20000: raise ValueError('Report text must be under 20,000 characters per section')
    for key, value in data.get('supplements', {}).items():
        if key not in SUPPLEMENTS: raise ValueError('Invalid supplementary amount')
        if value != '': number(value)
    text = json.dumps(data, ensure_ascii=False)
    with db.connect() as conn:
        conn.execute('INSERT INTO app_settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value', (KEY,text))
        conn.execute('INSERT INTO audit_log(user_id,action,entity,details,created_at) VALUES(?,?,?,?,?)', (user_id,'update','financial_statement_draft',text,utcnow()))
    return data

def default_group(code, amount):
    # Lebanese chart; overrides can be applied to exact accounts or prefixes.
    if code.startswith(('21','281','291')): return 'intangible'
    if code.startswith(('22','23','282','283','292','293')): return 'ppe'
    if code.startswith('2'): return 'noncurrent_assets'
    if code.startswith('3'): return 'inventory'
    if code.startswith('10'): return 'capital'
    if code.startswith(('11','14')): return 'reserves'
    if code.startswith(('12','13')): return 'retained'
    if code.startswith(('15','16','17','18')): return 'noncurrent_liabilities'
    if code.startswith('49'): return 'receivables'
    if code.startswith('4'): return 'receivables' if amount >= 0 else 'payables'
    if code.startswith(('51','53')): return 'cash' if amount >= 0 else 'current_liabilities'
    if code.startswith('5'): return 'current_assets' if amount >= 0 else 'current_liabilities'
    if code.startswith(('70','71')): return 'revenue'
    if code.startswith('77'): return 'finance'
    if code.startswith('7'): return 'other_income'
    for prefix, group in [('60','materials'),('61','materials'),('62','services'),('63','staff'),('64','taxes'),('67','finance'),('65','depreciation'),('69','income_tax'),('6','other_expenses')]:
        if code.startswith(prefix): return group
    return 'unmapped'

# ---------------------------------------------------------------- 2.9.69: audit-report layout, two years or a period
CASH_GROUPS = ['cash']
WORKING = ['inventory', 'receivables', 'current_assets', 'payables', 'current_liabilities', 'unmapped']
INVESTING = ['ppe', 'intangible', 'noncurrent_assets']
FINANCING = ['capital', 'reserves', 'retained', 'noncurrent_liabilities']
LINE_TITLES = {'ppe': 'Property, plant and equipment', 'intangible': 'Intangible assets', 'noncurrent_assets': 'Other non-current assets',
               'inventory': 'Inventories', 'receivables': 'Trade and other receivables', 'cash': 'Cash and cash equivalents',
               'current_assets': 'Other current assets', 'capital': 'Share capital', 'reserves': 'Reserves', 'retained': 'Retained earnings',
               'noncurrent_liabilities': 'Non-current liabilities and provisions', 'payables': 'Trade and other payables',
               'current_liabilities': 'Other current liabilities', 'revenue': 'Revenue', 'other_income': 'Other income',
               'materials': 'Cost of materials and goods', 'services': 'External services', 'staff': 'Staff costs', 'taxes': 'Taxes and duties',
               'finance': 'Finance costs, net', 'depreciation': 'Depreciation and provisions', 'other_expenses': 'Other expenses',
               'income_tax': 'Income tax', 'unmapped': 'Accounts to classify'}


def _day(value):
    return iso_date(value)


def _fill(text, values):
    for key, value in values.items(): text = text.replace('{' + key + '}', str(value))
    return text


def _text(cfg, kind, name, defaults, values):
    saved = (cfg.get(kind, {}) or {}).get(name)
    if saved is None or not str(saved).strip() or str(saved).strip() in OLD_DEFAULTS: saved = defaults[name]
    return _fill(saved, values)


def load_period(db, start, end, basis):
    """Balances of one company-year file for the period start..end (inclusive), in `basis`.
    Returns opening and closing balances (balance-sheet accounts), the P&L of the period, the profit of the year before the period."""
    fy_start = end[:4] + '-01-01'
    with db.connect() as conn:
        rows = [dict(r) for r in conn.execute("""SELECT j.*,a.code,a.name_en,e.entry_date,e.source_type,e.voucher_type,e.description entry_description,e.currency
          FROM journal_lines j JOIN journal_entries e ON e.id=j.entry_id JOIN accounts a ON a.id=j.account_id
          LEFT JOIN invoices i ON e.source_type='invoice' AND i.id=e.source_id
          WHERE (e.source_type!='invoice' OR i.status IN ('posted','cancelled') OR i.status IS NULL)""")]
    closing = defaultdict(lambda: ZERO); opening = defaultdict(lambda: ZERO); pnl = defaultdict(lambda: ZERO); before = defaultdict(lambda: ZERO)
    names = {}; count = 0
    for row in rows:
        day = _day(row['entry_date'])
        if day > end: continue
        if day >= fy_start and (row['source_type'] == 'year_close' or (row['voucher_type'] == '05' and (row['entry_description'] or '').startswith('CLOSING 6&7 - '))): continue
        code = row['code']; names[code] = row['name_en']
        value = number(row['debit']) - number(row['credit'])
        if row['line_currency'] and row['amount'] not in (None, ''):
            raw = row['amount_usd'] if basis == 'USD' else row['amount_lbp']
            if raw in (None, ''): raise ValueError(f'Missing {basis} equivalent for account {code}, {day}')
            value = number(raw) * (1 if value >= 0 else -1)
        elif row['currency'] != basis:
            value = db._converted_amount(value, row['currency'], basis, day)
        is_opening = day < fy_start or row['source_type'] == 'opening' or row['voucher_type'] == '04'
        if code[:1] in '67':
            if is_opening: continue  # profit of earlier years is already in retained earnings
            if day < start: before[code] += value
            else: pnl[code] += value; count += 1
            continue
        closing[code] += value
        if is_opening or day < start: opening[code] += value
        else: count += 1
    return dict(closing=closing, opening=opening, pnl=pnl, before=before, names=names, count=count)


def period_data(db, start, end, basis, label):
    cfg = config(db); raw = load_period(db, start, end, basis); mapping = cfg.get('mapping', {})
    def group(code, value):
        found = [p for p in mapping if code.startswith(p)]
        return mapping[max(found, key=len)] if found else default_group(code, value)
    close_g = defaultdict(lambda: ZERO); open_g = defaultdict(lambda: ZERO); pnl_g = defaultdict(lambda: ZERO); accounts = defaultdict(dict)
    for code in sorted(set(raw['closing']) | set(raw['opening'])):
        g = group(code, raw['closing'][code])
        close_g[g] += raw['closing'][code]; open_g[group(code, raw['opening'][code])] += raw['opening'][code]
        if raw['closing'][code]: accounts[g][code] = (raw['names'][code], raw['closing'][code])
    for code in sorted(raw['pnl']):
        g = group(code, raw['pnl'][code]); pnl_g[g] += raw['pnl'][code]
        if raw['pnl'][code]: accounts[g][code] = (raw['names'][code], raw['pnl'][code])
    profit = -sum(raw['pnl'].values(), ZERO); profit_before = -sum(raw['before'].values(), ZERO)
    depreciation = pnl_g['depreciation']
    def delta(groups): return sum((close_g[g] - open_g[g] for g in groups), ZERO)
    supplements = cfg.get('supplements', {}) if cfg.get('basis', basis) == basis else {}
    extra = {k: number(v) for k, v in supplements.items() if v != ''}
    cash_flow = {'profit': profit, 'depreciation': depreciation,
                 'working': {g: -(close_g[g] - open_g[g]) for g in WORKING},
                 'operating': profit + depreciation - delta(WORKING),
                 'investing': -(delta(INVESTING) + depreciation),
                 'financing': -delta(FINANCING)}
    reviewed = all(k in extra for k in ('cf_operating', 'cf_investing', 'cf_financing'))
    if reviewed:
        cash_flow.update(operating=extra['cf_operating'], investing=extra['cf_investing'], financing=extra['cf_financing'], fx=extra.get('cf_fx', ZERO))
    cash_flow['reviewed'] = reviewed
    equity_open = -sum((open_g[g] for g in EQUITY), ZERO) + profit_before
    equity_close = -sum((close_g[g] for g in EQUITY), ZERO) + profit_before + profit
    return dict(label=label, start=start, end=end, config=cfg, close=close_g, open=open_g, pnl=pnl_g, accounts=accounts, profit=profit,
                profit_before=profit_before, equity_open=equity_open, equity_close=equity_close, cash=cash_flow, extra=extra, count=raw['count'])


def periods_from(options, available_years):
    """[(year of the file, start, end, label)] - newest first. Two years: full calendar years. Period: From / As of
    (inside one fiscal year), and the same period one year before when asked and available."""
    if options.get('fs_mode') == 'period':
        start, end = _day(options.get('date_from')), _day(options.get('date_to'))
        if start > end: raise ValueError('From must be on or before As of')
        if start[:4] != end[:4]: raise ValueError('A period must stay inside one fiscal year (each year has its own books)')
        year = int(end[:4]); result = [(year, start, end, f'{start[8:]}-{start[5:7]} to {end[8:]}-{end[5:7]}-{end[:4]}')]
        if options.get('fs_compare') and (year - 1) in available_years:
            ps, pe = f'{year - 1}{start[4:]}', f'{year - 1}{end[4:]}'
            if pe[5:] == '02-29': pe = pe[:8] + '28'
            result.append((year - 1, ps, pe, f'{ps[8:]}-{ps[5:7]} to {pe[8:]}-{pe[5:7]}-{pe[:4]}'))
        return result
    return [(y, f'{y}-01-01', f'{y}-12-31', f'31-12-{y}') for y in years_from(options.get('years'))]


def build(databases, options):
    basis = options.get('basis', 'USD')
    if basis not in ('USD', 'LBP'): raise ValueError('Choose USD or LBP')
    periods = periods_from(options, set(databases))
    missing = [str(y) for y, *_rest in periods if y not in databases]
    if missing: raise ValueError('Fiscal year not found: ' + ', '.join(missing))
    data = [period_data(databases[y], s, e, basis, label) for y, s, e, label in periods]
    current = data[0]; settings = databases[periods[0][0]].settings(); cfg = current['config']
    company = settings.get('company_name') or '[Company name]'
    full_year = current['start'][5:] == '01-01' and current['end'][5:] == '12-31'
    end_text = f"{int(current['end'][8:])} {['January','February','March','April','May','June','July','August','September','October','November','December'][int(current['end'][5:7]) - 1]} {current['end'][:4]}"
    period_text = 'year' if full_year else f"period from {current['start'][8:]}-{current['start'][5:7]}-{current['start'][:4]}"
    for_period = f'for the year ended {end_text}' if full_year else f"for the period from {current['start'][8:]}-{current['start'][5:7]}-{current['start'][:4]} to {end_text}"
    values = {'company': company, 'end_text': end_text, 'period_text': period_text, 'basis': basis,
              'address_text': f", {settings['company_address']}" if settings.get('company_address') else '',
              'inventory_method': 'first-in first-out (FIFO)' if settings.get('inventory_method') == 'fifo' else 'weighted average cost'}
    heads = [f"{d['label']} ({basis})" for d in data]
    as_at = [f"{d['end'][8:]}-{d['end'][5:7]}-{d['end'][:4]} ({basis})" for d in data]
    sections = []; warnings = []
    q = lambda v: money(v) if isinstance(v, Decimal) else v

    # ---- Independent auditor's report
    audit_rows = [[_text(cfg, 'audit', 'Addressee', AUDIT, values)]]
    for name, title in (('Opinion', 'Opinion'), ('Basis for opinion', 'Basis for Opinion'), ('Going concern / key audit matters', 'Key Audit Matters'),
                        ('Other information', 'Other Information'), ('Management and governance responsibilities', 'Responsibilities of Management and Those Charged with Governance for the Financial Statements'),
                        ('Auditor responsibilities', "Auditor's Responsibilities for the Audit of the Financial Statements"),
                        ('Other legal and regulatory requirements', 'Report on Other Legal and Regulatory Requirements'), ('Signature, address and report date', '')):
        text = _text(cfg, 'audit', name, AUDIT, values).strip()
        if not text: continue
        if title: audit_rows.append([title.upper()])
        audit_rows += [[line] for line in text.splitlines() if line.strip()]
    sections.append(dict(heading="INDEPENDENT AUDITOR'S REPORT", headers=['Text'], rows=audit_rows, total_rows=[], narrative=True, page_break=True))

    # ---- note numbers for the statement lines that have amounts
    note_no = {}; next_note = [5]
    def note_for(group):
        if not any(d['accounts'].get(group) for d in data): return ''
        if group not in note_no: note_no[group] = next_note[0]; next_note[0] += 1
        return str(note_no[group])
    sign = lambda g: -1 if g in EQUITY + LIABILITIES + INCOME else 1

    # ---- Statement of financial position
    rows = []; totals = []
    def line(label, fn, total=False, note=''):
        rows.append([label, note] + [q(fn(d)) for d in data])
        if total: totals.append(len(rows) - 1)
    def heading(label): rows.append([label, ''] + ['' for _ in data])
    heading('ASSETS'); heading('Non-current assets')
    for g in ['ppe', 'intangible', 'noncurrent_assets']:
        if any(d['close'][g] for d in data): line(LINE_TITLES[g], lambda d, g=g: d['close'][g], note=note_for(g))
    line('Total non-current assets', lambda d: sum((d['close'][g] for g in ['ppe', 'intangible', 'noncurrent_assets']), ZERO), True)
    heading('Current assets')
    for g in ['inventory', 'receivables', 'current_assets', 'cash']:
        if any(d['close'][g] for d in data): line(LINE_TITLES[g], lambda d, g=g: d['close'][g], note=note_for(g))
    line('Total current assets', lambda d: sum((d['close'][g] for g in ['inventory', 'receivables', 'current_assets', 'cash']), ZERO), True)
    line('TOTAL ASSETS', lambda d: sum((d['close'][g] for g in ASSETS), ZERO), True)
    heading('EQUITY AND LIABILITIES'); heading('Equity')
    for g in EQUITY:
        if any(d['close'][g] for d in data): line(LINE_TITLES[g], lambda d, g=g: -d['close'][g], note=note_for(g))
    line('Profit for the year' if full_year else 'Profit for the year to date', lambda d: d['profit'] + d['profit_before'])
    line('Total equity', lambda d: d['equity_close'], True)
    heading('Liabilities')
    for g in LIABILITIES:
        if any(d['close'][g] for d in data): line(LINE_TITLES[g], lambda d, g=g: -d['close'][g], note=note_for(g))
    line('Total liabilities', lambda d: -sum((d['close'][g] for g in LIABILITIES), ZERO), True)
    line('TOTAL EQUITY AND LIABILITIES', lambda d: d['equity_close'] - sum((d['close'][g] for g in LIABILITIES), ZERO), True)
    if any(abs(d['close']['unmapped']) >= Decimal('.01') for d in data):
        line(LINE_TITLES['unmapped'] + ' (see review points)', lambda d: d['close']['unmapped'], note=note_for('unmapped'))
    sections.append(dict(heading=f'STATEMENT OF FINANCIAL POSITION as at {end_text}', headers=['', 'Notes'] + as_at, rows=rows, total_rows=totals, page_break=True, fixed=True))

    # ---- Statement of profit or loss
    rows = []; totals = []
    for g in INCOME:
        if any(d['pnl'][g] for d in data): line(LINE_TITLES[g], lambda d, g=g: -d['pnl'][g], note=note_for(g))
    line('Total income', lambda d: -sum((d['pnl'][g] for g in INCOME), ZERO), True)
    for g in EXPENSES:
        if g != 'income_tax' and any(d['pnl'][g] for d in data): line(LINE_TITLES[g], lambda d, g=g: -d['pnl'][g], note=note_for(g))
    line('Profit / (loss) before tax', lambda d: d['profit'] + d['pnl']['income_tax'], True)
    if any(d['pnl']['income_tax'] for d in data): line(LINE_TITLES['income_tax'], lambda d: -d['pnl']['income_tax'], note=note_for('income_tax'))
    line('PROFIT / (LOSS) FOR THE ' + ('YEAR' if full_year else 'PERIOD'), lambda d: d['profit'], True)
    line('Other comprehensive income', lambda d: d['extra'].get('oci', ZERO))
    line('TOTAL COMPREHENSIVE INCOME', lambda d: d['profit'] + d['extra'].get('oci', ZERO), True)
    sections.append(dict(heading=f"STATEMENT OF PROFIT OR LOSS AND OTHER COMPREHENSIVE INCOME {for_period}",
                         headers=['', 'Notes'] + heads, rows=rows, total_rows=totals, page_break=True, fixed=True))

    # ---- Statement of changes in equity (oldest period first)
    rows = []; totals = []
    for d in reversed(data):
        open_c = {g: -d['open'][g] for g in EQUITY}; close_c = {g: -d['close'][g] for g in EQUITY}
        open_c['retained'] += d['profit_before']; close_c['retained'] += d['profit_before']
        rows.append([f"Balance at start ({d['start'][8:]}-{d['start'][5:7]}-{d['start'][:4]})"] + [q(open_c[g]) for g in EQUITY] + [q(d['equity_open'])])
        rows.append(['Profit / (loss) for the period'] + [ZERO, ZERO, q(d['profit'])] + [q(d['profit'])])
        movement = {g: close_c[g] - open_c[g] for g in EQUITY}
        if any(movement[g] for g in EQUITY):
            rows.append(['Capital movements, dividends and transfers'] + [q(movement[g]) for g in EQUITY] + [q(sum(movement.values(), ZERO))])
        close_c['retained'] += d['profit']
        rows.append([f"Balance at end ({d['end'][8:]}-{d['end'][5:7]}-{d['end'][:4]})"] + [q(close_c[g]) for g in EQUITY] + [q(d['equity_close'])])
        totals.append(len(rows) - 1)
    sections.append(dict(heading=f'STATEMENT OF CHANGES IN EQUITY ({basis})', headers=['', 'Share capital', 'Reserves', 'Retained earnings', 'Total'],
                         rows=rows, total_rows=totals, page_break=True, fixed=True))

    # ---- Statement of cash flows (indirect method)
    rows = []; totals = []
    heading('CASH FLOWS FROM OPERATING ACTIVITIES')
    line('Profit / (loss) for the period', lambda d: d['cash']['profit'])
    line('Adjustment: depreciation and provisions', lambda d: d['cash']['depreciation'])
    for g in WORKING:
        if any(d['cash']['working'][g] for d in data):
            label = {'inventory': '(Increase) / decrease in inventories', 'receivables': '(Increase) / decrease in trade and other receivables',
                     'current_assets': '(Increase) / decrease in other current assets', 'payables': 'Increase / (decrease) in trade and other payables',
                     'current_liabilities': 'Increase / (decrease) in other current liabilities', 'unmapped': 'Movement in accounts to classify'}[g]
            line(label, lambda d, g=g: d['cash']['working'][g])
    line('Net cash from operating activities', lambda d: d['cash']['operating'], True)
    heading('CASH FLOWS FROM INVESTING ACTIVITIES')
    line('Acquisition / (disposal) of non-current assets, net', lambda d: d['cash']['investing'])
    line('Net cash used in investing activities', lambda d: d['cash']['investing'], True)
    heading('CASH FLOWS FROM FINANCING ACTIVITIES')
    line('Capital, borrowings and dividends, net', lambda d: d['cash']['financing'])
    line('Net cash from financing activities', lambda d: d['cash']['financing'], True)
    line('NET INCREASE / (DECREASE) IN CASH', lambda d: d['cash']['operating'] + d['cash']['investing'] + d['cash']['financing'] + d['cash'].get('fx', ZERO), True)
    line('Cash and cash equivalents at start', lambda d: d['open']['cash'])
    line('CASH AND CASH EQUIVALENTS AT END', lambda d: d['close']['cash'], True)
    sections.append(dict(heading=f'STATEMENT OF CASH FLOWS {for_period}', headers=['', ''] + heads, rows=rows, total_rows=totals, page_break=True, fixed=True))

    # ---- Notes
    notes = [('1. GENERAL INFORMATION', 'Entity and activities'), ('2. BASIS OF PREPARATION', 'Basis of preparation'),
             ('3. MATERIAL ACCOUNTING POLICIES', 'Material accounting policies'), ('4. JUDGEMENTS AND ESTIMATES', 'Judgements and estimates')]
    first = True
    for title, name in notes:
        sections.append(dict(heading='NOTES TO THE FINANCIAL STATEMENTS - ' + title if first else title, headers=['Text'],
                             rows=[[p] for p in _text(cfg, 'notes', name, NARRATIVES, values).splitlines() if p.strip()], total_rows=[], narrative=True, page_break=first))
        first = False
    for group, number_ in sorted(note_no.items(), key=lambda item: item[1]):
        codes = sorted(set().union(*(d['accounts'].get(group, {}).keys() for d in data)))
        rows = []
        for code in codes:
            name = next((d['accounts'][group][code][0] for d in data if code in d['accounts'].get(group, {})), '')
            rows.append([code, name] + [q(sign(group) * d['accounts'].get(group, {}).get(code, ('', ZERO))[1]) for d in data])
        rows.append(['', 'TOTAL'] + [q(sign(group) * (d['close'][group] if group in ASSETS + EQUITY + LIABILITIES + ['unmapped'] else d['pnl'][group])) for d in data])
        sections.append(dict(heading=f'{number_}. {LINE_TITLES[group].upper()}', headers=['Account', 'Name'] + heads, rows=rows, total_rows=[len(rows) - 1], fixed=True))
    n = next_note[0]
    for name in ('Currency and inflation', 'Related parties and commitments', 'Events and going concern', 'Additional disclosures'):
        text = _text(cfg, 'notes', name, NARRATIVES, values)
        sections.append(dict(heading=f'{n}. {name.upper()}', headers=['Text'], rows=[[p] for p in text.splitlines() if p.strip()], total_rows=[], narrative=True)); n += 1

    # ---- review points for the preparer (last page, remove before issue)
    for d in data:
        difference = sum((d['close'][g] for g in ASSETS + LIABILITIES), ZERO) - d['equity_close']
        if abs(difference) >= Decimal('.01'): warnings.append(f"{d['label']}: the statement of financial position does not balance ({money(difference)} {basis}) - check classifications.")
        if abs(d['close']['unmapped']) >= Decimal('.01') or d['pnl']['unmapped']: warnings.append(f"{d['label']}: accounts to classify ({money(d['close']['unmapped'] + d['pnl']['unmapped'])} {basis}) - Edit Notes / Audit / Mapping.")
        if not d['count']: warnings.append(f"{d['label']}: no posted movements in the period.")
        if not d['cash']['reviewed']: warnings.append(f"{d['label']}: cash flows are calculated from the balance sheet movements (indirect method); review the classification of investing and financing items.")
    if len(data) == 1: warnings.append('Single period: IAS 1 requires comparative figures for the preceding period.')
    warnings.append("The auditor's report is a template: the auditor completes and signs it after the audit. Remove this page before issuing.")
    sections.append(dict(heading='PREPARER REVIEW POINTS (remove before issue)', headers=['Point'], rows=[[w] for w in warnings], total_rows=[], narrative=True, page_break=True))
    return dict(title='Financial Statements, Notes and Audit Report',
                meta=[company, ('Year ended ' if full_year else 'Period ended ') + end_text + ' - with comparative figures' * (len(data) > 1), f'Presentation currency: {basis}'],
                sections=sections)


def year_data(db, year, basis):
    """Full calendar year (kept for older callers): period_data plus equity_start / equity_end."""
    data = period_data(db, f'{int(year)}-01-01', f'{int(year)}-12-31', basis, f'31-12-{int(year)}')
    data.update(equity_start=data['equity_open'], equity_end=data['equity_close'], totals=data['close'])
    return data
