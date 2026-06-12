# -*- coding: utf-8 -*-
"""
Integração TOTVS RM x Symplicity

Documentação da API do Symplicity disponível em:
https://www.symplicity.com/developer/csm/api-documentation
https://www.symplicity.com/developer/csm/getting-started

@author: wagner.canto
"""

import json
import sqlite3
import sys
from datetime import datetime

import pandas as pd
import pyodbc

from config import DB_PATH, RM_CONN_STR
from db_cache import lookup_student_json, rebuild_cache, student_exists
from symplicity_api import (
    _mock_result,
    create_student,
    get_picklist,
    update_student,
)
from utils import (
    fallback_area_from_subject,
    first_list_item,
    format_date_iso,
    gender_from_code,
    normalize_area_conhecimento,
    normalize_degree_mode,
    proc_cod,
    proc_label,
    resolve_email,
    resolve_phone,
)

# ---------------------------------------------------------------------------
# Picklist loading
# ---------------------------------------------------------------------------

def load_picklists() -> dict:
    print("Carregando picklists do Symplicity...")
    return {
        "mode":          get_picklist("students", "mode"),
        "minors":        get_picklist("students", "minors"),
        "award":         get_picklist("students", "award"),
        "schools":       get_picklist("students", "schools"),
        "majors":        get_picklist("students", "majors"),
        "new_gender":    get_picklist("students", "new_gender"),
        "gender":        get_picklist("students", "gender"),
        "applicantType": get_picklist("students", "applicantType"),
        "certificates":  get_picklist("students", "certificates"),
        "state":         get_picklist("addresses", "state", country="BR"),
        "country":       get_picklist("addresses", "country"),
    }


# ---------------------------------------------------------------------------
# TOTVS RM data loading
# ---------------------------------------------------------------------------

def load_rm_data() -> pd.DataFrame:
    try:
        conn = pyodbc.connect(RM_CONN_STR)
    except Exception as e:
        print("Erro ao conectar ao banco de dados:", e)
        sys.exit(1)

    try:
        print("Gerando tabela TMP_SYMPLICITY no TOTVS RM...")
        ret = pd.read_sql("EXEC dbo.sp_GerarTabSymplicity", conn)
        del ret
    except Exception as e:
        print("Erro ao executar sp_GerarTabSymplicity:", e)
        conn.close()
        sys.exit(1)

    try:
        print("Extraindo TMP_SYMPLICITY...")
        query = """
        WITH RegistrosRankeados AS (
            SELECT *,
                   ROW_NUMBER() OVER (
                       PARTITION BY SCHOOLSTUDENTID, PROGRAM
                       ORDER BY DTMATRICULA DESC
                   ) AS rn
            FROM TMP_SYMPLICITY
        )
        SELECT * FROM RegistrosRankeados WHERE rn = 1
        ORDER BY SCHOOLSTUDENTID, PROGRAM;
        """
        df = pd.read_sql(query, conn)
    except Exception as e:
        print("Erro ao extrair TMP_SYMPLICITY:", e)
        conn.close()
        sys.exit(1)

    conn.close()
    print(f"Registros extraídos: {len(df)}")
    return df


# ---------------------------------------------------------------------------
# Row processing
# ---------------------------------------------------------------------------

