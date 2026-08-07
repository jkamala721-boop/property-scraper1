from .location import normalize_location
from .bedroom import normalize_bedroom
from .bathroom import normalize_bathroom
from .pricing import normalize_price
from .amenities import normalize_amenities


def normalize_property(property_data):
    """
    Normalize a raw property listing into one standardized REOS record.
    """

    # Keep every field extracted by the scraper
    normalized = property_data.copy()

    # Merge normalized data
    normalized.update(normalize_location(property_data))
    normalized.update(normalize_bedroom(property_data))
    normalized.update(normalize_bathroom(property_data))
    normalized.update(normalize_price(property_data))
    normalized.update(normalize_amenities(property_data))

    return normalized


if __name__ == "__main__":

    property_data = {
        "title": "Luxury 3 Bedroom Apartment For Sale in Westlands",
        "description": """
        Modern apartment with Swimming Pool, Gym,
        Borehole, CCTV, Lift, Parking,
        Fibre Internet and Backup Generator.
        3 Bathrooms.
        """,
        "price": "KES 18,500,000",
        "location": "Westlands",
        "url": "https://example.com/property/123",
        "source": "BuyRentKenya"
    }

    result = normalize_property(property_data)

    from pprint import pprint
    pprint(result)