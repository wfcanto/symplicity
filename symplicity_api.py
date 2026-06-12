# -*- coding: utf-8 -*-
import json
import time
import requests
from config import HTTP_HEADERS, SYMPLICITY_BASE_URL


def get_picklist(entity: str, field: str, **params) -> list:
    url = f"{SYMPLICITY_BASE_URL}/picklists/{entity}/{field}"
    response = requests.get(url, headers=HTTP_HEADERS, params=params)
    response.raise_for_status()
    return response.json()


def get_all_students(per_page: int = 500) -> list[dict]:
    url = f"{SYMPLICITY_BASE_URL}/students?keywords=&page=1&perPage=1&customFields=1"
    first_resp = requests.get(url, headers=HTTP_HEADERS)
    first_resp.raise_for_status()
    first = first_resp.json()
    total = first.get("total", 0)

    if total == 0:
        raise RuntimeError(
            f"API retornou total=0 ao buscar alunos. "
            f"Verifique token/cookie. Resposta: {first}"
        )

    total_pages = (total + per_page - 1) // per_page

    print(f"Total no Symplicity: {total} | Páginas: {total_pages}")

    students = []
    for page in range(1, total_pages + 1):
        print(f"Extraindo página {page}/{total_pages}")
        page_url = f"{SYMPLICITY_BASE_URL}/students?keywords=&page={page}&perPage={per_page}&customFields=1"
        page_resp = requests.get(page_url, headers=HTTP_HEADERS)
        page_resp.raise_for_status()
        data = page_resp.json()
        students.extend(data.get("models", []))
        time.sleep(1)

    return students


def _put(url: str, payload: dict) -> dict:
    try:
        response = requests.put(
            url,
            headers=HTTP_HEADERS,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            timeout=10,
        )
        response.raise_for_status()
        return {"success": True, "status_code": response.status_code, "response_text": response.text}
    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "error": str(e),
            "status_code": getattr(e.response, "status_code", "N/A"),
            "response_text": getattr(e.response, "text", "Sem resposta"),
        }


def update_student(school_student_id: str, payload: dict) -> dict:
    url = f"{SYMPLICITY_BASE_URL}/students/schoolStudentId/{school_student_id}"
    return _put(url, payload)


def create_student(payload: dict) -> dict:
    # Symplicity API uses PUT on the collection endpoint for creation
    return _put(f"{SYMPLICITY_BASE_URL}/students", payload)


def _mock_result(school_student_id: str) -> dict:
    return {"success": True, "status_code": "999", "response_text": "teste", "school_student_id": school_student_id}
