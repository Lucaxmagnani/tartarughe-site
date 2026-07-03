#!/usr/bin/env python3
"""
Sends OneSignal email + push notifications for NEW transport alerts.

Runs in the GitHub Action right after update_events.py:
  1. compares the previous site/events.json (saved by the workflow as
     /tmp/old_events.json before the update) with the new one;
  2. for every alert that wasn't there before, notifies ONLY the
     subscribers whose stay window overlaps the alert dates
     (OneSignal tag filters on stay_start / stay_end, numeric YYYYMMDD);
  3. guests past their check-out never match the filter — the
     subscription is effectively dead after the stay.

Requires env ONESIGNAL_API_KEY (GitHub secret). Uses stdlib only.
"""

import json
import os
import sys
import urllib.request
from pathlib import Path

APP_ID = "43f7067c-cf52-4270-948b-3d5c8de52713"
API_URL = "https://api.onesignal.com/notifications"
SITE_URL = "https://tartarughe.netlify.app/stay.html"
NEW_JSON = Path(__file__).resolve().parent.parent / "site" / "events.json"
OLD_JSON = Path(os.environ.get("OLD_EVENTS_JSON", "/tmp/old_events.json"))
MAX_SENDS = 10  # safety cap per run


def auth_header(key: str) -> str:
    # new keys (os_v2_...) use "Key", legacy keys use "Basic"
    return f"Key {key}" if key.startswith("os_v2_") else f"Basic {key}"


def post(payload: dict, key: str) -> dict:
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json",
                 "Authorization": auth_header(key)},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def alert_key(a: dict) -> tuple:
    return (a.get("t", {}).get("it", ""), a.get("from", ""), a.get("to", ""))


def stay_filters(a: dict) -> list:
    """Subscribers whose stay overlaps [a.from, a.to]."""
    start = int(a["from"].replace("-", ""))
    end = int(a["to"].replace("-", ""))
    return [
        {"field": "tag", "key": "stay_start", "relation": "<", "value": str(end + 1)},
        {"operator": "AND"},
        {"field": "tag", "key": "stay_end", "relation": ">", "value": str(start - 1)},
    ]


def send_alert(a: dict, key: str):
    t_en, t_it = a["t"]["en"], a["t"]["it"]
    w_en, w_it = a["when"]["en"], a["when"]["it"]
    p_en, p_it = a["p"]["en"], a["p"]["it"]
    filters = stay_filters(a)

    # push (localized automatically by device language)
    push = {
        "app_id": APP_ID,
        "target_channel": "push",
        "headings": {"en": f"⚠️ {t_en}", "it": f"⚠️ {t_it}"},
        "contents": {"en": f"{w_en} — {p_en}", "it": f"{w_it} — {p_it}"},
        "url": SITE_URL,
        "filters": filters,
    }
    # email (bilingual body)
    body = f"""<p><b>⚠️ {t_it}</b><br>{w_it}<br>{p_it}</p>
<hr><p><b>⚠️ {t_en}</b><br>{w_en}<br>{p_en}</p>
<p><a href="{SITE_URL}">Guida / Guest guide — Le Tartarughe</a></p>
<p style="font-size:12px;color:#888">Ricevi questo avviso perché ti sei iscritto agli avvisi
per le date del tuo soggiorno. / You get this because you subscribed to alerts
for your stay dates. [unsubscribe_url]</p>"""
    email = {
        "app_id": APP_ID,
        "target_channel": "email",
        "email_subject": f"⚠️ {t_it} · {w_it} / {t_en}",
        "email_body": body,
        "filters": filters,
    }
    for name, payload in (("push", push), ("email", email)):
        try:
            res = post(payload, key)
            print(f"  {name}: id={res.get('id','-')} recipients~{res.get('recipients','?')}")
        except Exception as e:
            print(f"  {name}: FAILED ({e})", file=sys.stderr)


def main():
    key = os.environ.get("ONESIGNAL_API_KEY", "").strip()
    if not key:
        print("ONESIGNAL_API_KEY not set — skipping notifications.")
        return 0
    if not OLD_JSON.exists():
        print("No previous events.json — skipping (first run).")
        return 0

    old = {alert_key(a) for a in json.loads(OLD_JSON.read_text(encoding="utf-8")).get("alerts", [])}
    new_alerts = [a for a in json.loads(NEW_JSON.read_text(encoding="utf-8")).get("alerts", [])
                  if alert_key(a) not in old]

    if not new_alerts:
        print("No new alerts — nothing to send.")
        return 0
    if len(new_alerts) > MAX_SENDS:
        print(f"{len(new_alerts)} new alerts > cap {MAX_SENDS}; sending first {MAX_SENDS}.")
        new_alerts = new_alerts[:MAX_SENDS]

    for a in new_alerts:
        print(f"New alert: {a['t']['it']} {a['from']}→{a['to']}")
        send_alert(a, key)
    return 0


if __name__ == "__main__":
    sys.exit(main())
