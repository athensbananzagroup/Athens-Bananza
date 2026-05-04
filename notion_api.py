import time
import requests

from config import BASE_URL, HEADERS

# NOTION HELPERS [UTILIZING REQUESTS LIBRARY]

def notion_post(path: str, payload: dict) -> dict:
    if path == "/pages":
        return client.pages.create(**payload)
    elif "/query" in path:
        db_id = path.split("/databases/")[-1].split("/query")[0]
        return client.databases.query(
            database_id=db_id,
            filter=payload.get("filter"),
            page_size=payload.get("page_size", 100),
            start_cursor=payload.get("start_cursor"),
        )
    return {}


def notion_patch(endpoint, payload):
    response = requests.patch(
        f"{BASE_URL}{endpoint}",
        headers=HEADERS,
        json=payload,
    )

    if response.status_code not in [200, 201]:
        print("PATCH ERROR:", response.status_code)
        print(response.text)
        return None

    return response.json()
