import csv

from config import (
    PROJECT_DB_ID,
    EMPLOYEE_DB_ID,
    MIGRATION_DB_ID,
    MONDAY_CHECK_DB_ID
)
from parser import (
    load_csv_rows,
    load_indiv_csv,
    load_tues_csv
)
from notion_api import (
    notion_patch,
    fetch_migrated_pages,
    delete_page,
    uncheck_migrated
)
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
import streamlit as st

# MAIN EXTRA - Scroll down more for actual main program

# importing the linked Google Sheets and turning it into a .csv

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
        # STEP 1: Download CSV
        csv_text = export_google_sheet_as_csv(sheet_url)
        csv_path = save_csv_temp(csv_text, f"{page_id}.csv")

        # STEP 2: Parse CSV
        if import_type == "group":
            rows = load_csv_rows(csv_path)
        elif import_type == "ind":
            rows = load_indiv_csv(csv_path)
        elif import_type == "tues":
            rows = load_tues_csv(csv_path)
        else:
            raise Exception(f"Unknown import type: {import_type}")

        print(f"Loaded {len(rows)} rows.")

        # STEP 3: Process rows (USE process_row)
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

        # STEP 4: Write error log
        if error_log:
            with open("logs/errors.csv", "w", newline="", encoding="utf-8") as file:
                writer = csv.DictWriter(file, fieldnames=["row_number", "title", "error"])
                writer.writeheader()
                writer.writerows(error_log)

        # STEP 5: Mark complete
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

    # ✅ CRITICAL: return counts
    return success, skipped, failed

# processing individual rows

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

# utility function for catching errors and avoiding crashes

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

def confirm_migration():

    pages = fetch_migrated_pages(MONDAY_CHECK_DB_ID)

    confirmed = 0

    for page in pages:
        uncheck_migrated(page["id"])
        confirmed += 1

    return confirmed

def undo_migration():

    pages = fetch_migrated_pages(MONDAY_CHECK_DB_ID)

    deleted = 0

    for page in pages:
        delete_page(page["id"])
        deleted += 1

    return deleted

# streamlit UI code

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

# MAIN

# def main():
#     jobs = fetch_ready_imports(MIGRATION_DB_ID)

#     if not jobs:
#         print("No jobs found")
#         return

#     print("Loading relation lookups...")

#     project_lookup = fetch_relation_lookup(PROJECT_DB_ID, "Name")
#     employee_lookup = fetch_relation_lookup(EMPLOYEE_DB_ID, "Name")

#     print("Starting job execution...")

#     for job in jobs:
#         mark_import_running(job["page_id"])

#         run_import_job(
#             job,
#             project_lookup,
#             employee_lookup,
#             notion_patch
#         )


# if __name__ == "__main__":
#     main()

# streamlit UI code

st.set_page_config(page_title="Notion Migrater")

st.title("Notion Migrater")
st.write("Run migration jobs from Notion into your database.")

if st.button("Run Import"):
    with st.spinner("Running import..."):

        success, skipped, failed = run_pipeline()

    st.success("Import Complete!")

    col1, col2, col3 = st.columns(3)

    col1.metric("Success", success)
    col2.metric("Skipped", skipped)
    col3.metric("Failed", failed)
    st.divider()

    col1, col2 = st.columns(2)

    with col1:

        if st.button("Undo Migration"):
            with st.spinner("Deleting migrated pages..."):
                deleted_count = undo_migration()

            st.warning(f"Deleted {deleted_count} migrated pages.")

    with col2:

        if st.button("Confirm Migration"):
            with st.spinner("Confirming migration..."):
                confirmed_count = confirm_migration()

            st.success(f"Confirmed {confirmed_count} migrated pages.")
