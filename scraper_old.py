import requests
import json
import re
from bs4 import BeautifulSoup
from supabase import create_client
from config import SUPABASE_URL, SUPABASE_KEY

supabase = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)

url = "https://www.buyrentkenya.com/listings/3-bedroom-apartment-for-sale-kileleshwa-4018632"

headers = {
    "User-Agent": "Mozilla/5.0"
}


def extract_specs_from_json(graph):

    data = {}

    product = None
    accommodation = None

    for item in graph:

        if item.get("@type") == "Product":
            product = item

        elif item.get("@type") == "Accommodation":
            accommodation = item

    title = ""

    if product:
        title = product.get("name", "")

    data["title"] = title

    if product:
        data["description"] = product.get("description", "")

    if accommodation:
        data["bedrooms"] = accommodation.get("numberOfBedrooms")
        data["bathrooms"] = accommodation.get("numberOfBathroomsTotal")

    # Extract price from title
    price = re.search(r"KSh\s*([\d,]+)", title)

    if price:
        data["price"] = int(price.group(1).replace(",", ""))
        data["currency"] = "KES"
    else:
        data["price"] = None
        data["currency"] = None

    # Extract location from title
    location = re.search(r"in\s+(.+?)\s+for", title)

    if location:
        data["location"] = location.group(1)
    else:
        data["location"] = None
listing = re.search(r"(\d+)$", url)

if listing:
    data["listing_id"] = listing.group(1)
else:
    data["listing_id"] = None

data["source"] = "BuyRentKenya"

data["url"] = url

return data


def extract_listing_status(graph):

    status = {
        "posted_date": None,
        "last_updated": None,
        "is_live": False
    }

    for item in graph:

        if item.get("@type") == "RealEstateListing":

            status["posted_date"] = item.get("datePublished")
            status["last_updated"] = item.get("dateModified")
            status["is_live"] = True

            break

    return status


def check_listing_alive(url):

    try:

        r = requests.get(
            url,
            headers=headers,
            timeout=15
        )

        if r.status_code != 200:
            return False

        if "RealEstateListing" not in r.text:
            return False

        return True

    except Exception:
        return False


# ---------------- MAIN ----------------

if not check_listing_alive(url):

    print("LISTING NOT AVAILABLE")

else:

    response = requests.get(
        url,
        headers=headers,
        timeout=30
    )

    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )

    json_scripts = soup.find_all(
        "script",
        type="application/ld+json"
    )

    print("JSON-LD FOUND:", len(json_scripts))

for script in json_scripts:

        try:

            if not script.string:
                continue

            json_data = json.loads(script.string)

            graph = json_data.get("@graph")

            if not graph:
                continue

            # Show Real Estate Agent / Developer
            for item in graph:

                if item.get("@type") == "RealEstateAgent":

                    print("\n===== AGENT =====")
                    print(json.dumps(item, indent=4))

            result = extract_specs_from_json(graph)

            status = extract_listing_status(graph)

            result.update(status)

            print("\nPROPERTY DATA")
            print("----------------")

	response = (
    supabase
    .table("properties")
    .upsert(result)
    .execute()
)

print("Saved:", result["listing_id"])
            break

        except Exception as e:

            print("ERROR:", e)
        except Exception as e:

            print("ERROR:", e)
