import requests
from bs4 import BeautifulSoup

from logger import log

headers = {
    "User-Agent": "Mozilla/5.0"
}
AREAS = [

    "kilimani",
    "kileleshwa",
    "westlands-area",
    "lavington",
    "parklands",
    "riverside",
    "spring-valley",
    "gigiri",
    "kyuna",
    "lower-kabete",
    "upper-hill",
    "hurlingham",
    "ngong-road",
    "south-b",
    "south-c",
    "langata",
    "karen",
    "ridgeways",
    "ruaka",
    "rosslyn",
    "runda",
    "muthaiga",
    "kiambu-road",
    "kasarani",
    "roysambu",
    "garden-estate",
    "thindigua",
    "kiambu",
    "syokimau",
    "athi-river",
    "embakasi",
    "donholm",
    "utawala",
    "kahawa-west",
    "kahawa-sukari",
    "imara-daima",
    "kileleshwa-phase-1"

]
links = set()

for page in range(1, 21):

    log(f"\nChecking page {page}")

SEARCH_URLS = []

for area in AREAS:

    SEARCH_URLS.append({
        "type": "sale",
        "url": f"https://www.buyrentkenya.com/flats-apartments-for-sale/{area}"
    })

    SEARCH_URLS.append({
        "type": "rent",
        "url": f"https://www.buyrentkenya.com/flats-apartments-for-rent/{area}"
    })


for search in SEARCH_URLS:

    listing_type = search["type"]

    print(f"\n===== {listing_type.upper()} : {search['url']} =====")

    for page in range(1, 21):

        print(f"Checking page {page}")

        url = f'{search["url"]}?page={page}'

        response = requests.get(
            url,
            headers=headers,
            timeout=30
        )

        if response.status_code != 200:
            continue

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

        page_links = 0

        for a in soup.find_all("a", href=True):

            href = a["href"]

            if "/listings/" in href and "/crm/" not in href:

                if href.startswith("/"):
                    href = "https://www.buyrentkenya.com" + href

                links.add(f"{listing_type}|{href}")

                page_links += 1

        log(f"Found {page_links} links")

        if page_links == 0:
            print("No more pages for this area.")
            break

log(f"Unique links: {len(links)}")

with open("links.txt", "w") as file:

    for link in sorted(links):

        file.write(link + "\n")

log("Saved to links.txt successfully")
