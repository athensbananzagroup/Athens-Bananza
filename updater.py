from config import MONDAY_CHECK_DB_ID
from normalizer import (
    normalize_text,
    normalize_status,
    normalize_reviewed,
)
from notion_client import notion_post, notion_patch

# PAGE PAYLOAD BUILDER AND UPDATER

def build_properties(row, project_lookup, employee_lookup):
    title = normalize_text(row.get("Monday Check Name"))
    project_name = normalize_text(row.get("Project"))
    check_type = normalize_text(row.get("Type of Check"))
    employee_name = normalize_text(row.get("Relevant Employee"))
    status = normalize_status(row.get("Current Status"))
    comment = normalize_text(row.get("Any Comments"))
    reviewed = normalize_reviewed(row.get("Reviewed?"))

    project_id = project_lookup.get(project_name)
    employee_id = employee_lookup.get(employee_name)

    if not title:
        print("Skipping row: missing title")
        raise ValueError("Missing title to properly map row")

    if not project_id:
        print(f"Skipping row: project not found -> {project_name}")
        raise ValueError(f"Missing project mapping for: {project_name}")

    unique_key = f"{title}::{project_id}"

    properties = {
        "Name": {
            "title": [{
                "text": {
                    "content": title
                }
            }]
        },
        "Project": {
            "relation": [{
                "id": project_id
            }]
        },
        "Check Type": {
            "select": {"name": check_type}
        } if check_type else None,

        "Employee dashboards": {
            "relation": [{
                "id": employee_id
            }] if employee_id else []
        },
        "Status": {
            "select": {"name": status}
        } if status else None,

        "Comment": {
            "rich_text": [{
                "text": {
                    "content": comment
                }
            }] if comment else []
        },
        "Reviewed": {
            "select": {"name": reviewed}
        } if reviewed else None,

        "Migrated": {
            "checkbox": True
        }
    }

    cleaned = {}
    for key, value in properties.items():
        if value is not None:
            cleaned[key] = value

    return unique_key, cleaned


def create_page(properties):
    payload = {
        "parent": {"database_id": MONDAY_CHECK_DB_ID},
        "properties": properties
    }
    result = notion_post("/pages", payload)

    if not result:
        raise Exception("Notion API returned no response — page creation failed")

    print("Created new Monday Check")


def update_page(page_id, properties):
    payload = {
        "properties": properties
    }

    notion_patch(f"/pages/{page_id}", payload)
    print("Updated existing Monday Check")