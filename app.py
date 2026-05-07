import csv
import os
import re
import time
from datetime import datetime, timedelta

import requests
import streamlit as st
from notion_client import Client

from config import (
    PROJECT_DB_ID,
    EMPLOYEE_DB_ID,
    MIGRATION_DB_ID
)

from parser import (
    load_csv_rows,
    load_indiv_csv,
    load_tues_csv
)

from notion_api import notion_patch

from relation_lookup import (
    fetch_relation_lookup,
    fetch_ready_imports,
    mark_import_running
)

from updater import (
    build_properties,
    create_page
)

from sheet_exporter import (
    export_google_sheet_as_csv,
    save_csv_temp
)


# =========================
# APP CONFIG / AUTH
# =========================

st.set_page_config(page_title="Notion Tools")

NOTION_TOKEN = st.secrets.get("NOTION_TOKEN") or os.getenv("NOTION_TOKEN")

if not NOTION_TOKEN:
    st.error("NOTION_TOKEN is missing. Add it in Streamlit Cloud secrets or your local environment.")
    st.stop()

client = Client(auth=NOTION_TOKEN)

BASE_URL = "https://api.notion.com/v1"
HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28",
}


# =========================
# MAIN.PY — MIGRATION IMPORT
# =========================

def process_row(row, project_lookup, employee_lookup):
    try:
        unique_key, properties = build_properties(
            row,
            project_lookup,
            employee_lookup
        )

        if not properties:
            return "SKIPPED", "No properties built"

        create_page(properties)

        return "SUCCESS", unique_key

    except Exception as e:
        return "FAILED", str(e)


def mark_import_failed(page_id, notion_patch_fn, error_message):
    try:
        notion_patch_fn(f"/pages/{page_id}", {
            "properties": {
                "Import Status": {
                    "status": {
                        "name": "Failed"
                    }
                },
                "Last Error": {
                    "rich_text": [
                        {
                            "text": {
                                "content": str(error_message)[:2000]
                            }
                        }
                    ]
                }
            }
        })

        print(f"Marked {page_id} as FAILED")

    except Exception as e:
        print(f"CRITICAL: Could not update failure state -> {e}")


def run_import_job(job, project_lookup, employee_lookup, notion_patch_fn):
    page_id = job["page_id"]
    import_type = job["import_type"]
    sheet_url = job["google_sheets_link"]

    print(f"\n=== STARTING JOB: {page_id} ({import_type}) ===")

    success = 0
    failed = 0
    skipped = 0
    error_log = []

    try:
        csv_text = export_google_sheet_as_csv(sheet_url)
        csv_path = save_csv_temp(csv_text, f"{page_id}.csv")

        if import_type == "group":
            rows = load_csv_rows(csv_path)
        elif import_type == "ind":
            rows = load_indiv_csv(csv_path)
        elif import_type == "tues":
            rows = load_tues_csv(csv_path)
        else:
            raise Exception(f"Unknown import type: {import_type}")

        print(f"Loaded {len(rows)} rows.")

        for i, row in enumerate(rows, start=1):
            status, result = process_row(
                row,
                project_lookup,
                employee_lookup
            )

            if status == "SUCCESS":
                success += 1
            elif status == "SKIPPED":
                skipped += 1
            else:
                failed += 1
                error_log.append({
                    "row_number": i,
                    "title": row.get("Monday Check Name", ""),
                    "error": result
                })

        if error_log:
            os.makedirs("logs", exist_ok=True)

            with open("logs/errors.csv", "w", newline="", encoding="utf-8") as file:
                writer = csv.DictWriter(file, fieldnames=["row_number", "title", "error"])
                writer.writeheader()
                writer.writerows(error_log)

        notion_patch_fn(f"/pages/{page_id}", {
            "properties": {
                "Import Status": {"status": {"name": "Complete"}},
                "Last Error": {"rich_text": []}
            }
        })

        print(f"JOB COMPLETE → Success: {success}, Skipped: {skipped}, Failed: {failed}")

    except Exception as e:
        print(f"JOB FAILED: {str(e)}")
        mark_import_failed(page_id, notion_patch_fn, e)
        failed += 1

    return success, skipped, failed


