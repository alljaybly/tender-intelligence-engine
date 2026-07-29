"""
South African geographic location extraction from tender text.

Detects references to provinces, cities, towns, and regions
using keyword matching.
"""
import logging
import re
from typing import List

logger = logging.getLogger(__name__)

# South African provinces and major cities/towns
_LOCATIONS: dict[str, list[str]] = {
    "gauteng": [
        "gauteng", "johannesburg", "pretoria", "sandton", "midrand",
        "centurion", "soweto", "alexandra", "randburg", "roodepoort",
        "krugersdorp", "benoni", "boksburg", "brakpan", "springs",
        "kempton park", "tembisa", "ivory park",
    ],
    "western_cape": [
        "western cape", "cape town", "stellenbosch", "paarl",
        "worcester", "george", "knysna", "mossel bay", "hermanus",
        "somerset west", "belville", "durbanville", "milnerton",
    ],
    "kwazulu_natal": [
        "kwa-zulu natal", "kwazulu-natal", "kzn", "durban",
        "pietermaritzburg", "richards bay", "newcastle", "ladysmith",
        "umhlanga", "ballito", "port shepstone",
    ],
    "eastern_cape": [
        "eastern cape", "port elizabeth", "gqeberha", "east london",
        "mthatha", "grahamstown", "makhanda", "queenstown",
        "king william's town", "bisho", "bhisho",
    ],
    "limpopo": [
        "limpopo", "polokwane", "pietersburg", "nespruit",
        "lephalale", "thohoyandou", "modimolle", "mokopane",
    ],
    "mpumalanga": [
        "mpumalanga", "nelspruit", "mbombela", "ermelo",
        "witbank", "emalahleni", "secunda", "standerton",
    ],
    "north_west": [
        "north west", "north-west", "rustenburg", "mahikeng",
        "klerksdorp", "potchefstroom", "brits",
    ],
    "free_state": [
        "free state", "bloemfontein", "welkom", "bettie",
        "sasolburg", "phuthaditjhaba", "kroonstad",
    ],
    "northern_cape": [
        "northern cape", "kimberley", "upington", "springbok",
        "kuruman", "de aar",
    ],
    "national": [
        "national", "all provinces", "countrywide", "nationwide",
        "south africa", "republic of south africa",
    ],
}


def detect_locations(text: str) -> List[str]:
    """
    Scan tender text and return a list of detected locations (province keys).

    Returns province-level keys like ["gauteng", "western_cape"].
    """
    if not text or not text.strip():
        logger.debug("[LOCATION] Empty text")
        return []

    lower_text = text.lower()
    detected: list[str] = []

    for province, keywords in _LOCATIONS.items():
        for keyword in keywords:
            if re.search(re.escape(keyword), lower_text):
                detected.append(province)
                logger.debug("[LOCATION] Matched '%s' -> %s", keyword, province)
                break  # Only add province once per match

    if detected:
        logger.info("[LOCATION] Detected locations: %s", detected)
    else:
        logger.info("[LOCATION] No locations detected")

    return detected