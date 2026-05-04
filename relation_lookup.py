from notion_client import notion_post

# DATABASE LOOKUPS

# Importing data from Notion

def fetch_ready_imports(migration_db_id):

    payload = {
        "filter": {
            "and": [
                {
                    "property": "Ready to Import",
                    "checkbox": {
                        "equals": True
                    }
                },
                {
                    "property": "Import Status",
                    "status": {
                        "equals": "Pending"
                    }
                }
            ]
        }
    }

    results = notion_post(f"/databases/{migration_db_id}/query", payload)

    imports = []

    if not results:
        print("No response from Migration DB.")
        return imports

    for row in results.get("results", []):
        props = row.get("properties", {})

        def get_title(prop_name):
            title_field = props.get(prop_name, {}).get("title", [])
            return "".join([t.get("plain_text", "") for t in title_field]).strip()

        def get_select(prop_name):
            sel = props.get(prop_name, {}).get("select")
            return sel.get("name") if sel else ""

        def get_url(prop_name):
            return props.get(prop_name, {}).get("url", "")

        imports.append({
            "page_id": row["id"],
            "name": get_title("Name"),
            "import_type": get_select("Import Type"),
            "google_sheets_link": get_url("Google Sheets Link")
        })

    print(f"Found {len(imports)} ready import(s).")

    return imports

# Editing the Status data inside Migration

def mark_import_running(page_id):

    from notion_client import notion_patch

    payload = {
        "properties": {
            "Ready to Import": {
                "checkbox": False
            },
            "Import Status": {
                "status": {
                    "name": "Running"
                }
            }
        }
    }

    response = notion_patch(f"/pages/{page_id}", payload)

    if response:
        print(f"Claimed job {page_id} → RUNNING")
        return True

    print(f"FAILED to claim job {page_id}")
    return False

# Getting entries in Notion

def fetch_relation_lookup(database_id, title_property_name):
    lookup = {}
    payload = {"page_size": 100}

    while True:
        results = notion_post(f"/databases/{database_id}/query", payload)
        if not results:
            break

        for row in results.get("results", []):

            props = row.get("properties", {})

            if title_property_name not in props:
                continue
            title_data = props[title_property_name].get("title", [])
            if not title_data:
                continue
            title = "".join([x.get("plain_text", "") for x in title_data]).strip()
            if title:
                lookup[title] = row["id"]

        if results.get("has_more"):
            payload["start_cursor"] = results["next_cursor"]
        else:
            break

    return lookup