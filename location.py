import re

# Nairobi areas we'll recognize
KNOWN_LOCATIONS = {
    "westlands": "Westlands",
    "kileleshwa": "Kileleshwa",
    "kilimani": "Kilimani",
    "lavington": "Lavington",
    "ruaka": "Ruaka",
    "runda": "Runda",
    "gigiri": "Gigiri",
    "karen": "Karen",
    "langata": "Langata",
    "parklands": "Parklands",
    "spring valley": "Spring Valley",
    "riverside": "Riverside",
    "upper hill": "Upper Hill",
    "south b": "South B",
    "south c": "South C",
    "kileleshwa": "Kileleshwa",   # common typo
}


def normalize_location(property_data):
    """
    Returns:
        standard_location
        county
        country
        confidence
    """

    text = " ".join([
        str(property_data.get("location", "")),
        str(property_data.get("title", "")),
        str(property_data.get("description", ""))
    ]).lower()

    text = re.sub(r"[^a-z0-9\s]", " ", text)

    for key, value in KNOWN_LOCATIONS.items():

        if key in text:

            return {
                "standard_location": value,
                "county": "Nairobi",
                "country": "Kenya",
                "location_confidence": 1.0
            }

    return {
        "standard_location": None,
        "county": None,
        "country": "Kenya",
        "location_confidence": 0.0
    }
if __name__ == "__main__":
    print("Location test started")

    property_data = {
        "title": "Luxury 2 Bedroom Apartment in Westlands",
        "location": "",
        "description": "Close to Sarit Centre."
    }

    result = normalize_location(property_data)

    print(result)

    print("Location test finished")   