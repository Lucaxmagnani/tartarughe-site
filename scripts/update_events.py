#!/usr/bin/env python3
"""
Daily updater for site/events.json — Le Tartarughe "During your stay".

What it does (v1, no LLM):
  1. STRIKES  — fetches the official MIT strike observatory RSS
                (scioperi.mit.gov.it), keeps transport strikes that are
                national or affect Lazio/Roma within the next LOOKAHEAD days,
                and rebuilds the "alerts" section bilingually (EN/IT) from
                structured fields.
  2. PRUNING  — drops every alert/free/event entry whose "to" date has passed.
  3. Writes site/events.json only when content actually changed
                (so the Action commits only on real updates).

Curated sections ("free", "events") are NOT auto-generated in v1: they are
kept, pruned by date, and edited by hand (or by a future LLM step) in the
JSON. Strike alerts, the time-critical part, are fully automatic.

Run locally:  python scripts/update_events.py
"""

import json
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from pathlib import Path

RSS_URL = "https://scioperi.mit.gov.it/mit2/public/scioperi/rss"
SITE_JSON = Path(__file__).resolve().parent.parent / "site" / "events.json"
LOOKAHEAD_DAYS = 30
REGION = "Lazio"           # property region
CITY_WORDS = ("roma",)     # match in notes/category for local relevance

# transport sectors we care about → bilingual labels
SECTORS = {
    "aereo":                    {"en": "Air transport strike",            "it": "Sciopero trasporto aereo"},
    "ferroviario":              {"en": "Rail strike",                     "it": "Sciopero ferroviario"},
    "appalti ferroviari":       {"en": "Rail services strike",            "it": "Sciopero appalti ferroviari"},
    "trasporto pubblico locale":{"en": "Local public transport strike",   "it": "Sciopero trasporto pubblico locale"},
    "taxi":                     {"en": "Taxi strike",                     "it": "Sciopero taxi"},
    "marittimo":                {"en": "Ferry/maritime strike",           "it": "Sciopero marittimo"},
    "plurisettoriale":          {"en": "Multi-sector transport strike",   "it": "Sciopero plurisettoriale trasporti"},
    "generale":                 {"en": "General strike",                  "it": "Sciopero generale"},
}

MONTHS_EN = ["", "January", "February", "March", "April", "May", "June",
             "July", "August", "September", "October", "November", "December"]
MONTHS_IT = ["", "gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
             "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"]
DOW_EN = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
DOW_IT = ["Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì", "Sabato", "Domenica"]


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "LeTartarughe-guide/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")


def parse_date(s: str):
    s = (s or "").strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None


FIELD_NAMES = ("Inizio", "Fine", "Data inizio", "Data fine", "Sindacati",
               "Settore", "Categoria", "Modalità", "Rilevanza", "Note",
               "Data proclamazione", "Regione", "Provincia", "Data ricezione")


def field(text: str, name: str) -> str:
    """Extract 'Name: value' — value ends at the next known field name."""
    stop = "|".join(re.escape(f) for f in FIELD_NAMES if f.lower() != name.lower())
    m = re.search(rf"{re.escape(name)}\s*:\s*(.*?)(?=(?:{stop})\s*:|<br|\n|$)",
                  text, re.I | re.S)
    return m.group(1).strip(" -\t") if m else ""


def field_date(text: str, name: str):
    """Extract a dd/mm/yyyy (or yyyy-mm-dd) date right after 'Name:'."""
    m = re.search(rf"{re.escape(name)}\s*:\s*(\d{{2}}/\d{{2}}/\d{{4}}|\d{{4}}-\d{{2}}-\d{{2}})",
                  text, re.I)
    return parse_date(m.group(1)) if m else None


def when_str(d1, d2, hours, lang):
    dow, months = (DOW_IT, MONTHS_IT) if lang == "it" else (DOW_EN, MONTHS_EN)
    def one(d):
        return f"{dow[d.weekday()]} {d.day} {months[d.month]}"
    core = one(d1) if (not d2 or d2 == d1) else f"{one(d1)} → {one(d2)}"
    if hours:
        core += f" · {hours}"
    elif not d2 or d2 == d1:
        core += " · " + ("tutto il giorno" if lang == "it" else "all day")
    return core


