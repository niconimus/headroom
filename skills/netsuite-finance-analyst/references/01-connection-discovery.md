# 01 - Connection, tools and account discovery

Read this once per conversation, before the first figure.

## Contents
1. Choosing the connector
2. Tool behaviour (what each tool really returns)
3. Account profile - discovery queries
4. Standard reports - finding, running, parsing

---

## 1. Choosing the connector

Each attached NetSuite MCP server exposes the same tool names behind a prefix:
`mcp__<server>__ns_runCustomSuiteQL`. The server name is chosen by whoever connected it and
often tells the environment: `..._Prod`, `..._SB` / `Sandbox`, `DEMO`, `TSTDRV` (test drive).

- Question names an account or environment → use exactly that server.
- Several servers, none named → ask once: "Which account should I use: A (production),
  B (sandbox)?" Do not guess; sandbox numbers look real but are copies.
- Never mix servers in one answer. Never "fill gaps" from another account.
- Put the server name in the Basis line. Add "(Sandbox)" or "(Demo)" where it applies.

## 2. Tool behaviour

| Tool | Use for | Behaviour you must know |
|---|---|---|
| `ns_runCustomSuiteQL` | almost everything | Max 5,000 rows without paging. Use `pageSize` 1000 + `pageIndex`; response has `totalResults`, `numberOfPages`. Dates come back as `M/D/YYYY` strings. Column names come back lower-case. |
| `ns_getSuiteQLMetadata` | field lists, join targets | **Always pass `recordType`.** Without it the catalog is ~120,000 characters (1,600+ tables). Joinable fields carry `x-n:joinable: true` and `x-n:recordType`. |
| `ns_listAllReports` | finding report IDs | ~50 KB. Call once, keep the IDs you need in the profile. IDs differ per account. |
| `ns_runReport` | cross-checking totals | Returns the **whole report tree** (a Trial Balance for one subsidiary returned 495 rows / 91 KB, mostly zero rows). Run it for one subsidiary, read row `"0"` (grand total) and the rows you need. |
| `ns_getSubsidiaries` | report parameter `subsidiaryId` | Negative ID = consolidated (e.g. `-1` "Parent (Consolidated)"). Empty = not OneWorld. |
| `ns_getAccountingBooks` | report parameter `book` | Also tells you whether multi-book is in use. |
| `ns_runSavedSearch` / `ns_listSavedSearches` | when the customer already has a trusted search | Results follow the search definition; check its filters before relying on totals. |
| `ns_getRecord` | one record's fields | Respects role permissions (e.g. `accountingperiod` may return 403). |
| `ns_report_filters_app`, `ns_selector_app`, `ns_prompt_library_app` | interactive pickers | Only when a human is present to click. Not in unattended runs. |
| `ns_createRecord`, `ns_updateRecord`, `ns_executeRecordAction`, `ns_getRecordActionMetadata` | - | **Forbidden.** This skill is read-only. |

## 3. Account profile - discovery queries

Run these in order; each one is verified against a OneWorld demo account. Keep the results as a
profile block (template at the end) and reuse them.

### 3.1 Subsidiaries and base currencies
```sql
SELECT s.id, s.name, s.fullname, s.parent, s.iselimination, s.isinactive,
       BUILTIN.DF(s.currency) AS base_currency, s.country
FROM subsidiary s
ORDER BY s.id
```
- Error "Record 'subsidiary' was not found" usually means a non-OneWorld account: one company,
  one base currency. Then skip subsidiary filters entirely.
- `iselimination = 'T'` marks the elimination subsidiary (e.g. "xEliminations").
- Note the parent (`parent IS NULL`) - its currency is the consolidation currency.

### 3.2 Accounting books
Call `ns_getAccountingBooks`. One book → use it (usually ID 1, "Primary Accounting Book").
Several → the primary book is the default; mention the book in every Basis line.

### 3.3 Periods
First try the standard table:
```sql
SELECT id, periodname, TO_CHAR(startdate,'YYYY-MM-DD') AS start_d,
       TO_CHAR(enddate,'YYYY-MM-DD') AS end_d, isyear, isquarter, isadjust, closed, alllocked
FROM accountingperiod
WHERE isyear = 'F' AND isquarter = 'F'
ORDER BY startdate
```
If this fails with "Record 'accountingperiod' was not found" (seen in practice), use the
fallback - it lists every posting period that has GL activity:
```sql
SELECT apa.accountingperiod AS period_id, BUILTIN.DF(apa.accountingperiod) AS period_name,
       COUNT(*) AS n
FROM AccountPeriodActivity apa
GROUP BY apa.accountingperiod, BUILTIN.DF(apa.accountingperiod)
ORDER BY apa.accountingperiod DESC
```
- Period IDs are **not** contiguous or guaranteed chronological (quarters and years sit in
  between: Sep 2026 = 477, Oct 2026 = 479). Order periods by their name/dates, not by ID.
- With the fallback you **cannot** see whether a period is closed or locked. Say so; do not
  infer it.
- Fiscal year start: from `accountingperiod` rows with `isyear = 'T'`. Without that table, ask the
  user once ("Beginnt Ihr Geschäftsjahr im Januar?") and record the answer in the profile.
- To find the period ID for a month quickly:
  `SELECT DISTINCT t.postingperiod, BUILTIN.DF(t.postingperiod) FROM transaction t WHERE t.trandate BETWEEN TO_DATE('2026-09-01','YYYY-MM-DD') AND TO_DATE('2026-09-30','YYYY-MM-DD')`
  (may return two periods if documents were back-posted; pick by name).

