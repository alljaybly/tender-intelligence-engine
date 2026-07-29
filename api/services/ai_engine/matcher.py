import re
from typing import Dict, List


def normalize_text(text: str) -> str:
    return re.sub(r'\s+', ' ', text.lower()).strip()


def keyword_match_score(tender_text: str, company_keywords: List[str]) -> Dict:
    tender_text = normalize_text(tender_text)

    matches = []
    missing = []

    for keyword in company_keywords:
        keyword_clean = keyword.lower().strip()
        if keyword_clean in tender_text:
            matches.append(keyword)
        else:
            missing.append(keyword)

    total = len(company_keywords)
    score = int((len(matches) / total) * 100) if total > 0 else 0

    return {
        "score": score,
        "matched_keywords": matches,
        "missing_keywords": missing
    }


def experience_match(tender_text: str, min_years: int) -> Dict:
    tender_text = normalize_text(tender_text)

    years_found = re.findall(r'(\d+)\s+years', tender_text)
    years_found = [int(y) for y in years_found]

    best_match = max(years_found) if years_found else 0

    meets_requirement = best_match >= min_years

    return {
        "required_years": min_years,
        "found_years": best_match,
        "meets_requirement": meets_requirement
    }


def compute_match(
    tender_data: Dict,
    company_profile: Dict
) -> Dict:

    tender_text = tender_data.get("text", "")

    keywords = company_profile.get("keywords", [])
    min_years = company_profile.get("min_years_experience", 0)

    keyword_result = keyword_match_score(tender_text, keywords)
    experience_result = experience_match(tender_text, min_years)

    # Weighted scoring (you can tweak later)
    final_score = int(
        (keyword_result["score"] * 0.7) +
        (100 if experience_result["meets_requirement"] else 0) * 0.3
    )

    gaps = keyword_result["missing_keywords"]
    if not experience_result["meets_requirement"]:
        gaps.append("insufficient_experience")

    return {
        "match_score": final_score,
        "keyword_match": keyword_result,
        "experience_match": experience_result,
        "gaps": gaps
    }