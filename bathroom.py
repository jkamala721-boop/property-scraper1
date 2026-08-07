import re


NUMBER_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
}


def normalize_bathroom(property_data):
    """
    Returns:
        bathrooms
        bathroom_confidence
    """

    text = " ".join([
        str(property_data.get("bathrooms", "")),
        str(property_data.get("title", "")),
        str(property_data.get("description", ""))
    ]).lower()

    # Numeric values
    match = re.search(r"(\d+)\s*(bath|baths|bathroom|bathrooms)", text)

    if match:
        bathrooms = int(match.group(1))

        return {
            "bathrooms": bathrooms,
            "bathroom_confidence": 1.0
        }

    # Word values
    for word, number in NUMBER_WORDS.items():
        if f"{word} bathroom" in text or f"{word} bathrooms" in text:
            return {
                "bathrooms": number,
                "bathroom_confidence": 0.95
            }

    return {
        "bathrooms": None,
        "bathroom_confidence": 0.0
    }


if __name__ == "__main__":

    property_data = {
        "title": "Modern 4 Bedroom Apartment with 3 Bathrooms",
        "description": ""
    }

    result = normalize_bathroom(property_data)

    print(result)