def _resolve_codes(area: str, subject_area: str, picklists: dict, school_student_id: str) -> tuple:
    """
    Returns (final_area, cod_majors, cod_cert).
    Mirrors the original three-attempt cert lookup and two-attempt majors fallback.
    """
    # Cert attempt 1 — with raw area, BEFORE corrections (matches original behavior)
    cod_cert = (
        proc_cod(area, picklists["certificates"]) or
        proc_cod(area.upper(), picklists["certificates"])
    )

    area = normalize_area_conhecimento(area, subject_area)

    # Majors first try
    cod_majors = (
        proc_cod(area, picklists["majors"]) or
        proc_cod(area.upper(), picklists["majors"])
    )

    # Cert attempt 2
    if not cod_cert:
        cod_cert = (
            proc_cod(area, picklists["certificates"]) or
            proc_cod(area.upper(), picklists["certificates"])
        )

    # Majors fallback — reset area to raw subject suffix
    if not cod_majors:
        area = fallback_area_from_subject(subject_area)
        cod_majors = (
            proc_cod(area, picklists["majors"]) or
            proc_cod(area.upper(), picklists["majors"])
        )

    # Cert attempt 3 — with potentially updated area
    if not cod_cert:
        cod_cert = (
            proc_cod(area, picklists["certificates"]) or
            proc_cod(area.upper(), picklists["certificates"])
        )

    if not cod_majors:
        print(f"AREA_CONHECIMENTO/MAJORS NÃO ENCONTRADA >> {area} | {school_student_id}")
        cod_majors = ""
    if not cod_cert:
        print(f"AREA_CONHECIMENTO/CERTIFICATES NÃO ENCONTRADA >> {area} | {school_student_id}")
        cod_cert = ""

    return area, cod_majors, cod_cert


def process_rm_row(row: pd.Series, picklists: dict) -> dict:
    """Convert a raw RM row into a fully resolved student dict."""
    school_student_id = row["SCHOOLSTUDENTID"].strip()
    ra = row["RA"].strip()

    email = resolve_email(
        str(row["EMAIL"]).strip(),
        str(row["EMAIL1"]).strip() if pd.notna(row["EMAIL1"]) else "",
        ra,
    )
    phone = resolve_phone(
        str(row["PHONE"]).strip() if pd.notna(row["PHONE"]) else "",
        str(row["PHONE2"]).strip() if pd.notna(row["PHONE2"]) else "",
        str(row["PHONE3"]).strip() if pd.notna(row["PHONE3"]) else "",
    )

    degree_mode = normalize_degree_mode(row["DEGREE_MODE"].strip())

    rua = row["SCHOOL_ADDRESS_RUA"].strip()
    bairro = row["SCHOOL_ADDRESS_BAIRRO"].strip()

    area_raw = row["AREA_CONHECIMENTO"].strip()
    subject_area = row["SUBJECT_AREA"].strip()
    area, cod_majors, cod_cert = _resolve_codes(area_raw, subject_area, picklists, school_student_id)

    cod_mode = proc_cod(degree_mode, picklists["mode"])
    if cod_mode is None:
        print(f"DEGREE_MODE NÃO ENCONTRADO >> {degree_mode} | {school_student_id} | {row['FULLNAME'].strip()}")

    cod_minors = proc_cod(row["MINOR"].strip(), picklists["minors"]) or ""
    if not cod_minors:
        print(f"MINOR NÃO ENCONTRADO >> {row['MINOR'].strip()} | {school_student_id}")

    cod_award = proc_cod(row["DEGREE_AWARD"].strip(), picklists["award"])
    if cod_award is None:
        print(f"DEGREE_AWARD NÃO ENCONTRADO >> {row['DEGREE_AWARD'].strip()} | {school_student_id}")

    cod_schools = proc_cod(row["SCHOOL"].strip(), picklists["schools"])
    if cod_schools is None:
        print(f"SCHOOL NÃO ENCONTRADO >> {row['SCHOOL'].strip()} | {school_student_id}")

    cod_new_gender = proc_cod(row["NEW_GENDER"].strip(), picklists["new_gender"])

    return {
        "school_student_id": school_student_id,
        "ra": ra,
        "username": row["USERNAME"].strip(),
        "email": email,
        "firstname": row["FIRSTNAME"].strip(),
        "lastname": row["LASTNAME"].strip(),
        "fullname": row["FULLNAME"].strip(),
        "cpf": row["CPF_ALUNO"].strip(),
        "phone": phone,
        "birthdate": format_date_iso(row["BIRTHDATE"].strip()),
        "new_gender": row["NEW_GENDER"].strip(),
        "gender": gender_from_code(cod_new_gender or ""),
        "nome_social": str(row["NOMESOCIAL"]).strip() if pd.notna(row["NOMESOCIAL"]) else "",
        "alum": row["ALUM"].strip(),
        "applicant_type": row["APPLICANT_TYPE"].strip(),
        "street": f"{rua} - {bairro}",
        "city": row["SCHOOL_ADDRESS_CIDADE"].strip(),
        "zip": row["SCHOOL_ADDRESS_CEP"].strip(),
        "state": row["SCHOOL_ADDRESS_ESTADO"].strip(),
        "country": row["SCHOOL_ADDRESS_PAIS"].strip(),
        "visual_id": row["VISUAL_ID"].strip(),
        "program": row["PROGRAM"].strip(),
        "degree_mode": degree_mode,
        "minor": row["MINOR"].strip(),
        "school": row["SCHOOL"].strip(),
        "degree_award": row["DEGREE_AWARD"].strip(),
        "area_conhecimento": area,
        "degree_grad_date": format_date_iso(row["DEGREE_GRAD_DATE"].strip()),
        "cod_mode": cod_mode,
        "cod_minors": cod_minors,
        "cod_award": cod_award,
        "cod_schools": cod_schools,
        "cod_cert": cod_cert,
        "cod_majors": cod_majors,
        "cod_new_gender": cod_new_gender,
        "cod_applicant_type": proc_cod(row["APPLICANT_TYPE"].strip(), picklists["applicantType"]),
        "cod_state": proc_cod(row["SCHOOL_ADDRESS_ESTADO"].strip(), picklists["state"]),
        "cod_country": proc_cod(row["SCHOOL_ADDRESS_PAIS"].strip(), picklists["country"]),
    }


