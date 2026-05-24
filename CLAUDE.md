# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Python integration that syncs student data from **TOTVS RM** (ERP/SQL Server) to **Symplicity CSM** (Career Services platform).

## Running the Scripts

```bash
# 1. Full student sync (RM → Symplicity)
python atz_symplicity_v3_1.py

# 2. Alumni status correction (runs after step 1)
python atz_symplicity_alum.py
```

Both scripts generate timestamped log files in the working directory:
- `log_atz_symplicity_{timestamp}.txt` — detailed operation log
- `log_erro_symplicity_{timestamp}.txt` — error summary (CSV-style)
- `log_atz_symplicity_alum{timestamp}.txt` — alumni correction log

## Module Structure

| File | Purpose |
|------|---------|
| `config.py` | API token, cookie, base URL, SQLite path, SQL Server connection string |
| `utils.py` | Shared pure functions: email/phone resolution, picklist lookup, date formatting, AREA_CONHECIMENTO normalization |
| `symplicity_api.py` | All HTTP calls to the Symplicity REST API |
| `db_cache.py` | SQLite cache: rebuild, lookup, existence check |
| `atz_symplicity_v3_1.py` | Main sync: loads picklists, rebuilds cache, reads RM, creates/updates student records |
| `atz_symplicity_alum.py` | Fixes `alum` flag and `applicantType` for all students in the cache |

## Architecture & Data Flow (`atz_symplicity_v3_1.py`)

1. `load_picklists()` — fetches all Symplicity code tables (mode, majors, minors, award, schools, gender, applicantType, state, country, certificates)
2. `rebuild_cache()` — downloads every active Symplicity student and stores them in `jsons.db` (SQLite)
3. `load_rm_data()` — executes `sp_GerarTabSymplicity` on SQL Server, deduplicates by `(SCHOOLSTUDENTID, PROGRAM)` keeping the most recent enrolment
4. **Per-row loop** — for each RM student:
   - `process_rm_row()` normalizes all fields and resolves picklist codes → student dict
   - If not in cache → `atz_new_json()` creates full record
   - If in cache → `transform_to_payload()` + `atz_existing_json()` updates/appends the matching degree

## Key Business Logic

- **Student matching**: by `schoolStudentId` (CPF or RA)
- **Degree matching**: by `type` field (= `PROGRAM` from RM)
- **Degree mode mapping**: RM status → Symplicity code via `normalize_degree_mode()` — statuses "Interrupção de Matrícula", "Jubilado", etc. map to "Cancelado"
- **Graduated protection**: `atz_existing_json()` skips any degree already at mode `'5'` (Formado)
- **AREA_CONHECIMENTO normalization**: three-step process in `_resolve_codes()` with two fallback attempts; dict-driven renames in `utils.py`
- **Alumni logic** (`atz_symplicity_alum.py`): `alum=1` + `applicantType=3` when no degree with mode `'1'`; `alum=0` + `applicantType=1` when enrolled

## Test Mode

Set `test_mode = True` in `main()` of `atz_symplicity_v3_1.py` to run the full logic without writing to the Symplicity API (returns mock responses).

## SQLite Cache (`jsons.db`)

```
Table: jsons
  schoolid, username, fullname, email, ult_atz, alum
  json  -- full Symplicity student JSON
Indexes: idx_schoolid, idx_fullname, idx_email, idx_username
```

## Credentials (Security Note)

All credentials are currently hardcoded in `config.py`:
- `SYMPLICITY_TOKEN` — API bearer token
- `SYMPLICITY_COOKIE` — AWS load-balancer session cookie
- `RM_CONN_STR` — SQL Server connection (Windows auth, no password)

Move to environment variables + `python-dotenv` before any public sharing.

## Dependencies

```
pyodbc    # SQL Server (requires ODBC Driver 18 on host)
pandas    # DataFrame operations
requests  # HTTP calls to Symplicity
sqlite3   # stdlib — local cache
```

No `requirements.txt` exists. Install: `pip install pyodbc pandas requests`.

## Symplicity API

Base URL: `https://maua-csm.symplicity.com/api/public/v1/`  
All writes use `PUT` (Symplicity uses PUT for both update and create).
