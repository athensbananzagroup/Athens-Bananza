import sys
from datetime import datetime, timedelta
from notion_api import notion_post
from config import MONDAY_CHECK_DB_ID


# ---------------------------
# Mode handling
# ---------------------------
def get_mode():
    if len(sys.argv) < 2:
        print("Usage: python run_checks.py [monday|tuesday|start]")
        return None

    mode = sys.argv[1].lower()

    if mode not in ["monday", "tuesday", "start"]:
        print("Invalid mode. Use: monday, tuesday, or start")
        return None

    return mode


def get_check_type(mode):
    return {
        "monday": "Monday",
        "tuesday": "Tuesday",
        "start": "Start of Month"
    }[mode]


def get_date(mode):
    today = datetime.today()

    if mode == "monday":
        d = today - timedelta(days=today.weekday())
    elif mode == "tuesday":
        d = today + timedelta((1 - today.weekday()) % 7)
    elif mode == "start":
        d = today.replace(day=1)

    return d.strftime("%Y-%m-%d")


# ---------------------------
# Notion queries
# ---------------------------
def get_templates(check_type):
    payload = {
        "filter": {
            "and": [
                {"property": "Is Template", "checkbox": {"equals": True}},
                {"property": "Check Type", "select": {"equals": check_type}}
            ]
        }
    }

    data = notion_post(f"/databases/{MONDAY_CHECK_DB_ID}/query", payload)
    return data.get("results", []) if data else []


def entry_exists(template, date, check_type):
    props = template["properties"]

    name = "".join([t["plain_text"] for t in props["Name"]["title"]])
    project = props["Project"]["relation"]

    payload = {
        "filter": {
            "and": [
                {"property": "Name", "title": {"equals": name}},
                {"property": "Date", "date": {"equals": date}},
                {
                    "property": "Project",
                    "relation": {"contains": project[0]["id"]} if project else {}
                },
                {"property": "Check Type", "select": {"equals": check_type}},
                {"property": "Is Template", "checkbox": {"equals": False}}
            ]
        }
    }

    data = notion_post(f"/databases/{MONDAY_CHECK_DB_ID}/query", payload)
    return len(data.get("results", [])) > 0 if data else False


# ---------------------------
# Entry creation
# ---------------------------
def create_entry(template, date, check_type):
    props = template["properties"]

    name = "".join([t["plain_text"] for t in props["Name"]["title"]])

    if entry_exists(template, date, check_type):
        print(f"  — Skipping duplicate: {name}")
        return

    payload = {
        "parent": {"database_id": MONDAY_CHECK_DB_ID},
        "properties": {
            # Required fields
            "Name": {
                "title": [{"text": {"content": name}}]
            },
            "Project": props["Project"],
            "Date": {"date": {"start": date}},
            "Is Template": {"checkbox": False},
            "Check Type": {"select": {"name": check_type}},

            # ✅ Now just COPY from template
            "Employee dashboards": props["Employee dashboards"],
            "Status": props["Status"],
            "Reviewed": props["Reviewed"]
        }
    }

    notion_post("/pages", payload)
    print(f"  ✓ Created: {name}")


# ---------------------------
# Main
# ---------------------------
def run():
    mode = get_mode()
    if not mode:
        return

    check_type = get_check_type(mode)
    date = get_date(mode)

    print(f"\nRunning {check_type} checks for {date}\n")

    templates = get_templates(check_type)

    if not templates:
        print(f"No {check_type} templates found.")
        return

    for t in templates:
        create_entry(t, date, check_type)

    print(f"\n{check_type} entries created.")


if __name__ == "__main__":
    run()
