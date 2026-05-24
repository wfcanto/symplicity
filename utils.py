# -*- coding: utf-8 -*-
from datetime import datetime
from email.utils import parseaddr

_DEGREE_MODE_CORRECTIONS = {
    "Interrupção de Matrícula": "Cancelado",
    "Jubilado": "Cancelado",
    "Não Confirmou Matrícula": "Cancelado",
    "Não renovou Matrícula": "Cancelado",
}

_AREA_CONHECIMENTO_CORRECTIONS = {
    "Alimentos": "Engenharia de Alimentos",
    "Ambiental": "Gestão Ambiental",
    "Arquitetura": "Arquitetura e Urbanismo",
    "Ciência de Dados": "Ciência de Dados e Inteligência Artificial",
    "Controle": "Engenharia de Controle e Automação",
    "Energia e Sustentabilidade": "Energias Renováveis e Sustentabilidade",
    "Gestão de Operações: Qualidade & Produtividade, Inovação e S": (
        "Gestão de Operações: Qualidade & Produtividade, Inovação e Sustentabilidade"
    ),
    "Indústria 4.0 e Indústria Digital": "Indústria 4.0",
    "Engenharia Cosmética: Tecnologia, Inovação, Processos e Gest": (
        "Engenharia Cosmética: Tecnologia, Inovação, Processos e Gestão"
    ),
    "Engenharia de Alimentos - Desenvolvimento de Produtos, Proce": (
        "Engenharia de Alimentos - Desenvolvimento de Produtos, Processos e Assuntos Regulatórios"
    ),
    "Engenharia de Soldagem": "Engenharia da Soldagem",
    "Segurança do Trabalho": "Engenharia de Segurança do Trabalho",
    "Habilidades Pessoais e Sociais no Gerenciamento de Projetos na Engenharia": (
        "Gerenciamento de Projetos na Engenharia"
    ),
}

# Subject-area suffixes (from SUBJECT_AREA split on "/") that override AREA_CONHECIMENTO
_SUBJECT_AREA_OVERRIDES = {
    "Relações Internacionais",
    "Economia",
    "Ciência da Computação",
    "Sistemas de Informação",
    "Instalações Prediais: Projetos",
    "Ciências Econômicas",
    "Inteligência Artificial e Ciência de Dados",
}

_GENDER_MAP = {"1": "M", "2": "F", "3": "Not"}


def is_valid_email(email: str) -> bool:
    _, address = parseaddr(email)
    return "@" in address and "." in address.split("@")[-1]


def first_list_item(value, default=""):
    if isinstance(value, list) and value:
        return value[0]
    return default


def proc_cod(label: str, lista: list) -> str | None:
    for item in lista:
        if item["value"].strip() == label.strip():
            return item["id"]
    return None


def proc_label(cod: str, lista: list) -> str | None:
    for item in lista:
        if item["id"] == cod:
            return item["value"]
    return None


def format_date_iso(date_str: str) -> str:
    return datetime.strptime(date_str, "%d/%m/%Y").strftime("%Y-%m-%d")


def resolve_email(email: str, email1: str, ra: str) -> str:
    if is_valid_email(email):
        return email
    if is_valid_email(email1):
        return email1
    return f"{ra}@maua.br"


def resolve_phone(phone: str, phone2: str, phone3: str) -> str:
    return phone or phone2 or phone3


def normalize_degree_mode(mode: str) -> str:
    return _DEGREE_MODE_CORRECTIONS.get(mode, mode)


def normalize_area_conhecimento(area: str, subject_area: str) -> str:
    """Apply known renames then override from subject_area suffix when applicable."""
    area = _AREA_CONHECIMENTO_CORRECTIONS.get(area, area)
    suffix = subject_area.split("/", 1)[1] if "/" in subject_area else ""
    if suffix in _SUBJECT_AREA_OVERRIDES:
        area = suffix
    return area


def fallback_area_from_subject(subject_area: str) -> str:
    """Raw subject-area suffix used when normal lookup fails."""
    suffix = subject_area.split("/", 1)[1] if "/" in subject_area else ""
    if suffix == "Habilidades Pessoais e Sociais no Gerenciamento de Projetos na Engenharia":
        suffix = "Gerenciamento de Projetos na Engenharia"
    return suffix


def gender_from_code(cod: str) -> str:
    return _GENDER_MAP.get(cod, "")