def run_pipeline():
    success = 0
    skipped = 0
    failed = 0

    jobs = fetch_ready_imports(MIGRATION_DB_ID)

    if not jobs:
        print("No jobs found")
        return success, skipped, failed

    project_lookup = fetch_relation_lookup(PROJECT_DB_ID, "Name")
    employee_lookup = fetch_relation_lookup(EMPLOYEE_DB_ID, "Name")

    for job in jobs:
        try:
            mark_import_running(job["page_id"])

            job_success, job_skipped, job_failed = run_import_job(
                job,
                project_lookup,
                employee_lookup,
                notion_patch
            )

            success += job_success
            skipped += job_skipped
            failed += job_failed

        except Exception as e:
            print(f"JOB CRASHED: {str(e)}")
            failed += 1

    return success, skipped, failed


# =========================
# CREATE_APP.PY — RAW NOTION HELPERS
# =========================

MONDAY_CHECK_DB_ID = "31bcc2a6c00c80d49256cf371e364a26"
CREATE_PROJECT_DB_ID = "30acc2a6c00c817291bfd97875cad3e9"


def notion_get(endpoint: str) -> dict | None:
    response = requests.get(f"{BASE_URL}{endpoint}", headers=HEADERS)

    if response.status_code in [200, 201]:
        return response.json()

    st.error(f"GET ERROR {response.status_code}: {response.text}")
    return None


def notion_post(endpoint: str, payload: dict, retries: int = 3) -> dict | None:
    for attempt in range(retries):
        response = requests.post(f"{BASE_URL}{endpoint}", headers=HEADERS, json=payload)

        if response.status_code in [200, 201]:
            return response.json()

        if attempt < retries - 1:
            time.sleep(1)
        else:
            st.error(f"POST ERROR {response.status_code}: {response.text}")

    return None


def extract_page_id(url: str) -> str | None:
    url = url.split("?")[0]
    match = re.search(r"([a-f0-9]{32})$", url)
    return match.group(1) if match else None


def get_project(page_id: str) -> dict | None:
    return notion_get(f"/pages/{page_id}")


def get_work_points_by_type(project: dict) -> dict:
    props = project.get("properties", {})

    return {
        "Monday": [i["name"] for i in props.get("Monday Checks", {}).get("multi_select", [])],
        "Tuesday": [i["name"] for i in props.get("Tuesday Checks", {}).get("multi_select", [])],
        "Start of Month": [i["name"] for i in props.get("Start of Month Checks", {}).get("multi_select", [])],
    }


def template_exists(project_id: str, work_point: str, check_type: str) -> bool:
    payload = {
        "filter": {
            "and": [
                {"property": "Name", "title": {"equals": work_point}},
                {"property": "Project", "relation": {"contains": project_id}},
                {"property": "Check Type", "select": {"equals": check_type}},
                {"property": "Is Template", "checkbox": {"equals": True}},
            ]
        }
    }

    data = notion_post(f"/databases/{MONDAY_CHECK_DB_ID}/query", payload)
    return len(data.get("results", [])) > 0 if data else False


def create_template(project_id: str, work_point: str, check_type: str, employee_dashboards: list) -> str:
    if template_exists(project_id, work_point, check_type):
        return "skipped"

    notion_post("/pages", {
        "parent": {"database_id": MONDAY_CHECK_DB_ID},
        "properties": {
            "Name": {"title": [{"text": {"content": work_point}}]},
            "Project": {"relation": [{"id": project_id}]},
            "Is Template": {"checkbox": True},
            "Check Type": {"select": {"name": check_type}},
            "Employee dashboards": {"relation": employee_dashboards},
            "Status": {"select": {"name": "None"}},
            "Reviewed": {"select": {"name": "Not Started"}},
        },
    })

    return "created"


def get_check_type(mode: str) -> str:
    return {
        "monday": "Monday",
        "tuesday": "Tuesday",
        "start": "Start of Month"
    }[mode]


def get_date(mode: str) -> str:
    today = datetime.today()

    if mode == "monday":
        d = today - timedelta(days=today.weekday())
    elif mode == "tuesday":
        d = today + timedelta((1 - today.weekday()) % 7)
    elif mode == "start":
        d = today.replace(day=1)
    else:
        raise ValueError(f"Unknown mode: {mode}")

    return d.strftime("%Y-%m-%d")


