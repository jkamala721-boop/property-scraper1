import re
import json

from bs4 import BeautifulSoup

#from normalize import normalize

def extract_property(graph,
listing_type, url):

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

        # IMAGES
        images = product.get("image", [])

        image_urls = []

        if isinstance(images, list):

            for image in images:

                if isinstance(image, dict):
                    image_url = image.get("@id")

                elif isinstance(image, str):
                    image_url = image

                else:
                    image_url = None

                if image_url:
                    image_urls.append(image_url)

        elif isinstance(images, dict):

            image_url = images.get("@id")

            if image_url:
                image_urls.append(image_url)

        elif isinstance(images, str):

            image_urls.append(images)

        data["image_urls"] = image_urls

    else:
        data["description"] = None
        data["image_urls"] = []

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
    #data = normalize(data)

    return data
