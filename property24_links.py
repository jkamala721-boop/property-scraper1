import requests
from bs4 import BeautifulSoup

from logger import log

BASE_URL = "https://www.property24.co.ke"

SEARCH_URL = (
    "https://www.property24.co.ke/"
    "apartments-flats-to-rent-in-nairobi-c1890"
)


def get_links():

    headers = {
        "User-Agent": (
            "Mozilla/5.0 "
            "(Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/137.0 Safari/537.36"
        )
    }

    records = []

    page = 1

    while True:

        url = f"{SEARCH_URL}?Page={page}"

        log(f"Reading page {page}")

        response = requests.get(
            url,
            headers=headers,
            timeout=30
        )
        print(response.status_code)
        print(response.text[:1000])

        if response.status_code != 200:
            break

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )
        print("\nFirst 30 links found on the page:\n")

        for link in soup.find_all("a", href=True)[:30]:
            print(link["href"])
        links = soup.find_all("a", href=True)

        found = 0

        for link in links:

            href = link["href"]

            if "/to-rent/" not in href:
                continue

            if href.startswith("/"):
                href = BASE_URL + href

            records.append(("rent", href))

            found += 1

        print(f"Found {found} listings")

        if found == 0:
            break

        page += 1

    return list(set(records))
if __name__ == "__main__":

    links = get_links()

    print(f"Total links: {len(links)}")

    for listing_type, url in links[:10]:
        print(url)