import re
from normalize import normalize
def extract_property(obj, listing_type, url):
    data = {}
    return normalize(data)

import json
import re

from normalize import normalize


def extract_property(soup, listing_type, url):

    data = {}

    data["url"] = url
    data["listing_type"] = listing_type
    data["source"] = "Property24"

    # -----------------------------
    # Find Product JSON-LD
    # -----------------------------

    product = None

    scripts = soup.find_all(
        "script",
        type="application/ld+json"
    )

    for script in scripts:

        if not script.string:
            continue

        try:

            obj = json.loads(script.string)

        except Exception:
            continue

        if obj.get("@type") == "Product":

            product = obj
            break

    if product is None:

        return None

    # -----------------------------
    # Title
    # -----------------------------

    data["title"] = product.get("name")

    # -----------------------------
    # Description
    # -----------------------------

    data["description"] = product.get("description")
    
    # -----------------------------
# Bedrooms
# -----------------------------

    text = soup.get_text(" ", strip=True)

    m = re.search(r"(\d+)\s+Bedrooms?", text, re.IGNORECASE)

    if m:
        data["bedrooms"] = int(m.group(1))
    else:
        data["bedrooms"] = None


# -----------------------------
# Bathrooms
# -----------------------------

    m = re.search(r"(\d+)\s+Bathrooms?", text, re.IGNORECASE)

    if m:
        data["bathrooms"] = int(m.group(1))
    else:
        data["bathrooms"] = None


# -----------------------------
# Parking
# -----------------------------

    m = re.search(r"(\d+)\s+Parking Spaces?", text, re.IGNORECASE)

    if m:
        data["parking"] = int(m.group(1))
    else:
        data["parking"] = None


# -----------------------------
# Floor Size
# -----------------------------

    m = re.search(r"(\d+)\s*m²", text)

    if m:
        data["floor_size"] = int(m.group(1))
    else:
        data["floor_size"] = None

    # -----------------------------
    # Price
    # -----------------------------

    offers = product.get("offers", {})

    price = offers.get("price")

    if price:

        m = re.search(r"([\d, ]+)", str(price))

        if m:

            data["price"] = int(
                m.group(1)
                .replace(",", "")
                .replace(" ", "")
            )

        else:

            data["price"] = None

    else:

        data["price"] = None

    data["currency"] = "KES"

    # -----------------------------
    # Listing ID
    # -----------------------------

    m = re.search(r"(\d+)$", url)

    if m:

        data["listing_id"] = m.group(1)

    else:

        data["listing_id"] = None

    return normalize(data)