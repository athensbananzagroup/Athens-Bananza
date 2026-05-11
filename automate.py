import os
import time
import requests
from datetime import datetime, timedelta

NOTION_TOKEN = os.getenv("NOTION_TOKEN")
MONDAY_CHECK_DB_ID = "31bcc2a6c00c80d49256cf371e364a26"


BASE_URL = "https://api.notion.com/v1"
HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28",
}


def notion_post(endpoint, payload, retries=3):
    for attempt in range(retries):
        response = requests.post(f"{BASE_URL}{endpoint}", headers=HEADERS, json=payload)
        if response.status_code in [200, 201]:
            return response.json()
        if attempt < retries - 1:
            time.sleep(1)
        else:
            print(f"POST ERROR {response.status_code}: {response.text}")
    return None


def get_date(mode):
    today = datetime.today()
    if mode == "monday":
        return (today - timedelta(days=today.weekday())).strftime("%Y-%m-%d")
    elif mode == "tuesday":
        return (today + timedelta((1 - today.weekday()) % 7)).strftime("%Y-%m-%d")
    elif mode == "start":
        return today.replace(day=1).strftime("%Y-%m-%d")


def get_check_type(mode):
    return {"monday": "Monday", "tuesday": "Tuesday", "start": "Start of Month"}[mode]


def get_templates(check_type):
    data = notion_post(f"/databases/{MONDAY_CHECK_DB_ID}/query", {
        "filter": {
            "and": [
                {"property": "Is Template", "checkbox": {"equals": True}},
                {"property": "Check Type", "select": {"equals": check_type}},
            ]
        }
    })
    return data.get("results", []) if data else []


def entry_exists(template, date, check_type):
    props = template["properties"]
    name = "".join([t["plain_text"] for t in props["Name"]["title"]])
    project = props["Project"]["relation"]

    data = notion_post(f"/databases/{MONDAY_CHECK_DB_ID}/query", {
        "filter": {
            "and": [
                {"property": "Name", "title": {"equals": name}},
                {"property": "Date", "date": {"equals": date}},
                {"property": "Project", "relation": {"contains": project[0]["id"]} if project else {}},
                {"property": "Check Type", "select": {"equals": check_type}},
                {"property": "Is Template", "checkbox": {"equals": False}},
            ]
        }
    })
    return len(data.get("results", [])) > 0 if data else False


def create_entry(template, date, check_type):
    props = template["properties"]
    name = "".join([t["plain_text"] for t in props["Name"]["title"]])

    if entry_exists(template, date, check_type):
        return "skipped"

    notion_post("/pages", {
        "parent": {"database_id": MONDAY_CHECK_DB_ID},
        "properties": {
            "Name": {"title": [{"text": {"content": name}}]},
            "Project": props["Project"],
            "Date": {"date": {"start": date}},
            "Is Template": {"checkbox": False},
            "Check Type": {"select": {"name": check_type}},
            "Employee dashboards": props["Employee dashboards"],
            "Status": props["Status"],
            "Reviewed": props["Reviewed"],
        },
    })
    return "created"


if __name__ == "__main__":
    # Determines which check type runs based on today
    today = datetime.today().weekday()  # 0=Mon, 1=Tue
    
    if today == 0:
        mode = "monday"
    elif today == 1:
        mode = "tuesday"
    else:
        mode = "monday"  # fallback for manual triggers

    check_type = get_check_type(mode)
    date = get_date(mode)

    print(f"Running {check_type} checks for {date}")

    templates = get_templates(check_type)
    print(f"Found {len(templates)} templates")

    created, skipped = 0, 0
    for t in templates:
        result = create_entry(t, date, check_type)
        if result == "created":
            created += 1
        else:
            skipped += 1

    print(f"Done. Created {created}, skipped {skipped}.")