### 3.4 As-of date and future-dated postings
Take today's date from the conversation/system context. Then:
```sql
SELECT COUNT(*) AS n_future, MAX(TO_CHAR(t.trandate,'YYYY-MM-DD')) AS latest
FROM transaction t
WHERE t.posting = 'T' AND t.trandate > TO_DATE('2026-10-08','YYYY-MM-DD')
```
If `n_future > 0`, the account contains future-dated postings: exclude them from "as of today"
figures and mention the count.

### 3.5 Chart of accounts overview
```sql
SELECT a.accttype, BUILTIN.DF(a.accttype) AS type_name, COUNT(*) AS n
FROM account a
WHERE a.isinactive = 'F'
GROUP BY a.accttype, BUILTIN.DF(a.accttype)
ORDER BY a.accttype
```
Account fields that exist: `id, acctnumber, accountsearchdisplaynamecopy` (name),
`fullname, accttype, currency, subsidiary` (text list), `issummary, isinactive, parent, eliminate,
generalrate, cashflowrate`. `acctnumber` can be NULL (system accounts such as "VAT on Sales [2]").

### 3.6 Table availability
Probe the tables you will need with a one-row query; record "ok" or the error:
```sql
SELECT COUNT(*) AS n FROM AccountsReceivableAging WHERE ROWNUM <= 1
```
Check at least: `transactionaccountingline`, `AccountsReceivableAging`, `AccountsPayableAging`,
`accountingperiod`, `AccountPeriodActivity`, `SystemNote`, `consolidatedExchangeRate`.

### 3.7 Profile block (keep in the conversation)
```
NetSuite-Profil: <server> (<Prod|Sandbox|Demo>) · Stand <today>
- OneWorld: ja · Konsolidierung auf <parent> (<currency>) · Eliminierung: <name> (ID)
- Gesellschaften: <id name currency>, ...
- Bücher: <id name> (primär)
- Perioden: Quelle accountingperiod | AccountPeriodActivity (Status nicht lesbar) · GJ-Beginn <Monat|unbekannt>
- Vordatierte Buchungen: <n> (bis <date>)
- Tabellen: AR-Aging ok · AP-Aging ok · SystemNote ok · accountingperiod fehlt
- Reports: Trial Balance=<id>, Balance Sheet=<id>, Income Statement=<id>, A/R Aging Summary=<id>, A/P Aging Summary=<id>
```

## 4. Standard reports - finding, running, parsing

### Finding
Call `ns_listAllReports` once and pick by **title**. Useful titles (English UI; customised
accounts may rename them, and `{#Customer#}`-style placeholders appear in some titles):
`Trial Balance`, `General Ledger`, `Balance Sheet`, `Balance Sheet Detail`, `Income Statement`,
`Income Statement Detail`, `Comparative Income Statement`, `Cash Statement`, `Cash Flow Statement`,
`A/R Aging Summary`, `A/R Aging Detail`, `A/P Aging Summary`, `A/P Aging Detail`,
`Intercompany Reconciliation`, `Intercompany Elimination`, `Realized Exchange Rate Gains and Losses`,
`Unrealized Exchange Rate Gains and Losses`, `Budget vs. Actual`, VAT/GST reports
(`VAT on Sales Summary`, `VAT on Purchases Summary`, country-specific "Sales by Tax Code" reports).
Several reports can share a title (e.g. two "Income Statement" entries); prefer the one with
`has_subsidiary_filter: true`.

### Running
Read the report's properties from `ns_listAllReports`:
- `as_of_format: true` → only `dateTo` (balance sheet, trial balance, aging).
- `as_of_format: false` → `dateFrom` and `dateTo` (P&L, GL detail).
- `has_subsidiary_filter: true` and subsidiaries exist → `subsidiaryId` is required.
  Use a negative ID for consolidated only if `supports_consolidation: true`.
- Optional parameters (`book`, `range`, `taxCashBasisMode`, ...) only when the matching
  `supports_*` flag is true.

### Parsing the output
The response is `{reportData: {"0": {...}, "1": {...}}, reportColumns: [...], currency, title}`.
- Row `"0"` holds the grand totals in `summaryLineValues`.
- Summary rows carry the group label in `value` (e.g. `"4000 - Sales"`, a customer name);
  detail rows have `isDetailLine: true` and `parent` pointing to the grouping alias.
- Column IDs are in `reportColumns`. In the A/R and A/P Aging Summary all columns are labelled
  "Open Balance" (`Current > Open Balance`, `... (2)` to `(5)`, `empty > Open Balance`). Only the
  last one, `empty > Open Balance`, is reliably the **total**. The bucket columns did not map
  consistently to due-date buckets in testing (they depend on the account's aging preferences),
  so use the report for the total only and compute buckets yourself from `dueDate`
  (`04-ar-ap.md`), stating the rule you used.
- `currency` is a symbol (`€`, `$`) - the subsidiary's base currency.

Verified example: Trial Balance, Germany GmbH, `dateTo` 2026-09-30 → totals matched the SuiteQL
trial balance exactly (A/R 2,600 / Sales -2,600). A/R Aging Summary, Germany GmbH, 2026-10-08 →
total 9,740 = AR control account in the GL = aging table filtered to documents dated up to the
as-of date.

Keep report calls small: one subsidiary per call, and never paste the raw tree into the answer.
