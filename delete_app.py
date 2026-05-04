import os

import streamlit as st
from dotenv import load_dotenv
from notion_client import Client


# load_dotenv()

# NOTION_TOKEN = os.getenv("NOTION_TOKEN")

NOTION_TOKEN = st.secrets.get("NOTION_TOKEN") or os.getenv("NOTION_TOKEN")

if not NOTION_TOKEN:
    st.error("NOTION_TOKEN is missing. Add it in Streamlit Cloud secrets.")
    st.stop()

if not NOTION_TOKEN:
    st.error("NOTION_TOKEN not found. Check your .env file.")
    st.stop()

client = Client(auth=NOTION_TOKEN)

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


st.title("Notion Template Cleaner")

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
