from api.services.matcher import compute_match

tender_data = {
    "text": "We require construction services with at least 5 years experience in roadworks and civil engineering."
}

company_profile = {
    "keywords": ["construction", "civil engineering", "electrical"],
    "min_years_experience": 3
}

result = compute_match(tender_data, company_profile)

print(result)