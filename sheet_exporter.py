import requests
import os

# converting the linked Google sheets into a csv file, which the parser will then turn into a format
# that new format will be turned into Monday Check entries

def export_google_sheet_as_csv(sheet_url):
    import requests

    base_url = sheet_url.split("/edit")[0]

    # gid identifies which tab of the sheet we grab from
    # this is ugly but necessary

    gid = None
    if "gid=" in sheet_url:
        gid = sheet_url.split("gid=")[-1].split("&")[0]

    if gid:
        csv_url = f"{base_url}/export?format=csv&gid={gid}"
    else:
        csv_url = f"{base_url}/export?format=csv"

    print(f"Exporting CSV from: {csv_url}")

    response = requests.get(csv_url)

    if response.status_code != 200:
        raise Exception(f"Failed to download sheet CSV: {response.status_code}")

    return response.text

# creating and saving a temporary csv files

def save_csv_temp(csv_text, filename="temp_import.csv"):
    path = os.path.join("csv_files", filename)

    os.makedirs("csv_files", exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        f.write(csv_text)

    return path