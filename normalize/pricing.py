import re


def normalize_price(property_data):
    """
    Returns:
        price
        currency
        listing_type
        price_confidence
    """

    text = " ".join([
        str(property_data.get("price", "")),
        str(property_data.get("title", "")),
        str(property_data.get("description", ""))
    ]).upper()

    # Determine listing type
    if "SALE" in text or "FOR SALE" in text:
        listing_type = "sale"
    elif "RENT" in text or "TO LET" in text:
        listing_type = "rent"
    else:
        listing_type = "unknown"

    # Find KES price
    match = re.search(r"(KES|KSH|KSHS)?\s*([\d,]+)", text)

    if match:
        value = int(match.group(2).replace(",", ""))

        return {
            "price": value,
            "currency": "KES",
            "listing_type": listing_type,
            "price_confidence": 1.0
        }

    return {
        "price": None,
        "currency": "KES",
        "listing_type": listing_type,
        "price_confidence": 0.0
    }


if __name__ == "__main__":

    property_data = {
        "title": "Apartment For Sale",
        "price": "KES 18,500,000",
        "description": ""
    }

    result = normalize_price(property_data)

    print(result)