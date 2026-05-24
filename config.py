# -*- coding: utf-8 -*-
import os
from dotenv import load_dotenv

load_dotenv()

SYMPLICITY_TOKEN  = os.environ["SYMPLICITY_TOKEN"]
SYMPLICITY_COOKIE = os.environ["SYMPLICITY_COOKIE"]
SYMPLICITY_BASE_URL = "https://maua-csm.symplicity.com/api/public/v1"

HTTP_HEADERS = {
    "Content-Type": "application/json; charset=UTF-8",
    "Authorization": f"Token {SYMPLICITY_TOKEN}",
    "Cookie": SYMPLICITY_COOKIE,
}

DB_PATH = "jsons.db"

RM_CONN_STR = (
    "DRIVER={ODBC Driver 18 for SQL Server};"
    "SERVER=10.64.0.55;"
    "DATABASE=CORPORERM;"
    "Trusted_Connection=yes;"
    "TrustServerCertificate=yes;"
)