# ---------------------------------------------------------------------------
# Payload builders
# ---------------------------------------------------------------------------

def transform_to_payload(existing_json: dict) -> dict:
    """Extract the degrees structure from a Symplicity student JSON into API payload format."""
    payload = {"degrees": []}
    for deg in existing_json.get("degrees", []) or []:
        if deg is None:
            continue
        payload["degrees"].append({
            "visualId":       deg.get("visualId", ""),
            "primary":        "1" if deg.get("primary") else "0",
            "schools":        [s["id"] for s in (deg.get("schools") or [])],
            "award":          (deg.get("award") or {}).get("id", ""),
            "type":           deg.get("type", ""),
            "mode":           (deg.get("mode") or {}).get("id", ""),
            "majors":         [m["id"] for m in (deg.get("majors") or [])],
            "minors":         [m["id"] for m in (deg.get("minors") or [])],
            "graduationDate": deg.get("graduationDate") or "",
            "campus":         "",
        })
    return payload


def _build_degree_entry(student: dict, primary: str = "0") -> dict:
    return {
        "visualId":       student["visual_id"],
        "primary":        primary,
        "schools":        [student["cod_schools"]],
        "award":          student["cod_award"],
        "type":           student["program"],
        "mode":           student["cod_mode"],
        "majors":         [student["cod_majors"]] if student["cod_majors"] else [],
        "minors":         [student["cod_minors"]] if student["cod_minors"] else [],
        "graduationDate": student["degree_grad_date"],
        "campus":         "",
    }


# ---------------------------------------------------------------------------
# Symplicity update helpers
# ---------------------------------------------------------------------------

def _call_api(op: str, student: dict, payload: dict, test_mode: bool) -> dict:
    if test_mode:
        return _mock_result(student["school_student_id"])
    if op == "upd":
        return update_student(student["school_student_id"], payload)
    return create_student(payload)


