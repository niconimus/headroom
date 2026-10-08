#!/usr/bin/env python3
"""Render a self-contained HTML dashboard from the netsuite-finance-analyst JSON contract.

Usage:
    python render_dashboard.py data.json output.html
    python render_dashboard.py --selftest

The JSON contract is described in references/07-output-formats.md (meta, kpis, charts,
sheets). The template lives in ../assets/dashboard_template.html and has no external
dependencies; the data is embedded as JSON and rendered in the browser with textContent
only (no HTML injection from data).
"""

from __future__ import annotations

import json
import re
import sys
import tempfile
from datetime import datetime
from pathlib import Path

PLACEHOLDER = "/*__DASHBOARD_DATA__*/null"
TEMPLATE = Path(__file__).resolve().parent.parent / "assets" / "dashboard_template.html"


def embed_json(data: dict) -> str:
    text = json.dumps(data, ensure_ascii=False, indent=None, separators=(",", ":"))
    # Keep the payload from closing the <script> element or opening a comment.
    text = text.replace("</", "<\\/").replace("<!--", "<\\!--")
    # U+2028/U+2029 are valid in JSON but not in older JS string literals.
    return text.replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")


def render(data: dict, output: Path, template: Path = TEMPLATE) -> Path:
    html = template.read_text(encoding="utf-8")
    if PLACEHOLDER not in html:
        raise ValueError(f"placeholder {PLACEHOLDER!r} not found in {template}")
    payload = dict(data)
    meta = dict(payload.get("meta") or {})
    meta.setdefault("created", datetime.now().strftime("%Y-%m-%d %H:%M"))
    payload["meta"] = meta
    title = meta.get("title") or "NetSuite Dashboard"
    safe_title = str(title).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    html = html.replace("<title>NetSuite Dashboard</title>", f"<title>{safe_title}</title>")
    html = html.replace(PLACEHOLDER, embed_json(payload))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html, encoding="utf-8")
    return output


SELFTEST_DATA = {
    "meta": {
        "title": "Abschluss-Check Sep 2026 (Selbsttest) </script><b>x</b>",
        "lang": "de",
        "account": "DEMO",
        "env": "Demo",
        "as_of": "2026-10-08",
        "basis": "United States · Sep 2026 · USD · Primary Book · nur gebuchte Werte",
        "notes": ["Periodensperrstatus nicht lesbar (Recht 'Manage Accounting Periods' fehlt)"],
        "checks": [
            {"label": "Journale ohne Genehmigung", "status": "fail", "detail": "4 Belege"},
            {"label": "Nebenbuch AR = Hauptbuch", "status": "warn", "detail": "Differenz 5.279,77"},
            {"label": "Periodenstatus", "status": "unknown", "detail": "nicht lesbar"},
            {"label": "Saldenliste ausgeglichen", "status": "ok", "detail": "Soll = Haben"},
        ],
        "queries": [
            {
                "purpose": "Belegstatus",
                "suiteql": "SELECT t.type FROM transaction t WHERE t.memo = '</script>'",
                "totalResults": 22,
                "fetched": 22,
            }
        ],
    },
    "kpis": [
        {"label": "Blocker", "value": 1, "type": "number"},
        {"label": "Offene Forderungen", "value": 537557.18, "type": "amount", "currency": "USD"},
    ],
    "charts": [
        {
            "title": "Veränderung nach Konto",
            "unit": "USD",
            "series": [
                {"label": "5000 COGS", "value": -14049.58},
                {"label": "6000 Salaries", "value": 3200.5},
            ],
        }
    ],
    "sheets": [
        {
            "name": "Blocker",
            "columns": [
                {"key": "doc", "label": "Beleg", "type": "text"},
                {"key": "date", "label": "Datum", "type": "date"},
                {"key": "cur", "label": "Währung", "type": "currency"},
                {"key": "amt", "label": "Betrag", "type": "amount"},
            ],
            "rows": [
                {"doc": "JE101", "date": "9/30/2026", "cur": "USD", "amt": 1200},
                {"doc": "JE102", "date": "2026-09-29", "cur": "GBP", "amt": 300},
            ],
            "totals": True,
        }
    ],
}


def selftest() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        out = render(SELFTEST_DATA, Path(tmp) / "selftest.html")
        html = out.read_text(encoding="utf-8")
        assert PLACEHOLDER not in html
        script = html.split("<script>", 1)[1].rsplit("</script>", 1)[0]
        assert "</script>" not in script, "payload must not close the script element"
        assert not re.search(r"(src|href)\s*=\s*[\"']?https?://", html), "no external resources"
        assert "<title>Abschluss-Check Sep 2026 (Selbsttest) &lt;/script&gt;" in html
        assert '"status":"fail"' in html
    print("render_dashboard selftest: OK")
    return 0


def main(argv: list[str]) -> int:
    if len(argv) == 2 and argv[1] == "--selftest":
        return selftest()
    if len(argv) != 3:
        sys.stderr.write(__doc__ or "")
        return 2
    data = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
    out = render(data, Path(argv[2]))
    print(f"written: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
