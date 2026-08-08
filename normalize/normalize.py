from .property import normalize_property


def normalize(property_data):
    """
    Main entry point for the REOS normalization package.
    """

    return normalize_property(property_data)


if __name__ == "__main__":

    sample_property = {
        "title": "Luxury 3 Bedroom Apartment For Sale in Westlands",
        "description": """
        Swimming Pool
        Gym
        Borehole
        CCTV
        Lift
        Backup Generator
        Fibre Internet
        3 Bathrooms
        """,
        "price": "KES 18,500,000",
        "location": "Westlands",
        "url": "https://example.com/property/123",
        "source": "BuyRentKenya"
    }

    result = normalize(sample_property)

    from pprint import pprint
    pprint(result)