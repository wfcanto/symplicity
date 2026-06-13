# -*- coding: utf-8 -*-
"""Busca o picklist de award direto da API do Symplicity."""
from symplicity_api import get_picklist

awards = get_picklist("students", "award")
print("Award picklist completo:")
for item in awards:
    print(f"  id={item.get('id')!r:6} value={item.get('value')!r}")