def get_templates(check_type: str) -> list[dict]:
    payload = {
        "filter": {
            "and": [
                {"property": "Is Template", "checkbox": {"equals": True}},
                {"property": "Check Type", "select": {"equals": check_type}},
            ]
        }
    }

    data = notion_post(f"/databases/{MONDAY_CHECK_DB_ID}/query", payload)
    return data.get("results", []) if data else []


def entry_exists(template: dict, date: str, check_type: str) -> bool:
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
                    "relation": {"contains": project[0]["id"]} if project else {},
                },
                {"property": "Check Type", "select": {"equals": check_type}},
                {"property": "Is Template", "checkbox": {"equals": False}},
            ]
        }
    }

    data = notion_post(f"/databases/{MONDAY_CHECK_DB_ID}/query", payload)
    return len(data.get("results", [])) > 0 if data else False


def create_entry(template: dict, date: str, check_type: str) -> str:
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


# =========================
# DELETE.PY — TEMPLATE CLEANER
# =========================

MONDAY_CHECKS_DATA_SOURCE_ID = "31bcc2a6c00c80958f52000bc92cde8c"
PROJECTS_DATA_SOURCE_ID = "30acc2a6c00c81179587000b85dd79c0"

PROJECT_PROPERTY_NAME = "Project"
TITLE_PROPERTY_NAME = "Name"
IS_TEMPLATE_PROPERTY_NAME = "Is Template"


def get_title_property_as_string(page: dict, prop_name: str) -> str:
    prop = page["properties"].get(prop_name)

    if not prop or prop["type"] != "title":
        return "(Untitled)"

    return "".join(t.get("plain_text", "") for t in prop["title"]) or "(Untitled)"


def get_project_page_id(project_name: str) -> str | None:
    query = client.data_sources.query(
        data_source_id=PROJECTS_DATA_SOURCE_ID,
        page_size=1,
        filter={
            "property": TITLE_PROPERTY_NAME,
            "title": {"equals": project_name},
        },
    )

    results = query["results"]
    return results[0]["id"] if results else None


def query_template_rows_for_project(project_page_id: str) -> list[dict]:
    rows = []
    start_cursor = None

    while True:
        query = client.data_sources.query(
            data_source_id=MONDAY_CHECKS_DATA_SOURCE_ID,
            page_size=100,
            start_cursor=start_cursor,
            filter={
                "and": [
                    {
                        "property": PROJECT_PROPERTY_NAME,
                        "relation": {"contains": project_page_id},
                    },
                    {
                        "property": IS_TEMPLATE_PROPERTY_NAME,
                        "checkbox": {"equals": True},
                    },
                ]
            },
        )

        rows.extend(query["results"])

        if not query.get("has_more"):
            break

        start_cursor = query.get("next_cursor")

    return rows


def trash_rows(rows: list[dict]) -> int:
    trashed_count = 0

    for row in rows:
        if row.get("in_trash") or row.get("archived"):
            continue

        client.pages.update(page_id=row["id"], in_trash=True)
        trashed_count += 1

    return trashed_count


# =========================
# STREAMLIT UI
# =========================

st.title("Notion Tools")

tab_import, tab_setup, tab_run, tab_delete = st.tabs([
    "Run Imports",
    "Setup Project",
    "Run Checks",
    "Delete Templates"
])


with tab_import:
    st.header("Notion Migrater")
    st.write("Run migration jobs from Notion into your database.")

    if st.button("Run Import"):
        with st.spinner("Running import..."):
            success, skipped, failed = run_pipeline()

        st.success("Import Complete!")

        col1, col2, col3 = st.columns(3)
        col1.metric("Success", success)
        col2.metric("Skipped", skipped)
        col3.metric("Failed", failed)


