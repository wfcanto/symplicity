# -*- coding: utf-8 -*-
"""
Corrige os campos `alum` e `applicantType` de todos os alunos no cache Symplicity.

Regras:
  - Aluno matriculado (mode id == '1')  → alum=0, applicantType=1
  - Sem curso ativo                     → alum=1, applicantType=3
"""

import json
import sqlite3
from datetime import datetime

import pandas as pd

from config import DB_PATH
from symplicity_api import update_student
from utils import is_valid_email


def _is_enrolled(degrees: list) -> bool:
    for degree in degrees:
        if isinstance(degree, dict):
            mode = degree.get("mode")
            if isinstance(mode, dict) and mode.get("id") == "1":
                return True
    return False


def _resolve_email(json_student: dict) -> str:
    school_id = json_student.get("schoolStudentId", "")
    email = json_student.get("email", "")
    if not is_valid_email(email) or email in ("", "nan"):
        return f"{school_id}@maua.br"
    return email


def _current_applicant_type(json_student: dict) -> str:
    data = json_student.get("applicantType", [])
    if isinstance(data, list) and data and isinstance(data[0], dict):
        return data[0].get("id", "")
    return ""


def _needs_update(alum_value, applicant_type_value: str, enrolled: bool) -> bool:
    if alum_value and enrolled:
        return True
    if not alum_value and not enrolled:
        return True
    correctly_matched = (
        (applicant_type_value == "1" and not alum_value) or
        (applicant_type_value == "3" and alum_value)
    )
    return not correctly_matched


def process_student(json_student: dict, log_file: str) -> tuple[int, int, int]:
    """
    Returns (erro_1_inc, erro_2_inc, erro_3_inc) — increments for each counter.
    """
    enrolled = _is_enrolled(json_student.get("degrees", []))
    alum_value = json_student.get("alum")
    applicant_type_value = _current_applicant_type(json_student)
    school_student_id = json_student.get("schoolStudentId")
    email = _resolve_email(json_student)

    alum = "0" if enrolled else "1"
    applicant_type = "1" if enrolled else "3"

    e1 = 1 if (alum_value and enrolled) else 0
    e2 = 1 if (not alum_value and not enrolled) else 0
    e3 = 1 if not _correct_pair(applicant_type_value, alum_value) else 0

    if not _needs_update(alum_value, applicant_type_value, enrolled):
        return 0, 0, 0

    payload = {"email": email, "alum": alum, "applicantType": [applicant_type]}
    result = update_student(school_student_id, payload)

    with open(log_file, "a", encoding="utf-8") as f:
        f.write("Alteração >> --atual--|--correto--\n")
        f.write(f"schoolstudentid: {school_student_id}\n")
        f.write(f"alum: {alum_value} | {alum}\n")
        f.write(f"email: {json_student.get('email')} | {email}\n")
        f.write(f"applicantType: {applicant_type_value} | {applicant_type}\n")
        if result["success"]:
            f.write(f"Sucesso: {result.get('response_text')}\n")
        else:
            f.write(f"Erro >>;{result.get('error')};{result.get('response_text')}\n")
        f.write("\n-----------------------\n")

    return e1, e2, e3


def _correct_pair(applicant_type_value: str, alum_value) -> bool:
    return (applicant_type_value == "1" and not alum_value) or (applicant_type_value == "3" and alum_value)


def main() -> None:
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    log_file = f"log_atz_symplicity_alum{timestamp}.txt"
    open(log_file, "w", encoding="utf-8").close()

    with sqlite3.connect(DB_PATH) as conn:
        df = pd.read_sql_query("SELECT * FROM jsons", conn)

    print(f"Registros no cache: {len(df)}")

    cont_lidos = 0
    cont_alum  = 0
    erro_1 = erro_2 = erro_3 = erro_4 = 0

    for index, row in df.iterrows():
        cont_lidos += 1
        if cont_lidos % 100 == 0:
            print(f"{cont_lidos} registros processados...")

        try:
            json_student = json.loads(row["json"])
        except (json.JSONDecodeError, TypeError) as e:
            print(f"[{index}] Erro ao decodificar JSON: {e}")
            continue

        if json_student.get("accountDisabled"):
            continue

        enrolled = _is_enrolled(json_student.get("degrees", []))
        if not enrolled:
            cont_alum += 1

        e1, e2, e3 = process_student(json_student, log_file)
        erro_1 += e1
        erro_2 += e2
        erro_3 += e3

    print(f"Lidos          >> {cont_lidos}")
    print(f"Alumni         >> {cont_alum}")
    print(f"Matriculados   >> {cont_lidos - cont_alum}")
    print("-----------------------------------------")
    print(f"Erro 1 (alum=1 mas matriculado) >> {erro_1}")
    print(f"Erro 2 (alum=0 mas não matric.) >> {erro_2}")
    print(f"Erro 3 (applicantType incompat.) >> {erro_3}")
    print(f"Erro de atualização API         >> {erro_4}")


if __name__ == "__main__":
    main()