def _log_degree_change(f, label: str, student: dict, degree_type: str, result: dict, payload: dict,
                       existing_mode=None, existing_majors=None, existing_minors=None, existing_grad=None):
    f.write(f"{label} >> --RM--|--Symplicity--\n")
    f.write(f"schoolstudentid: {student['school_student_id']} | {student['email']}\n")
    f.write(f"TYPE: {student['program']} | {degree_type}\n")
    if existing_majors is not None:
        f.write(f"MAJORS: {student['cod_majors']}-{student['area_conhecimento']} | {existing_majors}\n")
        f.write(f"MODE: {student['cod_mode']} | {existing_mode}\n")
        f.write(f"MINOR: {student['cod_minors']} | {existing_minors}\n")
        f.write(f"DEGREE_GRAD_DATE: {student['degree_grad_date']} | {existing_grad}\n")
    else:
        f.write(f"MAJORS: {student['cod_majors']} - {student['area_conhecimento']}\n")
        f.write(f"MODE: {student['cod_mode']} - {student['degree_mode']}\n")
        f.write(f"MINOR: {student['cod_minors']} - {student['minor']}\n")
        f.write(f"AWARD: {student['cod_award']} - {student['degree_award']}\n")
        f.write(f"DEGREE_GRAD_DATE: {student['degree_grad_date']}\n")
    if result["success"]:
        f.write(f"Sucesso: {result.get('response_text')}\n")
    else:
        f.write(f"Erro: {result.get('error')} | {result.get('response_text')}\n")
        f.write(json.dumps(payload, ensure_ascii=False, indent=2))
    f.write("\n-----------------------\n")


def atz_existing_json(
    payload: dict,
    student: dict,
    picklists: dict,
    log_atz: str,
    log_erro: str,
    test_mode: bool,
) -> bool:
    alterou = False
    achou_ra = False

    for degree in payload.get("degrees", []):
        if degree.get("type", "").strip() != student["program"]:
            continue

        achou_ra = True

        existing_mode   = degree.get("mode")
        existing_majors = first_list_item(degree.get("majors"))
        existing_minors = first_list_item(degree.get("minors"))
        existing_grad   = (degree.get("graduationDate") or "").strip()
        majors_label    = proc_label(existing_majors, picklists["majors"]) if existing_majors else ""

        # Skip if already graduated
        if existing_mode == "5":
            break

        changed = (
            student["cod_mode"] != existing_mode or
            (student["cod_majors"] != "" and student["cod_majors"] != existing_majors) or
            student["cod_minors"] != existing_minors or
            student["degree_grad_date"] != existing_grad
        )
        if not changed:
            break

        degree["mode"]           = student["cod_mode"]
        degree["majors"]         = [student["cod_majors"]] if student["cod_majors"] else []
        degree["minors"]         = [student["cod_minors"]] if student["cod_minors"] else []
        degree["graduationDate"] = student["degree_grad_date"]

        result = _call_api("upd", student, payload, test_mode)
        alterou = True

        with open(log_atz, "a", encoding="utf-8") as f:
            _log_degree_change(f, "Alteração Degree", student, degree["type"], result, payload,
                               existing_mode, existing_majors, existing_minors, existing_grad)

        if not result["success"]:
            with open(log_erro, "a", encoding="utf-8") as f:
                f.write(
                    f"Erro Alteração Degree >>;{student['school_student_id']};{student['ra']};"
                    f"{student['fullname']};{result.get('error')};{result.get('response_text')}\n"
                )

    if not achou_ra and not alterou and student["degree_mode"] in ("Formado", "Matriculado"):
        payload["degrees"].append(_build_degree_entry(student, primary="0"))
        result = _call_api("upd", student, payload, test_mode)
        alterou = True

        with open(log_atz, "a", encoding="utf-8") as f:
            _log_degree_change(f, "Inclusão Degree", student, student["program"], result, payload)

        if not result["success"]:
            with open(log_erro, "a", encoding="utf-8") as f:
                f.write(
                    f"Erro Inclusão Degree >>;{student['school_student_id']};{student['ra']};"
                    f"{student['fullname']};{result.get('error')};{result.get('response_text')}\n"
                )

    return alterou


