#!/usr/bin/env python3
"""Build a formatted .xlsx from the netsuite-finance-analyst JSON contract.

Usage:
    python build_xlsx.py data.json output.xlsx
    python build_xlsx.py --selftest

The JSON contract is described in references/07-output-formats.md. Each entry in
"sheets" becomes a worksheet; a final "Quelle" (de) / "Source" (en) sheet holds the
account, basis, notes, checks and every query with its row counts.

Totals never mix currencies: if a sheet has a column of type "currency" with more
than one value, one total row per currency is written and no grand total.
"""

from __future__ import annotations

import json
import re
import sys
import tempfile
from datetime import date, datetime
from pathlib import Path

try:
    from openpyxl import Workbook, load_workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter
except ImportError:  # pragma: no cover - environment dependent
    sys.stderr.write("openpyxl is required: pip install openpyxl\n")
    raise

LABELS = {
    "de": {
        "source": "Quelle",
        "total": "Summe",
        "total_for": "Summe {value}",
        "account": "Account",
        "env": "Umgebung",
        "as_of": "Stand",
        "basis": "Basis",
        "notes": "Hinweise",
        "checks": "Prüfungen",
        "status": "Status",
        "detail": "Detail",
        "queries": "Abfragen",
        "purpose": "Zweck",
        "total_results": "Treffer (totalResults)",
        "fetched": "Abgerufen",
        "created": "Erstellt",
        "status_text": {
            "ok": "OK",
            "warn": "Achtung",
            "fail": "Blocker",
            "unknown": "nicht bestimmbar",
        },
    },
    "en": {
        "source": "Source",
        "total": "Total",
        "total_for": "Total {value}",
        "account": "Account",
        "env": "Environment",
        "as_of": "As of",
        "basis": "Basis",
        "notes": "Notes",
        "checks": "Checks",
        "status": "Status",
        "detail": "Detail",
        "queries": "Queries",
        "purpose": "Purpose",
        "total_results": "totalResults",
        "fetched": "Fetched",
        "created": "Created",
        "status_text": {
            "ok": "OK",
            "warn": "Attention",
            "fail": "Blocker",
            "unknown": "not determinable",
        },
    },
}

AMOUNT_FORMAT = "#,##0.00;-#,##0.00"
NUMBER_FORMAT = "#,##0.##"
PCT_FORMAT = "0.0%"
DATE_FORMATS = {"de": "DD.MM.YYYY", "en": "YYYY-MM-DD"}
HEADER_FILL = PatternFill("solid", fgColor="E1E0D9")
TOTAL_FILL = PatternFill("solid", fgColor="F0EFEC")
BOLD = Font(bold=True)
INVALID_SHEET_CHARS = re.compile(r"[\[\]\*\?/\\:]")


def parse_date(value: object) -> date | None:
    """Accept YYYY-MM-DD, YYYY-MM-DD HH:MM, or NetSuite's M/D/YYYY."""
    if value in (None, ""):
        return None
    if isinstance(value, (date, datetime)):
        return value if isinstance(value, date) else value.date()
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%m/%d/%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def to_number(value: object) -> float | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).replace(",", ""))
    except ValueError:
        return None


def sheet_title(name: str, used: set[str]) -> str:
    base = INVALID_SHEET_CHARS.sub("_", name or "Sheet").strip()[:31] or "Sheet"
    title, n = base, 2
    while title in used:
        suffix = f"_{n}"
        title = base[: 31 - len(suffix)] + suffix
        n += 1
    used.add(title)
    return title


def write_data_sheet(ws, sheet: dict, lang: str) -> None:
    labels = LABELS[lang]
    columns = sheet.get("columns") or []
    rows = sheet.get("rows") or []
    if not columns and rows:
        columns = [{"key": k, "label": k, "type": "text"} for k in rows[0]]

    for c, col in enumerate(columns, start=1):
        cell = ws.cell(row=1, column=c, value=col.get("label", col["key"]))
        cell.font = BOLD
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(vertical="top", wrap_text=True)

    widths = [len(str(col.get("label", col["key"]))) for col in columns]
    for r, row in enumerate(rows, start=2):
        for c, col in enumerate(columns, start=1):
            kind = col.get("type", "text")
            raw = row.get(col["key"])
            cell = ws.cell(row=r, column=c)
            if kind == "date":
                parsed = parse_date(raw)
                cell.value = parsed if parsed else raw
                if parsed:
                    cell.number_format = DATE_FORMATS[lang]
                shown = 10
            elif kind in ("amount", "number", "pct"):
                num = to_number(raw)
                cell.value = num if num is not None else raw
                cell.number_format = {
                    "amount": AMOUNT_FORMAT,
                    "number": NUMBER_FORMAT,
                    "pct": PCT_FORMAT,
                }[kind]
                shown = len(f"{num:,.2f}") if num is not None else len(str(raw or ""))
            else:
                cell.value = raw
                shown = len(str(raw)) if raw is not None else 0
            widths[c - 1] = max(widths[c - 1], shown)

    last_data_row = len(rows) + 1
    if columns:
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = f"A1:{get_column_letter(len(columns))}{max(last_data_row, 1)}"

    if sheet.get("totals") and rows:
        write_totals(ws, sheet, columns, rows, last_data_row, labels)

    for c, width in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(c)].width = min(max(width + 2, 8), 60)


