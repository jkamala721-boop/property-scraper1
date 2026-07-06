import json
import re

from bs4 import BeautifulSoup
from supabase import create_client

from config import SUPABASE_URL, SUPABASE_KEY

from logger import log


# -----------------------------
# SUPABASE
# -----------------------------
import requests
supabase = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)


# -----------------------------
# CONFIG
# -----------------------------

#with open("links.txt", "r") as f:
records = []

with open("links.txt", "r") as f:

    for line in f:

        line = line.strip()

        if not line:
            continue

        listing_type, url = line.split("|", 1)

        records.append((listing_type, url))

headers = {
    "User-Agent": "Mozilla/5.0"
}


# -----------------------------
# CHECK LISTING
# -----------------------------

def check_listing_alive(url):

    try:

        r = requests.get(
            url,
            headers=headers,
            timeout=20
        )

        if r.status_code != 200:
            return False

        return "RealEstateListing" in r.text

    except:

        return False


# -----------------------------
# EXTRACT PROPERTY
# -----------------------------

def extract_property(graph,
listing_type):

    data = {}

    product = None
    accommodation = None
    listing = None
    agent = None

    for item in graph:

        t = item.get("@type")

        if t == "Product":
            product = item

        elif t == "Accommodation":
            accommodation = item

        elif t == "RealEstateListing":
            listing = item

        elif t == "RealEstateAgent":
            agent = item


    title = ""

    if product:
        title = product.get("name", "")

    data["title"] = title

    if product:
        data["description"] = product.get("description")


    if accommodation:

        data["bedrooms"] = accommodation.get(
            "numberOfBedrooms"
        )

        data["bathrooms"] = accommodation.get(
            "numberOfBathroomsTotal"
        )


    # PRICE

    m = re.search(r"KSh\s*([\d,]+)", title)

    if m:

        data["price"] = int(
            m.group(1).replace(",", "")
        )

        data["currency"] = "KES"

    else:

        data["price"] = None
        data["currency"] = None


    # LOCATION

    m = re.search(
        r"in\s+(.+?)\s+for",
        title
    )

    if m:
        data["location"] = m.group(1)

    else:
        data["location"] = None


    # LISTING ID

    m = re.search(r"(\d+)$", url)

    if m:
        data["listing_id"] = m.group(1)


    # SOURCE

    data["source"] = "BuyRentKenya"

    data["listing_type"] = listing_type

    data["url"] = url


    # STATUS

    if listing:

        data["posted_date"] = listing.get(
            "datePublished"
        )

        data["last_updated"] = listing.get(
            "dateModified"
        )

        data["is_live"] = True

    else:

        data["is_live"] = False


    # AGENT

    if agent:

        data["agent_name"] = agent.get("name")

    else:

        data["agent_name"] = None


    return data


# -----------------------------
# MAIN
# -----------------------------
for listing_type, url in records:

    print("\n==========================")
    log(f"Scraping: {url}")
    print("==========================")

    if not check_listing_alive(url):

        log(f"Listing not available: {url}")

        continue


    response = requests.get(
        url,
        headers=headers
    )

    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )

    scripts = soup.find_all(
        "script",
        type="application/ld+json"
    )

    for script in scripts:

        if not script.string:
            continue

        try:

            obj = json.loads(script.string)

        except:

            continue

        graph = obj.get("@graph")

        if not graph:
            continue

        result = extract_property(graph,
                listing_type)

        print("\nPROPERTY")
        print("----------------")

        for k, v in result.items():
            print(k, ":", v)

        supabase.table("properties").upsert(result).execute()

        log(f"Saved property {result['listing_id']}")

        break