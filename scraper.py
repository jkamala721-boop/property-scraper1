import json
import re
import time

from bs4 import BeautifulSoup
from database import save_property, flush


from logger import log
from normalize import normalize
from extractor import extract_property

import requests


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
# MAIN
# -----------------------------
for listing_type, url in records:

    print("\n==========================")
    log(f"Scraping: {url}")
    print("==========================")

    if not check_listing_alive(url):

        log(f"Listing not available: {url}")
        continue

    # Download page with retry
    for attempt in range(3):

        try:

            response = requests.get(
                url,
                headers=headers,
                timeout=30
            )

            break

        except requests.exceptions.RequestException as e:

            print(f"Request failed (attempt {attempt + 1}): {e}")

            time.sleep(5)

    else:

        log(f"Skipping {url} after 3 failed attempts")
        continue


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

        except Exception:
           continue

    graph = obj.get("@graph")

    if not graph:
        continue

    print("Found @graph")

    raw_property = extract_property(graph, listing_type, url)

    print("✅ extract_property() finished")

    clean_property = normalize(raw_property)

    print("✅ normalize() finished")

    print("\nNORMALIZED PROPERTY")
    print("----------------")

    for k, v in clean_property.items():
     print(k, ":", v)

    print("✅ About to save property")

    save_property(clean_property)

print("\nRAW PROPERTY")
print("----------------")

for k, v in raw_property.items():
    print(k, ":", v)

print(f"Extracted listing {raw_property['listing_id']}")

print("\nNormalizing property...")
    
flush()