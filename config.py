# CONFIG

# notion token ID should be the API key for the workspace
# the database ID is the 32 characters between / and ? on the URL of a notion database
# if the database ID is the last 32 characters following [database]-copy- in the URL, that is the page database
# that will not work properly. Make sure you are accessing the database ID, not the page ID

NOTION_TOKEN = "NOTION_TOKEN_HERE"

MONDAY_CHECK_DB_ID = "31bcc2a6c00c80d49256cf371e364a26"
PROJECT_DB_ID = "30acc2a6c00c817291bfd97875cad3e9"
EMPLOYEE_DB_ID = "30acc2a6c00c81739727f17b2bba8dc4"
MIGRATION_DB_ID = "351cc2a6c00c80e0b130c5286eca5dd4"

# CSV_FILE_PATH = "csv_files/monday_checks - ind.csv"

# notion version may have to be changed. This can be seen in the link below:
# https://developers.notion.com/reference/versioning
NOTION_VERSION = "2022-06-28"
BASE_URL = "https://api.notion.com/v1"

HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": NOTION_VERSION,
}