with tab_setup:
    st.header("Setup Project")

    project_url = st.text_input("Project URL")

    if st.button("Preview project"):
        if not project_url.strip():
            st.warning("Enter a project URL first.")
        else:
            page_id = extract_page_id(project_url.strip())

            if not page_id:
                st.error("Could not extract a page ID from that URL.")
            else:
                project = get_project(page_id)

                if not project:
                    st.error("Could not fetch the project.")
                else:
                    work_points_by_type = get_work_points_by_type(project)
                    missing = [ct for ct, wps in work_points_by_type.items() if not wps]

                    if missing:
                        st.error(
                            f"Missing work points for: {', '.join(missing)}. "
                            "Please select at least one in each category."
                        )
                    else:
                        st.session_state["setup_page_id"] = page_id
                        st.session_state["setup_project"] = project
                        st.session_state["setup_work_points"] = work_points_by_type

                        total = sum(len(v) for v in work_points_by_type.values())
                        st.success(f"Found {total} work point(s) across all check types.")

                        for check_type, wps in work_points_by_type.items():
                            st.write(f"**{check_type}**")
                            for wp in wps:
                                st.write("-", wp)

    if st.button("Create templates"):
        work_points_by_type = st.session_state.get("setup_work_points")
        page_id = st.session_state.get("setup_page_id")
        project = st.session_state.get("setup_project")

        if not work_points_by_type or not page_id:
            st.warning("No project loaded. Click 'Preview project' first.")
        else:
            props = project.get("properties", {})
            employee_dashboards = props.get("Employee dashboards", {}).get("relation", [])

            created_count = 0
            skipped_count = 0

            for check_type, work_points in work_points_by_type.items():
                for wp in work_points:
                    result = create_template(page_id, wp, check_type, employee_dashboards)

                    if result == "created":
                        created_count += 1
                    else:
                        skipped_count += 1

            st.success(
                f"Done. Created {created_count} template(s), "
                f"skipped {skipped_count} duplicate(s)."
            )

            st.session_state["setup_work_points"] = None


with tab_run:
    st.header("Run Checks")

    mode = st.selectbox("Check mode", ["monday", "tuesday", "start"])

    if st.button("Preview entries"):
        check_type = get_check_type(mode)
        date = get_date(mode)
        templates = get_templates(check_type)

        if not templates:
            st.error(f"No {check_type} templates found.")
        else:
            st.session_state["run_templates"] = templates
            st.session_state["run_check_type"] = check_type
            st.session_state["run_date"] = date

            st.success(f"Found {len(templates)} template(s) for {check_type} ({date}).")

            for t in templates:
                props = t["properties"]
                name = "".join([x["plain_text"] for x in props["Name"]["title"]])
                st.write("-", name)

    if st.button("Create entries"):
        templates = st.session_state.get("run_templates", [])
        check_type = st.session_state.get("run_check_type")
        date = st.session_state.get("run_date")

        if not templates:
            st.warning("No templates loaded. Click 'Preview entries' first.")
        else:
            created_count = 0
            skipped_count = 0

            for t in templates:
                result = create_entry(t, date, check_type)

                if result == "created":
                    created_count += 1
                else:
                    skipped_count += 1

            st.success(
                f"Done. Created {created_count} entr(ies), "
                f"skipped {skipped_count} duplicate(s)."
            )

            st.session_state["run_templates"] = []


with tab_delete:
    st.header("Notion Template Cleaner")

    project_name = st.text_input("Project name")

    if st.button("Find templates"):
        if not project_name.strip():
            st.warning("Enter a project name first.")
        else:
            project_page_id = get_project_page_id(project_name.strip())

            if not project_page_id:
                st.error(f'No project found named "{project_name}".')
            else:
                rows = query_template_rows_for_project(project_page_id)

                st.session_state["template_rows"] = rows
                st.session_state["project_name"] = project_name.strip()

                st.success(f'Found {len(rows)} template row(s) for "{project_name}".')

                for row in rows:
                    st.write("-", get_title_property_as_string(row, TITLE_PROPERTY_NAME))

    if st.button("Trash templates"):
        rows = st.session_state.get("template_rows", [])
        saved_project_name = st.session_state.get("project_name", project_name.strip())

        if not rows:
            st.warning("No template rows loaded. Click 'Find templates' first.")
        else:
            st.warning("This will move the checked template rows to trash.")

            trashed_count = trash_rows(rows)

            st.success(f'Trashed {trashed_count} template row(s) for "{saved_project_name}".')

            st.session_state["template_rows"] = []