def write_totals(ws, sheet, columns, rows, last_data_row, labels) -> None:
    amount_cols = [
        (i, col) for i, col in enumerate(columns, start=1) if col.get("type") == "amount"
    ]
    if not amount_cols:
        return

    group_key = sheet.get("subtotal_by")
    if not group_key:
        currency_cols = [col["key"] for col in columns if col.get("type") == "currency"]
        if currency_cols:
            values = {row.get(currency_cols[0]) for row in rows}
            if len(values) > 1:
                group_key = currency_cols[0]

    label_col = 1
    out_row = last_data_row + 2
    first, last = 2, last_data_row

    if group_key:
        key_index = next(
            (i for i, col in enumerate(columns, start=1) if col["key"] == group_key), None
        )
        groups = sorted({str(row.get(group_key)) for row in rows})
        key_letter = get_column_letter(key_index) if key_index else None
        for value in groups:
            ws.cell(row=out_row, column=label_col, value=labels["total_for"].format(value=value))
            for c, _col in amount_cols:
                letter = get_column_letter(c)
                if key_letter:
                    formula = (
                        f'=SUMIF({key_letter}{first}:{key_letter}{last},"{value}",'
                        f"{letter}{first}:{letter}{last})"
                    )
                else:
                    formula = None
                cell = ws.cell(row=out_row, column=c, value=formula)
                cell.number_format = AMOUNT_FORMAT
            style_total_row(ws, out_row, len(columns))
            out_row += 1
        return

    ws.cell(row=out_row, column=label_col, value=labels["total"])
    for c, _col in amount_cols:
        letter = get_column_letter(c)
        cell = ws.cell(row=out_row, column=c, value=f"=SUM({letter}{first}:{letter}{last})")
        cell.number_format = AMOUNT_FORMAT
    style_total_row(ws, out_row, len(columns))


def style_total_row(ws, row: int, ncols: int) -> None:
    for c in range(1, ncols + 1):
        cell = ws.cell(row=row, column=c)
        cell.font = BOLD
        cell.fill = TOTAL_FILL


def write_source_sheet(ws, meta: dict, lang: str) -> None:
    labels = LABELS[lang]
    wrap = Alignment(vertical="top", wrap_text=True)
    row = 1

    def pair(label: str, value: object) -> None:
        nonlocal row
        ws.cell(row=row, column=1, value=label).font = BOLD
        cell = ws.cell(row=row, column=2, value=value)
        cell.alignment = wrap
        row += 1

    if meta.get("title"):
        ws.cell(row=row, column=1, value=meta["title"]).font = Font(bold=True, size=13)
        row += 2
    pair(labels["account"], meta.get("account", ""))
    pair(labels["env"], meta.get("env", ""))
    pair(labels["as_of"], meta.get("as_of", ""))
    pair(labels["basis"], meta.get("basis", ""))
    pair(labels["created"], datetime.now().strftime("%Y-%m-%d %H:%M"))

    notes = meta.get("notes") or []
    if notes:
        row += 1
        ws.cell(row=row, column=1, value=labels["notes"]).font = BOLD
        row += 1
        for note in notes:
            ws.cell(row=row, column=2, value=note).alignment = wrap
            row += 1

    checks = meta.get("checks") or []
    if checks:
        row += 1
        ws.cell(row=row, column=1, value=labels["checks"]).font = BOLD
        row += 1
        for check in checks:
            status = labels["status_text"].get(check.get("status", ""), check.get("status", ""))
            ws.cell(row=row, column=1, value=status)
            ws.cell(row=row, column=2, value=check.get("label", "")).alignment = wrap
            ws.cell(row=row, column=3, value=check.get("detail", "")).alignment = wrap
            row += 1

    queries = meta.get("queries") or []
    if queries:
        row += 1
        ws.cell(row=row, column=1, value=labels["queries"]).font = BOLD
        row += 1
        headers = [labels["purpose"], "SuiteQL", labels["total_results"], labels["fetched"]]
        for c, header in enumerate(headers, start=1):
            cell = ws.cell(row=row, column=c, value=header)
            cell.font = BOLD
            cell.fill = HEADER_FILL
        row += 1
        for query in queries:
            ws.cell(row=row, column=1, value=query.get("purpose", "")).alignment = wrap
            ws.cell(row=row, column=2, value=query.get("suiteql", "")).alignment = wrap
            ws.cell(row=row, column=3, value=query.get("totalResults"))
            ws.cell(row=row, column=4, value=query.get("fetched"))
            row += 1

    ws.column_dimensions["A"].width = 28
    ws.column_dimensions["B"].width = 90
    ws.column_dimensions["C"].width = 22
    ws.column_dimensions["D"].width = 12


