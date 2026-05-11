import time
import requests

from config import BASE_URL, HEADERS

# NOTION HELPERS [UTILIZING REQUESTS LIBRARY]

def notion_post(endpoint, payload, retries=3):
    for attempt in range(retries):
        response = requests.post(
            f"{BASE_URL}{endpoint}",
            headers=HEADERS,
            json=payload,
        )

        if response.status_code in [200, 201]:
            return response.json()

        print("POST ERROR:", response.status_code)
        print(response.text)

        if attempt < retries - 1:
            print(f"Retrying... Attempt {attempt + 1}/{retries}")
            time.sleep(1)

    print("FAILED FINAL: Request could not be completed.")
    return None


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

def fetch_migrated_pages(database_id):

    payload = {
        "filter": {
            "property": "Migrated",
            "checkbox": {
                "equals": True
            }
        },
        "page_size": 100
    }

    results = notion_post(
        f"/databases/{database_id}/query",
        payload
    )

    if not results:
        return []

    return results.get("results", [])

def delete_page(page_id):

    payload = {
        "archived": True
    }

    return notion_patch(
        f"/pages/{page_id}",
        payload
    )

def uncheck_migrated(page_id):

    payload = {
        "properties": {
            "Migrated": {
                "checkbox": False
            }
        }
    }

    return notion_patch(
        f"/pages/{page_id}",
        payload
    )

    return response.json()
