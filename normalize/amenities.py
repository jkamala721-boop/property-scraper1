AMENITIES = {
    "swimming_pool": [
        "swimming pool",
        "pool"
    ],
    "gym": [
        "gym",
        "fitness centre",
        "fitness center"
    ],
    "parking": [
        "parking",
        "car park"
    ],
    "lift": [
        "lift",
        "elevator"
    ],
    "backup_generator": [
        "backup generator",
        "generator"
    ],
    "borehole": [
        "borehole"
    ],
    "cctv": [
        "cctv"
    ],
    "security": [
        "24 hour security",
        "24/7 security",
        "security"
    ],
    "fiber_internet": [
        "fiber",
        "fibre",
        "wifi",
        "internet"
    ],
    "garden": [
        "garden",
        "landscaped garden"
    ],
    "children_play_area": [
        "play area",
        "kids play area",
        "children play area"
    ]
}


def normalize_amenities(property_data):
    """
    Returns:
        amenities
        amenities_count
    """

    text = " ".join([
        str(property_data.get("description", "")),
        str(property_data.get("title", ""))
    ]).lower()

    found = {}

    for amenity, keywords in AMENITIES.items():

        found[amenity] = any(keyword in text for keyword in keywords)

    found["amenities_count"] = sum(found.values())

    return found


if __name__ == "__main__":

    property_data = {
        "title": "Luxury Apartment",
        "description": """
        Features include:
        Swimming Pool,
        Gym,
        CCTV,
        Borehole,
        Parking,
        Lift,
        Backup Generator,
        Fibre Internet,
        Landscaped Garden,
        Children's Play Area
        """
    }

    result = normalize_amenities(property_data)

    print(result)