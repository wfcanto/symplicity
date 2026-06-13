# -*- coding: utf-8 -*-
"""Inspeciona awards usados nos degrees do cache jsons.db"""
import json
import sqlite3
from config import DB_PATH

with sqlite3.connect(DB_PATH) as conn:
    rows = conn.execute("SELECT json FROM jsons LIMIT 200").fetchall()

awards_found = {}
for (raw,) in rows:
    try:
        student = json.loads(raw)
    except Exception:
        continue
    for deg in student.get("degrees") or []:
        if deg and deg.get("award"):
            award = deg["award"]
            key = (award.get("id"), award.get("value"))
            awards_found[key] = awards_found.get(key, 0) + 1

print("Awards encontrados no cache (id, value): contagem")
for (aid, aval), count in sorted(awards_found.items(), key=lambda x: -x[1]):
    print(f"  id={aid!r:10} value={aval!r} ({count}x)")
