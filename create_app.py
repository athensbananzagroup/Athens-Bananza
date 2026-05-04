import os
import re
from datetime import datetime, timedelta

import streamlit as st
from notion_client import Client

# --- Auth ---
NOTION_TOKEN = st.secrets.get("NOTION_TOKEN") or os.getenv("NOTION_TOKEN")
if not NOTION_TOKEN:
    st.error("NOTION_TOKEN is missing. Add it in Streamlit Cloud secrets.")
    st.stop()

client = Client(auth=NOTION_TOKEN)

MONDAY_CHECK_DB_ID = "31bcc2a6c00c80958f52000bc92cde8c"
PROJECTS_DB_ID = "30acc2a6c00c81179587000b85dd79c0"

# ----------------------------
# Notion helpers
# ----------------------------

def notion_get(page_id: str) -> dict:
    return client.pages.retrieve(page_id=page_id)


def notion_query(data_source_id: str, filter: dict = None, page_size: int = 100, start_cursor: str = None) -> dict:
    kwargs = dict(data_source_id=data_source_id, page_size=page_size)
    if filter:
        kwargs["filter"] = filter
    if start_cursor:
        kwargs["start_cursor"] = start_cursor
    return client.data_sources.query(**kwargs)


def notion_create(payload: dict) -> dict:
    return client.pages.create(**payload)


# ----------------------------
# Setup Project logic
# ----------------------------

def extract_page_id(url: str) -> str | None:
    url = url.split("?")[0]
    match = re.search(r"([a-f0-9]{32})$", url)
    return match.group(1) if match else None


def get_project(page_id: str) -> dict:
    return notion_get(page_id)


def get_work_points_by_type(project: dict) -> dict:
    props = project.get("properties", {})
    return {
        "Monday": [i["name"] for i in props.get("Monday Checks", {}).get("multi_select", [])],
        "Tuesday": [i["name"] for i in props.get("Tuesday Checks", {}).get("multi_select", [])],
        "Start of Month": [i["name"] for i in props.get("Start of Month Checks", {}).get("multi_select", [])],
    }


def template_exists(project_id: str, work_point: str, check_type: str) -> bool:
    data = notion_query(
        data_source_id=MONDAY_CHECK_DB_ID,
        filter={
            "and": [
                {"property": "Name", "title": {"equals": work_point}},
                {"property": "Project", "relation": {"contains": project_id}},
                {"property": "Check Type", "select": {"equals": check_type}},
                {"property": "Is Template", "checkbox": {"equals": True}},
            ]
        }
    )
    return len(data.get("results", [])) > 0 if data else False


def create_template(project_id: str, work_point: str, check_type: str, employee_dashboards: list) -> str:
    if template_exists(project_id, work_point, check_type):
        return "skipped"

    notion_create({
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


# ----------------------------
# Run Checks logic
# ----------------------------

def get_check_type(mode: str) -> str:
    return {"monday": "Monday", "tuesday": "Tuesday", "start": "Start of Month"}[mode]


def get_date(mode: str) -> str:
    today = datetime.today()
    if mode == "monday":
        d = today - timedelta(days=today.weekday())
    elif mode == "tuesday":
        d = today + timedelta((1 - today.weekday()) % 7)
    elif mode == "start":
        d = today.replace(day=1)
    return d.strftime("%Y-%m-%d")


def get_templates(check_type: str) -> list[dict]:
    data = notion_query(
        data_source_id=MONDAY_CHECK_DB_ID,
        filter={
            "and": [
                {"property": "Is Template", "checkbox": {"equals": True}},
                {"property": "Check Type", "select": {"equals": check_type}},
            ]
        }
    )
    return data.get("results", []) if data else []


def entry_exists(template: dict, date: str, check_type: str) -> bool:
    props = template["properties"]
    name = "".join([t["plain_text"] for t in props["Name"]["title"]])
    project = props["Project"]["relation"]

    data = notion_query(
        data_source_id=MONDAY_CHECK_DB_ID,
        filter={
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
    )
    return len(data.get("results", [])) > 0 if data else False


def create_entry(template: dict, date: str, check_type: str) -> str:
    props = template["properties"]
    name = "".join([t["plain_text"] for t in props["Name"]["title"]])

    if entry_exists(template, date, check_type):
        return "skipped"

    notion_create({
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


# ----------------------------
# UI
# ----------------------------

st.title("Notion Checks Manager")

tab1, tab2 = st.tabs(["Setup Project", "Run Checks"])

# --- Tab 1: Setup Project ---
with tab1:
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
                        st.error(f"Missing work points for: {', '.join(missing)}. Please select at least one in each category.")
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

            st.success(f"Done. Created {created_count} template(s), skipped {skipped_count} duplicate(s).")
            st.session_state["setup_work_points"] = None

# --- Tab 2: Run Checks ---
with tab2:
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

            st.success(f"Done. Created {created_count} entr(ies), skipped {skipped_count} duplicate(s).")
            st.session_state["run_templates"] = []