def atz_new_json(student: dict, log_atz: str, log_erro: str, test_mode: bool) -> bool:
    alum = "1" if student["degree_mode"] == "Formado" else "0"

    payload = {
        "schoolStudentId": student["school_student_id"],
        "firstName":       student["firstname"],
        "lastName":        student["lastname"],
        "fullName":        student["fullname"],
        "username":        student["username"],
        "email":           student["email"],
        "phone":           student["phone"],
        "birthdate":       student["birthdate"],
        "applicantType":   [student["cod_applicant_type"]],
        "new_gender":      [student["cod_new_gender"]],
        "gender":          student["gender"],
        "nome_social":     student["nome_social"],
        "rg":              "",
        "cpf_aluno":       student["cpf"],
        "certificates":    [student["cod_cert"]],
        "alum":            alum,
        "address": {
            "street":  student["street"],
            "city":    student["city"],
            "zip":     student["zip"],
            "state":   student["cod_state"],
            "country": student["cod_country"],
        },
        "degrees": [_build_degree_entry(student, primary="1")],
    }

    result = _call_api("add", student, payload, test_mode)
    incluiu = result["success"]

    with open(log_atz, "a", encoding="utf-8") as f:
        _log_degree_change(f, "Inclusão completa", student, student["program"], result, payload)

    if not result["success"]:
        with open(log_erro, "a", encoding="utf-8") as f:
            f.write(
                f"Inclusão completa >>;{student['school_student_id']};{student['ra']};"
                f"{student['fullname']};{result.get('error')};{result.get('response_text')}\n"
            )

    return incluiu


# ---------------------------------------------------------------------------
# Main processing loop
# ---------------------------------------------------------------------------

def process_students(
    df: pd.DataFrame,
    picklists: dict,
    log_atz: str,
    log_erro: str,
    test_mode: bool,
) -> dict:
    counters = {"achou": 0, "nao_achou": 0, "alterou": 0, "incluiu": 0}

    for _, row in df.iterrows():
        student = process_rm_row(row, picklists)

        if not student_exists(student["school_student_id"]):
            if student["degree_mode"] in ("Formado", "Matriculado"):
                counters["nao_achou"] += 1
                if atz_new_json(student, log_atz, log_erro, test_mode):
                    counters["incluiu"] += 1
            continue

        existing_json = lookup_student_json(student["school_student_id"])
        if existing_json is None:
            with open(log_atz, "a", encoding="utf-8") as f:
                f.write(
                    f"JSON não encontrado >> {student['school_student_id']} | "
                    f"{student['fullname']} | {student['email']}\n"
                    "-------------------------------------------------------------------\n"
                )
            continue

        counters["achou"] += 1
        payload = transform_to_payload(existing_json)
        if atz_existing_json(payload, student, picklists, log_atz, log_erro, test_mode):
            counters["alterou"] += 1

    return counters


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    test_mode = False  # True = não grava no Symplicity

    picklists = load_picklists()

    rebuild_cache(DB_PATH)

    with sqlite3.connect(DB_PATH) as _conn:
        cache_count = _conn.execute("SELECT COUNT(*) FROM jsons").fetchone()[0]
    print(f"Cache verificado: {cache_count} registros.")
    if cache_count < 1000:
        print(
            f"ABORTANDO: cache com apenas {cache_count} registros. "
            "Isso indica falha na extração do Symplicity. "
            "Verifique token/cookie antes de prosseguir."
        )
        sys.exit(1)

    df = load_rm_data()

    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    log_atz  = f"log_atz_symplicity_{timestamp}.txt"
    log_erro = f"log_erro_symplicity_{timestamp}.txt"
    open(log_atz,  "w", encoding="utf-8").close()
    open(log_erro, "w", encoding="utf-8").close()

    counters = process_students(df, picklists, log_atz, log_erro, test_mode)

    print("-------------------------------------------")
    print(f"Achou no Symplicity        >> {counters['achou']}")
    print(f"Não achou no Symplicity    >> {counters['nao_achou']}")
    print(f"Alterou / incluiu degree   >> {counters['alterou']}")
    print(f"Incluiu novo registro      >> {counters['incluiu']}")


if __name__ == "__main__":
    main()