def build(data: dict, output: Path) -> Path:
    meta = data.get("meta") or {}
    lang = meta.get("lang", "de")
    if lang not in LABELS:
        lang = "en"
    wb = Workbook()
    wb.remove(wb.active)
    used: set[str] = set()
    for sheet in data.get("sheets") or []:
        ws = wb.create_sheet(sheet_title(sheet.get("name", "Daten"), used))
        write_data_sheet(ws, sheet, lang)
    ws = wb.create_sheet(sheet_title(LABELS[lang]["source"], used))
    write_source_sheet(ws, meta, lang)
    output.parent.mkdir(parents=True, exist_ok=True)
    wb.save(output)
    return output


SELFTEST_DATA = {
    "meta": {
        "title": "OP-Liste Debitoren (Selbsttest)",
        "lang": "de",
        "account": "DEMO",
        "env": "Demo",
        "as_of": "2026-10-08",
        "basis": "alle Gesellschaften · je Basiswährung · Primary Book",
        "notes": ["2 vordatierte Belege nicht enthalten"],
        "checks": [{"label": "Nebenbuch = Hauptbuch", "status": "ok", "detail": "9.740 = 9.740"}],
        "queries": [
            {
                "purpose": "Offene Posten",
                "suiteql": "SELECT 1 FROM DUAL",
                "totalResults": 3,
                "fetched": 3,
            }
        ],
    },
    "sheets": [
        {
            "name": "Daten",
            "columns": [
                {"key": "sub", "label": "Gesellschaft", "type": "text"},
                {"key": "cur", "label": "Währung", "type": "currency"},
                {"key": "doc", "label": "Beleg", "type": "text"},
                {"key": "due", "label": "Fällig", "type": "date"},
                {"key": "open", "label": "Offen", "type": "amount"},
                {"key": "share", "label": "Anteil", "type": "pct"},
            ],
            "rows": [
                {
                    "sub": "Germany GmbH",
                    "cur": "EUR",
                    "doc": "INV252",
                    "due": "2026-10-04",
                    "open": 7140,
                    "share": 0.733,
                },
                {
                    "sub": "Germany GmbH",
                    "cur": "EUR",
                    "doc": "INV268",
                    "due": "8/30/2026",
                    "open": 1500,
                    "share": 0.154,
                },
                {
                    "sub": "United States",
                    "cur": "USD",
                    "doc": "INV158",
                    "due": "2026-11-05",
                    "open": 12190,
                    "share": 1.0,
                },
            ],
            "totals": True,
        }
    ],
}


def selftest() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        out = build(SELFTEST_DATA, Path(tmp) / "selftest.xlsx")
        wb = load_workbook(out)
        assert wb.sheetnames == ["Daten", "Quelle"], wb.sheetnames
        ws = wb["Daten"]
        assert isinstance(ws["D2"].value, datetime), ws["D2"].value
        assert ws["D3"].value.date() == date(2026, 8, 30), ws["D3"].value
        totals = [ws.cell(row=r, column=1).value for r in range(6, 8)]
        assert totals == ["Summe EUR", "Summe USD"], totals
        assert str(ws["E6"].value).startswith("=SUMIF("), ws["E6"].value
        assert ws.freeze_panes == "A2"
        source = wb["Quelle"]
        assert any(source.cell(row=r, column=2).value == "SELECT 1 FROM DUAL" for r in range(1, 30))
    print("build_xlsx selftest: OK")
    return 0


def main(argv: list[str]) -> int:
    if len(argv) == 2 and argv[1] == "--selftest":
        return selftest()
    if len(argv) != 3:
        sys.stderr.write(__doc__ or "")
        return 2
    data = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
    out = build(data, Path(argv[2]))
    print(f"written: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
