from notion_api import notion_get, notion_post
from config import MONDAY_CHECK_DB_ID

import re

def extract_page_id(url):
    url = url.split("?")[0]
    match = re.search(r"([a-f0-9]{32})$", url)
    return match.group(1) if match else None

def get_project(page_id):
    return notion_get(f"/pages/{page_id}")


def get_work_points_by_type(project):
    props = project.get("properties", {})

    return {
        "Monday": [i["name"] for i in props.get("Monday Checks", {}).get("multi_select", [])],
        "Tuesday": [i["name"] for i in props.get("Tuesday Checks", {}).get("multi_select", [])],
        "Start of Month": [i["name"] for i in props.get("Start of Month Checks", {}).get("multi_select", [])],
    }


def create_template(project_id, work_point, check_type, employee_dashboards):
    if template_exists(project_id, work_point, check_type):
        print(f"  — Skipping duplicate: {work_point} ({check_type})")
        return

    payload = {
        "parent": {"database_id": MONDAY_CHECK_DB_ID},
        "properties": {
            "Name": {
                "title": [{"text": {"content": work_point}}]
            },
            "Project": {
                "relation": [{"id": project_id}]
            },
            "Is Template": {
                "checkbox": True
            },
            "Check Type": {
                "select": {"name": check_type}
            },
            "Employee dashboards": {
                "relation": employee_dashboards
            },
            "Status": {
                "select": {"name": "None"}
            },
            "Reviewed": {
                "select": {"name": "Not Started"}
            }
        }
    }
    notion_post("/pages", payload)
    print(f"  ✓ Created: {work_point} ({check_type})")


def template_exists(project_id, work_point, check_type):
    payload = {
        "filter": {
            "and": [
                {
                    "property": "Name",
                    "title": {"equals": work_point}
                },
                {
                    "property": "Project",
                    "relation": {"contains": project_id}
                },
                {
                    "property": "Check Type",
                    "select": {"equals": check_type}
                },
                {
                    "property": "Is Template",
                    "checkbox": {"equals": True}
                }
            ]
        }
    }

    data = notion_post(f"/databases/{MONDAY_CHECK_DB_ID}/query", payload)

    return len(data.get("results", [])) > 0 if data else False


def run():
    page_url = input("Paste project URL: ").strip()
    page_id = extract_page_id(page_url)

    if not page_id:
        print("Invalid URL.")
        return

    project = get_project(page_id)

    if not project:
        print("Could not fetch project.")
        return

    props = project.get("properties", {})
    employee_dashboards = props.get("Employee dashboards", {}).get("relation", [])

    work_points_by_type = get_work_points_by_type(project)

    # Count total
    total_points = sum(len(wps) for wps in work_points_by_type.values())

    # Enforce all categories have at least one
    missing = [ctype for ctype, wps in work_points_by_type.items() if len(wps) == 0]

    if missing:
        print("Missing work points for:")
        for m in missing:
            print(f"  - {m}")
        print("\nPlease select at least one work point in each category before running.")
        return

    for check_type, work_points in work_points_by_type.items():
        print(f"Creating {check_type} templates:")

        for wp in work_points:
            print(f"  - {wp}")
            create_template(page_id, wp, check_type, employee_dashboards)

    print(f"\nCreated {total_points} template(s).")


if __name__ == "__main__":
    run()
