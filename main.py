import csv

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
from notion_client import (
    notion_patch
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

# MAIN EXTRA - Scroll down more for actual main program

# importing the linked Google Sheets and turning it into a .csv

def run_import_job( job, project_lookup, employee_lookup, notion_patch_fn
):

    page_id = job["page_id"]
    import_type = job["import_type"]
    sheet_url = job["google_sheets_link"]

    print(f"\n=== STARTING JOB: {page_id} ({import_type}) ===")

    success = 0
    failed = 0
    skipped = 0
    error_log = []

    try:
        # STEP 1: Export sheet → CSV
        print("Downloading Google Sheet...")
        csv_text = export_google_sheet_as_csv(sheet_url)

        csv_path = save_csv_temp(csv_text, f"{page_id}.csv")

        # STEP 2: Parse CSV
        print("Parsing CSV...")

        if import_type == "group":
            rows = load_csv_rows(csv_path)

        elif import_type == "ind":
            rows = load_indiv_csv(csv_path)

        elif import_type == "tues":
            rows = load_tues_csv(csv_path)

        else:
            raise Exception(f"Unknown import type: {import_type}")

        print(f"Loaded {len(rows)} rows.")

        # STEP 3: Process rows (NOW WITH FULL LOGGING)
        for i, row in enumerate(rows, start=1):
            try:
                print(f"\nProcessing Row {i}...")

                _, props = build_properties(
                    row,
                    project_lookup,
                    employee_lookup
                )

                if not props:
                    skipped += 1
                    print(f"[{i}] SKIPPED -> No properties built")
                    continue

                create_page(props)

                success += 1
                print(f"[{i}] SUCCESS -> {row.get('Monday Check Name', 'Unknown')}")

            except Exception as e:
                failed += 1

                print(f"[{i}] FAILED -> {str(e)}")

                error_log.append({
                    "row_number": i,
                    "title": row.get("Monday Check Name", ""),
                    "error": str(e)
                })

        # STEP 4: Write error log (same as old main)
        if error_log:
            with open("logs/errors.csv", "w", newline="", encoding="utf-8") as file:
                writer = csv.DictWriter(
                    file,
                    fieldnames=["row_number", "title", "error"]
                )
                writer.writeheader()
                writer.writerows(error_log)

            print("\nError log written to logs/errors.csv")

        notion_patch_fn(f"/pages/{page_id}", {
            "properties": {
                "Import Status": {
                    "status": {
                        "name": "Complete"
                    }
                },
                "Last Error": {
                    "rich_text": []
                }
            }
        })

        print("\nJOB COMPLETE")

        print("\n=====================================")
        print(f"Success: {success}")
        print(f"Skipped: {skipped}")
        print(f"Failed:  {failed}")
        print("=====================================")


    except Exception as e:

        print(f"JOB FAILED: {str(e)}")

        mark_import_failed(
            page_id,
            notion_patch_fn,
            e
        )

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

# MAIN

def main():
    jobs = fetch_ready_imports(MIGRATION_DB_ID)

    if not jobs:
        print("No jobs found")
        return

    print("Loading relation lookups...")

    project_lookup = fetch_relation_lookup(PROJECT_DB_ID, "Name")
    employee_lookup = fetch_relation_lookup(EMPLOYEE_DB_ID, "Name")

    from notion_client import notion_patch

    print("Starting job execution...")

    for job in jobs:
        mark_import_running(job["page_id"])

        run_import_job(
            job,
            project_lookup,
            employee_lookup,
            notion_patch
        )


if __name__ == "__main__":
    main()