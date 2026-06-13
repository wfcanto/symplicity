# -*- coding: utf-8 -*-
"""Lista os valores distintos de DEGREE_AWARD na tabela TMP_SYMPLICITY do RM."""
import sys
sys.stdout.reconfigure(encoding="utf-8")
import pyodbc
from config import RM_CONN_STR

try:
    conn = pyodbc.connect(RM_CONN_STR)
except Exception as e:
    print("Erro ao conectar ao RM:", e)
    sys.exit(1)

rows = conn.execute(
    "SELECT DEGREE_AWARD, COUNT(*) AS total "
    "FROM TMP_SYMPLICITY "
    "GROUP BY DEGREE_AWARD "
    "ORDER BY total DESC"
).fetchall()
conn.close()

print("DEGREE_AWARD no RM (valor, contagem):")
for award, total in rows:
    print(f"  {award!r:40} {total}x")
