import time
import requests

from config import BASE_URL, HEADERS

# NOTION HELPERS [UTILIZING REQUESTS LIBRARY]

def notion_post(path: str, payload: dict) -> dict:
    if path == "/pages":
        return client.pages.create(**payload)
    elif "/query" in path:
        db_id = path.split("/databases/")[-1].split("/query")[0]
        filter_val = payload.pop("filter", None)
        kwargs = {**payload}
        if filter_val is not None:
            kwargs["filter"] = filter_val
        return client.databases.query(database_id=db_id, **kwargs)
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
