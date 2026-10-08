# 07 - Output formats: chat, Excel, dashboard

## Contents
1. Choosing the format
2. Chat answer template and Basis line
3. Number and date formatting
4. JSON contract (shared by both scripts)
5. Excel with `scripts/build_xlsx.py`
6. Dashboard with `scripts/render_dashboard.py`
7. Without code execution

---

## 1. Choosing the format

| Situation | Format |
|---|---|
| A figure, a short comparison, up to ~15 rows | Chat |
| A list the user will work through or forward (OP-Liste, document list, trial balance), more than ~15 rows, or "Liste"/"Excel"/"export" requested | Excel (.xlsx) |
| Overview with several KPIs, close status, comparison across subsidiaries, or "Dashboard"/"Übersicht" requested | Dashboard (.html) |

When you create a file, still give the key result in chat (2-5 lines) plus the Basis line, and
name the file.

## 2. Chat answer template and Basis line

```
<Ergebnis in 1-2 Sätzen.>

| Gesellschaft | ... | Betrag |
|---|---|---:|
| ... | ... | 1.234,56 € |

Auffällig: <Differenzen, Blocker, Besonderheiten - oder weglassen>

Basis: <Account> (<Prod|Sandbox|Demo>) · <Gesellschaft|konsolidiert auf X> · <Periode|Stichtag> · <Währung> · <Buch> · nur gebuchte Werte · Stand <Datum> · <vordatierte Belege: n nicht enthalten>
```
- English questions get English labels ("Basis:" stays as "Basis:").
- No SuiteQL in chat unless asked. If asked, give the exact query you ran.
- Amounts right-aligned in tables; currency on every amount or in the column header.

## 3. Number and date formatting

| | German | English |
|---|---|---|
| Amount | `1.234.567,89 €` | `EUR 1,234,567.89` or `$1,234,567.89` |
| Negative | `-1.234,56 €` | `-1,234.56` |
| Date | `07.10.2026` | `2026-10-07` or `Oct 7, 2026` |
| Period | `Sep 2026` | `Sep 2026` |

SuiteQL dates arrive as `M/D/YYYY` - select ISO (`TO_CHAR(...,'YYYY-MM-DD')`) and convert.
Round translated (consolidated) amounts to 2 decimals.

## 4. JSON contract (shared by both scripts)

Write the data to a JSON file, then call the script. Keep files small: aggregate in SQL and
select only the columns you need (under ~3,000 rows per sheet; above that, split by subsidiary
or period, or summarise).

```json
{
  "meta": {
    "title": "OP-Liste Debitoren",
    "lang": "de",
    "account": "4a-DEMO_ALL",
    "env": "Demo",
    "as_of": "2026-10-08",
    "basis": "alle Gesellschaften · je Basiswährung · Primary Book · nur gebuchte Werte",
    "notes": ["151 vordatierte Belege nicht enthalten"],
    "checks": [
      {"label": "Nebenbuch = Hauptbuch (Germany GmbH)", "status": "ok", "detail": "9.740,00 = 9.740,00"},
      {"label": "Nebenbuch = Hauptbuch (United States)", "status": "fail", "detail": "Differenz 101.124,29 USD"}
    ],
    "queries": [
      {"purpose": "Offene Posten", "suiteql": "SELECT ...", "totalResults": 1062, "fetched": 1062}
    ]
  },
  "kpis": [
    {"label": "Offene Forderungen Germany GmbH", "value": 9740, "type": "amount", "currency": "EUR", "note": "davon überfällig 9.740"}
  ],
  "charts": [
    {"title": "Überfällig nach Gesellschaft", "unit": "EUR", "series": [{"label": "Germany GmbH", "value": 9740}]}
  ],
  "sheets": [
    {
      "name": "Daten",
      "columns": [
        {"key": "subsidiary", "label": "Gesellschaft", "type": "text"},
        {"key": "currency", "label": "Währung", "type": "currency"},
        {"key": "doc", "label": "Beleg", "type": "text"},
        {"key": "due", "label": "Fällig", "type": "date"},
        {"key": "open", "label": "Offen", "type": "amount"},
        {"key": "share", "label": "Anteil", "type": "pct"}
      ],
      "rows": [
        {"subsidiary": "Germany GmbH", "currency": "EUR", "doc": "INV252", "due": "2026-10-04", "open": 7140, "share": 0.733}
      ],
      "totals": true
    }
  ]
}
```
- Column `type`: `text`, `currency` (currency code, text), `date` (`YYYY-MM-DD` or `M/D/YYYY`),
  `amount`, `number`, `pct` (0.25 = 25 %).
- `checks[].status`: `ok`, `warn`, `fail`, `unknown` (= not determinable, e.g. period lock).
- `totals: true` adds totals for `amount` columns. If the sheet has a `currency` column with more
  than one value, the script writes one total per currency and **no grand total** (no
  cross-currency sums). `"subtotal_by": "<key>"` forces totals per value of another column.
- `kpis`, `charts` are used by the dashboard only; `sheets` are used by both (in the dashboard
  they render as tables).

## 5. Excel with `scripts/build_xlsx.py`

```bash
python scripts/build_xlsx.py data.json OP_Liste_Debitoren_2026-10-08.xlsx
python scripts/build_xlsx.py --selftest   # checks the installation (needs openpyxl)
```
Produces: one sheet per entry in `sheets` (header row, frozen pane, filter, number and date
formats, totals as formulas) and a last sheet "Quelle" (English: "Source") with account,
environment, as-of date, basis, notes, checks and every query with its row counts.
File names: no spaces, use underscores and the as-of date.

## 6. Dashboard with `scripts/render_dashboard.py`

```bash
python scripts/render_dashboard.py data.json Abschluss_Sep_2026_US.html
python scripts/render_dashboard.py --selftest
```
Produces one self-contained HTML file (no external scripts, fonts or CDNs; light and dark mode):
header with title, account and Basis; KPI tiles; check list with status (ok / attention /
blocker / not determinable, shown with text labels, not colour alone); bar charts; tables; a
collapsible "Quelle" section with checks and queries.

For a close-status dashboard, put each close check (`03-gl-close.md`, section 7) into
`meta.checks` and the blocking documents into a sheet.

## 7. Without code execution

If Python is not available (some claude.ai setups):
- Dashboard: create an HTML artifact directly with the same structure (header + Basis, KPI
  tiles, check list with text status, tables, "Quelle" section). Inline CSS only.
- Lists: a Markdown table with at most 50 rows, then the full data as CSV in a code block, and
  one sentence that an .xlsx needs Cowork or code execution.
