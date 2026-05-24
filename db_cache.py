# -*- coding: utf-8 -*-
import json
import os
import sqlite3
import pandas as pd
from config import DB_PATH
from symplicity_api import get_all_students


def rebuild_cache(db_path: str = DB_PATH) -> None:
    if os.path.exists(db_path):
        os.remove(db_path)
        print(f"{db_path} removido")

    students = get_all_students()

    rows = [
        {
            "schoolid": s.get("schoolStudentId"),
            "username": s.get("username") or "",
            "fullname": s.get("fullName") or "",
            "email": s.get("email") or "",
            "ult_atz": s.get("lastModified"),
            "alum": s.get("alum"),
            "json": json.dumps(s),
        }
        for s in students
        if not s.get("accountDisabled")
    ]

    df = pd.DataFrame(rows)
    print(f"Registros gravados no cache: {len(df)}")

    with sqlite3.connect(db_path) as conn:
        df.to_sql("jsons", conn, index=False, if_exists="replace")
        conn.execute("CREATE INDEX idx_schoolid ON jsons(schoolid);")
        conn.execute("CREATE INDEX idx_fullname ON jsons(fullname);")
        conn.execute("CREATE INDEX idx_email ON jsons(email);")
        conn.execute("CREATE INDEX idx_username ON jsons(username);")


def student_exists(school_id: str, db_path: str = DB_PATH) -> bool:
    query = "SELECT 1 FROM jsons WHERE schoolid = ? LIMIT 1"
    with sqlite3.connect(db_path) as conn:
        df = pd.read_sql_query(query, conn, params=(school_id,))
    return not df.empty


def lookup_student_json(school_id: str, db_path: str = DB_PATH) -> dict | None:
    query = "SELECT json FROM jsons WHERE schoolid = ?"
    with sqlite3.connect(db_path) as conn:
        df = pd.read_sql_query(query, conn, params=(school_id,))

    if df.empty:
        return None

    try:
        result = json.loads(df.loc[0, "json"])
        return result if isinstance(result, dict) else None
    except json.JSONDecodeError:
        return None
