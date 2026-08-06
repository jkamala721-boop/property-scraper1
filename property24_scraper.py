import json
import time
import requests

from bs4 import BeautifulSoup

from logger import log
from database import save_property, flush
from property24_extractor import extract_property

records = []

with open("links.txt", "r") as f:

    for line in f:

        line = line.strip()

        if not line:
            continue

        listing_type, url = line.split("|", 1)

        records.append((listing_type, url))
headers = {"User-Agent": "Mozilla/5.0"
}
           
def check_listing_alive(url):

    try:

        response = requests.get(
            url,
            headers=headers,
            timeout=20
        )

        return response.status_code == 200

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

    # Download page
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

        log(f"Skipping {url}")
        continue

    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )

    result = extract_property(
        soup,
        listing_type,
        url
    )

    if result is None:
        continue

    print("\nPROPERTY")
    print("----------------")

    for k, v in result.items():
        print(k, ":", v)

    save_property(result)

flush()  
        