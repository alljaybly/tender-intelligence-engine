import re
from typing import Dict, List

def clean_text(text: str) -> str:

    # Normalize spaces
    text = re.sub(r'\s+', ' ', text)

    # Restore line breaks after periods
    text = re.sub(r'\.\s+', '.\n', text)

    return text.strip()


def extract_field(pattern, text, default="Not found"):
    match = re.search(pattern, text, re.IGNORECASE)
    return match.group(1).strip() if match else default


def extract_requirements(text: str) -> List[str]:

    requirements = []

    requirement_keywords = [
        "experience",
        "registration",
        "compliance",
        "insurance",
        "cidb",
        "csd",
        "tax clearance",
        "site meeting",
        "mandatory",
        "qualification",
        "BEE",
        "B-BBEE",
        "closing time",
        "closing date"
    ]

    lines = text.splitlines()

    for line in lines:

        clean_line = line.strip()

        if len(clean_line) < 5:
            continue

        for keyword in requirement_keywords:
            if (
                keyword.lower() in clean_line.lower()
                and len(clean_line) < 250
            ):
                requirements.append(clean_line)
                break

    return list(set(requirements))[:10]


def summarize_text(text: str) -> Dict:

    text = clean_text(text)

    project_title = extract_field(
        r"quotation for[:\s]+(.*?)(?:Bid Number|Advert Date)",
        text
    )

    issuer = extract_field(
        r"(?:Issuer)\s+(.*?)(?:Tuesday|Closing|Contact)",
        text
    )

    closing_date = extract_field(
        r"Closing date and time\s+(?:\w+,\s+)?(\d{1,2}\s+\w+\s+\d{4})",
        text
    )

    contract_duration = extract_field(
        r"period of\s+(\d+\s+months?)",
        text
    )

    compulsory_meeting = extract_field(
        r"(?:Compulsory Site Meeting.*?)(\d{1,2}\s+\w+\s+\d{4})",
        text
    )

    requirements = extract_requirements(text)

    summary = {
        "project_title": project_title,
        "issuer": issuer,
        "closing_date": closing_date,
        "contract_duration": contract_duration,
        "compulsory_site_meeting": compulsory_meeting,
        "requirements": requirements
    }

    return summary