def strike_alerts():
    """Parse MIT RSS → list of alert dicts. Fail-safe: returns None on error."""
    try:
        xml_text = fetch(RSS_URL)
        root = ET.fromstring(xml_text)
    except Exception as e:
        print(f"WARN: MIT RSS unavailable ({e}); keeping existing alerts.", file=sys.stderr)
        return None

    today = date.today()
    horizon = today + timedelta(days=LOOKAHEAD_DAYS)
    out = []
    for item in root.iter("item"):
        title = (item.findtext("title") or "")
        desc = re.sub(r"<[^>]+>", " ", item.findtext("description") or "")
        blob = f"{title}  {desc}"

        sector = ""
        for key in SECTORS:
            if re.search(rf"\b{re.escape(key)}\b", blob, re.I):
                sector = key
                break
        if not sector:
            continue

        rilevanza = field(blob, "Rilevanza").lower()
        regione = field(blob, "Regione")
        is_national = "nazional" in rilevanza or sector in ("generale", "plurisettoriale")
        is_local = REGION.lower() in regione.lower() or any(w in blob.lower() for w in CITY_WORDS)
        if not (is_national or is_local):
            continue

        d1 = field_date(blob, "Inizio") or field_date(blob, "Data inizio")
        d2 = field_date(blob, "Fine") or field_date(blob, "Data fine") or d1
        if not d1 or d2 < today or d1 > horizon:
            continue

        hours = ""
        hm = re.search(r"(?:dalle|from)\s*(?:ore\s*)?(\d{1,2}[:.]\d{2})\s*(?:alle|to)\s*(?:ore\s*)?(\d{1,2}[:.]\d{2})", blob, re.I)
        if hm:
            hours = f"{hm.group(1).replace('.', ':')}–{hm.group(2).replace('.', ':')}"

        modal = field(blob, "Modalità")
        scope_en = "national" if is_national else "Rome/Lazio"
        scope_it = "nazionale" if is_national else "Roma/Lazio"
        p_en = f"Scope: {scope_en}." + (f" Details: {modal}." if modal else "") + \
               " Guaranteed-service windows usually apply (~5:30–8:30 and 17:00–20:00 for local transport). Check before travelling."
        p_it = f"Rilevanza: {scope_it}." + (f" Modalità: {modal}." if modal else "") + \
               " Di norma valgono le fasce di garanzia (~5:30–8:30 e 17:00–20:00 per il TPL). Verifica prima di partire."

        out.append({
            "from": d1.isoformat(), "to": d2.isoformat(),
            "when": {"en": when_str(d1, d2, hours, "en"), "it": when_str(d1, d2, hours, "it")},
            "t": SECTORS[sector],
            "p": {"en": p_en, "it": p_it},
            "source": "MIT osservatorio scioperi",
        })

    out.sort(key=lambda x: x["from"])
    # de-duplicate same sector+day
    seen, dedup = set(), []
    for a in out:
        k = (a["t"]["it"], a["from"], a["to"])
        if k not in seen:
            seen.add(k)
            dedup.append(a)
    return dedup


def prune(items, today):
    return [x for x in items if not x.get("to") or x["to"] >= today.isoformat()]


def main():
    data = json.loads(SITE_JSON.read_text(encoding="utf-8"))
    today = date.today()
    before = json.dumps(data, sort_keys=True, ensure_ascii=False)

    fresh = strike_alerts()
    if fresh is not None:
        data["alerts"] = fresh          # alerts are fully machine-owned
    else:
        data["alerts"] = prune(data.get("alerts", []), today)  # keep but prune

    data["free"] = prune(data.get("free", []), today)          # curated, pruned
    data["events"] = prune(data.get("events", []), today)      # curated, pruned

    after = json.dumps(data, sort_keys=True, ensure_ascii=False)
    if before == after:
        print("No changes.")
        return 0

    data["updated"] = today.isoformat()
    SITE_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"events.json updated ({len(data['alerts'])} alerts, "
          f"{len(data['free'])} free, {len(data['events'])} events).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
