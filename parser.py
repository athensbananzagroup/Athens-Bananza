import csv

from normalizer import normalize_text, normalize_status

# MANUAL INPUT GROUP PARSER

def load_csv_rows(path):
    rows = []

    with open(path, newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)

        # normalize fieldnames (IMPORTANT FIX)
        reader.fieldnames = [clean_header(f) for f in reader.fieldnames]

        for row in reader:
            cleaned_row = {
                clean_header(k): v for k, v in row.items()
            }
            rows.append(cleaned_row)

    return rows


# INDIVIDUAL PARSER

def load_indiv_csv(path):
    rows = []

    table1_finished = False
    table2_finished = False

    with open(path, newline="", encoding="utf-8-sig") as file:
        reader = csv.reader(file)

        # STEP 1: Clean all rows
        raw_rows = [
            [clean_header(x) for x in row]
            for row in reader
        ]

        # STEP 2: Filter meaningful rows only
        filtered_rows = [
            row for row in raw_rows
            if is_meaningful_row(row)
        ]

        # DEBUG (keep temporarily)
        for i in range(min(5, len(filtered_rows))):
            print(f"Filtered Row {i + 1}: {filtered_rows[i]}")

        # can be removed but like probably don't it's a nice easy debug

        if len(filtered_rows) < 2:
            print("ERROR: Not enough meaningful rows")
            return rows

        project_row = filtered_rows[1]

        if not project_row or all(not clean_header(x) for x in project_row):
            print("ERROR: CSV missing project row (Row 2)")
            return rows

        project_row = [clean_header(x) for x in project_row]

        while len(project_row) < 9:
            project_row.append("")

        table1_project = normalize_text(project_row[1])
        table2_project = normalize_text(project_row[6])

        print(f"Table 1 Project: {table1_project}")
        print(f"Table 2 Project: {table2_project}")

        for row_number, row in enumerate(filtered_rows[2:], start=3):

            row = [clean_header(x) for x in row]

            while len(row) < 9:
                row.append("")

            table1_title = normalize_text(row[1])
            table1_status = normalize_status(row[2])
            table1_comment = normalize_text(row[3])

            if not table1_finished:
                if table1_title == "":
                    table1_finished = True
                    print(f"Table 1 ended at row {row_number}")
                else:
                    rows.append({
                        "Monday Check Name": table1_title,
                        "Project": table1_project,
                        "Relevant Employee": "",
                        "Current Status": table1_status,
                        "Any Comments": table1_comment,
                        "Type of Check": "Start of Month"
                    })

            table2_title = normalize_text(row[6])
            table2_status = normalize_status(row[7])
            table2_comment = normalize_text(row[8])

            if not table2_finished:
                if table2_title == "":
                    table2_finished = True
                    print(f"Table 2 ended at row {row_number}")
                else:
                    rows.append({
                        "Monday Check Name": table2_title,
                        "Project": table2_project,
                        "Relevant Employee": "",
                        "Current Status": table2_status,
                        "Any Comments": table2_comment,
                        "Type of Check": "Monday"
                    })

            if table1_finished and table2_finished:
                print(f"Both tables completed. Stopping at row {row_number}")
                break

    print(f"Loaded {len(rows)} total rows from individual CSV.")
    return rows

# TUESDAY CHECK PARSER

def load_tues_csv(path):

    rows = []

    with open(path, newline="", encoding="utf-8-sig") as file:
        reader = csv.reader(file)

        # STEP 1: Clean all rows
        raw_rows = [
            [clean_header(x) for x in row]
            for row in reader
        ]

        # STEP 2: Filter meaningful rows
        filtered_rows = [
            row for row in raw_rows
            if any(clean_header(cell) for cell in row)
        ]

        # DEBUG (keep temporarily)
        for i in range(min(5, len(filtered_rows))):
            print(f"Filtered Row {i + 1}: {filtered_rows[i]}")

        # STEP 3: Validate structure
        if len(filtered_rows) < 2:
            print("ERROR: Not enough meaningful rows")
            return rows

        header_row = filtered_rows[1]

        while len(header_row) < 2:
            header_row.append("")

        employee_name = normalize_text(header_row[0])

        if not employee_name:
            print("ERROR: Missing employee name in Row 2 Column A")
            return rows

        # STEP 4: Extract titles
        titles = []
        for col in range(1, len(header_row)):
            titles.append(normalize_text(header_row[col]))

        print(f"Employee: {employee_name}")
        print(f"Found {len(titles)} title columns")

        # STEP 5: Process data rows
        for row_number, row in enumerate(filtered_rows[2:], start=3):

            while len(row) < len(header_row):
                row.append("")

            project_name = normalize_text(row[0])

            # blank project row = stop
            if not project_name:
                print(f"Stopped at row {row_number} (blank project)")
                break

            for col in range(1, len(header_row)):
                title = titles[col - 1]
                status = normalize_status(row[col])

                if not status:
                    continue

                if not title:
                    continue

                rows.append({
                    "Monday Check Name": title,
                    "Project": project_name,
                    "Relevant Employee": employee_name,
                    "Current Status": status,
                    "Any Comments": "",
                    "Type of Check": "Tuesday"
                })

    print(f"Loaded {len(rows)} total rows from Tuesday CSV.")
    return rows

# White space and weird row breaks fix

def clean_header(value):
    if value is None:
        return ""
    return str(value).replace("\r", "").strip()

def is_meaningful_row(row):
    return any(clean_header(cell) for cell in row)