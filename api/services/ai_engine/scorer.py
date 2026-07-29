KEYWORDS = [
    "construction", "contractor", "building", "supply",
    "maintenance", "infrastructure", "engineering"
]

def score_tender(text):
    score = 0
    text_lower = text.lower()

    for kw in KEYWORDS:
        if kw in text_lower:
            score += 10

    # length = complexity
    score += min(len(text) // 1000, 30)

    return min(score, 100)