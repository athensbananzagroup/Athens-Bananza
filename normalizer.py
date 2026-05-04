# NORMALIZERS

STATUS_NORMALIZATION = {
    "in progress": "In Progress",
    "in-progress": "In Progress",
    "ip": "In Progress",
    "done": "Done",
    "completed": "Done",
    "complete": "Done",
    "reviewed": "Reviewed",
    "none": "None",

    "not started": "Not Started",
}

REVIEWED_NORMALIZATION = {
    "yes": "Yes",
    "y": "Yes",
    "true": "Yes",
    "no": "No",
    "n": "No",
    "false": "No",
}


def normalize_text(value):
    if value is None:
        return ""
    return str(value).strip()



def normalize_status(value):
    value = normalize_text(value)
    if not value:
        return ""
    lowered = value.lower()
    return STATUS_NORMALIZATION.get(lowered, value)



def normalize_reviewed(value):
    value = normalize_text(value)
    if not value:
        return ""
    lowered = value.lower()
    return REVIEWED_NORMALIZATION.get(lowered, value)