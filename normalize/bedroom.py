import re


NUMBER_WORDS = {
    "studio": 0,
    "bedsitter": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
}


def normalize_bedroom(property_data):
    """
    Returns:
        bedrooms
        bedroom_type
        bedroom_confidence
    """

    text = " ".join([
        str(property_data.get("bedrooms", "")),
        str(property_data.get("title", "")),
        str(property_data.get("description", ""))
    ]).lower()

    # Studio / Bedsitter
    if "studio" in text or "bedsitter" in text:
        return {
            "bedrooms": 0,
            "bedroom_type": "Studio",
            "bedroom_confidence": 1.0
        }

    # Numeric values (e.g. 2 Bedroom, 3 Bed)
    match = re.search(r"(\d+)\s*(bed|beds|bedroom|bedrooms)", text)

    if match:
        bedrooms = int(match.group(1))

        return {
            "bedrooms": bedrooms,
            "bedroom_type": f"{bedrooms} Bedroom",
            "bedroom_confidence": 1.0
        }

    # Word values (e.g. Two Bedroom)
    for word, number in NUMBER_WORDS.items():
        if f"{word} bedroom" in text or f"{word} bed" in text:
            return {
                "bedrooms": number,
                "bedroom_type": f"{number} Bedroom",
                "bedroom_confidence": 0.95
            }

    return {
        "bedrooms": None,
        "bedroom_type": None,
        "bedroom_confidence": 0.0
    }


if __name__ == "__main__":

    property_data = {
        "title": "Luxury 3 Bedroom Apartment for Sale in Westlands",
        "description": ""
    }

    result = normalize_bedroom(property_data)

    print(result)