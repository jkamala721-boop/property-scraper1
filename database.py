import time

from supabase import create_client

from config import SUPABASE_URL, SUPABASE_KEY
from logger import log
from scrape_safety import has_sufficient_discovery_coverage


supabase = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)


# -----------------------------
# GLOBAL STATE
# -----------------------------

current_run_id = None
current_run_started_at = None

BATCH_SIZE = 100

batch = []
image_batch = []
run_property_batch = []


# -----------------------------
# START SCRAPE RUN
# -----------------------------

def start_scrape_run():

    global current_run_id
    global current_run_started_at

    result = (
        supabase
        .table("scrape_runs")
        .insert({
            "source": "BuyRentKenya",
            "status": "running"
        })
        .execute()
    )

    current_run_id = result.data[0]["id"]
    current_run_started_at = result.data[0]["started_at"]

    print(f"Scrape run started: {current_run_id}")

    return current_run_id


# -----------------------------
# SAVE PROPERTY
# -----------------------------

def save_property(property_data):

    image_urls = property_data.pop(
        "image_urls",
        []
    )

    listing_id = property_data.get(
        "listing_id"
    )

    # Record when this property was seen
    property_data["last_seen_at"] = "now()"

    batch.append(property_data)

    # Record property in current scrape snapshot
    if (
        current_run_id is not None
        and listing_id is not None
    ):

        run_property_batch.append({
            "run_id": current_run_id,
            "source": "BuyRentKenya",
            "listing_id": int(listing_id)
        })

    # Collect images
    for order, image_url in enumerate(image_urls):

        image_batch.append({
            "listing_id": listing_id,
            "image_url": image_url,
            "image_order": order
        })

    print(
        f"Batch size = {len(batch)}"
    )

    print(
        f"Images collected = {len(image_batch)}"
    )

    print(
        f"Snapshot properties = "
        f"{len(run_property_batch)}"
    )

    if len(batch) >= BATCH_SIZE:

        upload_batch()

# -----------------------------
# RECORD PRICE HISTORY
# -----------------------------

def record_price_history(property_data):

    listing_id = property_data.get("listing_id")
    price = property_data.get("price")
    currency = property_data.get("currency")

    if (
        current_run_id is None
        or listing_id is None
        or price is None
    ):
        return

    price_history = {
        "source": "BuyRentKenya",
        "listing_id": int(listing_id),
        "price": int(price),
        "currency": currency,
        "scrape_run_id": current_run_id
    }

    (
        supabase
        .table("property_price_history")
        .upsert(
            price_history,
            on_conflict=(
                "source,"
                "listing_id,"
                "scrape_run_id"
            )
        )
        .execute()
    )

# -----------------------------
# UPLOAD BATCH
# -----------------------------

def upload_batch():

    global batch
    global image_batch
    global run_property_batch

    if not batch:
        return

    for attempt in range(3):

        try:

            print(
                f"Uploading {len(batch)} "
                f"properties..."
            )

            # -------------------------
            # PROPERTIES
            # -------------------------

            supabase.table(
                "properties"
            ).upsert(
                batch,
                on_conflict="source,listing_id"
            ).execute()

            log(
                f"Uploaded {len(batch)} "
                f"properties"
            )


            # -------------------------
            # IMAGES
            # -------------------------

            if image_batch:

                supabase.table(
                    "property_images"
                ).upsert(
                    image_batch,
                    on_conflict="listing_id,image_url"
                ).execute()

                log(
                    f"Uploaded {len(image_batch)} "
                    f"images"
                )


            # -------------------------
            # SCRAPE SNAPSHOT
            # -------------------------

            if run_property_batch:

                supabase.table(
                    "scrape_run_properties"
                ).upsert(
                    run_property_batch,
                    on_conflict=(
                        "run_id,source,listing_id"
                    )
                ).execute()

                log(
                    f"Recorded "
                    f"{len(run_property_batch)} "
                    f"properties for scrape run"
                )


            # -------------------------
            # CLEAR BATCHES
            # -------------------------

            batch.clear()
            image_batch.clear()
            run_property_batch.clear()

            return


        except Exception as e:

            print(
                f"Upload failed "
                f"(attempt {attempt + 1}): {e}"
            )

            time.sleep(10)


    log(
        "Batch upload failed after 3 attempts"
    )

    raise RuntimeError(
        "Batch upload failed after 3 attempts"
    )


# -----------------------------
# MARK MISSING PROPERTIES
# -----------------------------

def mark_missing_properties_inactive(
    previous_run_id,
    current_run_id
):

    print(
        "Checking for properties that "
        "disappeared from the previous "
        "scrape..."
    )


    # -----------------------------
    # GET PREVIOUS SNAPSHOT
    # -----------------------------

    previous_result = (
        supabase
        .table("scrape_run_properties")
        .select("listing_id")
        .eq("run_id", previous_run_id)
        .eq("source", "BuyRentKenya")
        .execute()
    )

    previous_ids = {
        int(row["listing_id"])
        for row in previous_result.data
    }


    # -----------------------------
    # GET CURRENT SNAPSHOT
    # -----------------------------

    current_result = (
        supabase
        .table("scrape_run_properties")
        .select("listing_id")
        .eq("run_id", current_run_id)
        .eq("source", "BuyRentKenya")
        .execute()
    )

    current_ids = {
        int(row["listing_id"])
        for row in current_result.data
    }


    # -----------------------------
    # FIND DISAPPEARED LISTINGS
    # -----------------------------

    missing_ids = (
        previous_ids - current_ids
    )


    if not missing_ids:

        print(
            "No properties disappeared."
        )

        return


    print(
        f"Found {len(missing_ids)} "
        f"properties missing from "
        f"current scrape."
    )


    # -----------------------------
    # UPDATE IN CHUNKS
    # -----------------------------

    missing_ids = list(missing_ids)

    chunk_size = 500

    for i in range(
        0,
        len(missing_ids),
        chunk_size
    ):

        chunk = missing_ids[
            i:i + chunk_size
        ]

        (
            supabase
            .table("properties")
            .update({
                "is_live": "false"
            })
            .eq(
                "source",
                "BuyRentKenya"
            )
            .in_(
                "listing_id",
                chunk
            )
            .execute()
        )

        print(
            f"Marked {len(chunk)} "
            f"properties inactive."
        )


    print(
        "Inactive-property update "
        "completed."
    )


# -----------------------------
# DISCOVERY COVERAGE
# -----------------------------

def has_sufficient_discovery_baseline(discovered_properties):

    previous_result = (
        supabase
        .table("scrape_runs")
        .select("properties_found")
        .eq(
            "source",
            "BuyRentKenya"
        )
        .eq(
            "status",
            "completed"
        )
        .order(
            "id",
            desc=True
        )
        .limit(1)
        .execute()
    )

    previous_completed_properties = None

    if previous_result.data:
        previous_completed_properties = (
            previous_result.data[0].get("properties_found")
        )

        if previous_completed_properties is None:
            return False

    return has_sufficient_discovery_coverage(
        discovered_properties,
        previous_completed_properties
    )


# -----------------------------
# FINISH SCRAPE RUN
# -----------------------------

def finish_scrape_run(
    properties_found,
    expected_properties
):

    global current_run_id
    global current_run_started_at

    if current_run_id is None:

        return None

    finishing_run_id = current_run_id
    
    if properties_found != expected_properties:

        print(
            f"Scrape incomplete: "
            f"{properties_found}/"
            f"{expected_properties} properties processed."
        )

        (
            supabase
            .table("scrape_runs")
            .update({
            "finished_at": "now()",
            "status": "incomplete",
            "properties_found": properties_found
            })
            .eq(
                "id",
                current_run_id
            )
            .execute()
        )

        current_run_id = None
        current_run_started_at = None

        return {
            "run_id": finishing_run_id,
            "source": "BuyRentKenya",
            "status": "incomplete"
        }

    snapshot_result = (
        supabase
        .table("scrape_run_properties")
        .select("listing_id")
        .eq(
            "run_id",
            current_run_id
        )
        .eq(
            "source",
            "BuyRentKenya"
        )
        .execute()
    )

    snapshot_count = len(snapshot_result.data)

    if snapshot_count != expected_properties:

        print(
            f"Snapshot incomplete: "
            f"{snapshot_count}/"
            f"{expected_properties} properties persisted."
        )

        (
            supabase
            .table("scrape_runs")
            .update({
                "finished_at": "now()",
                "status": "incomplete",
                "properties_found": properties_found
            })
            .eq(
                "id",
                current_run_id
            )
            .execute()
        )

        current_run_id = None
        current_run_started_at = None

        return {
            "run_id": finishing_run_id,
            "source": "BuyRentKenya",
            "status": "incomplete"
        }

    if not has_sufficient_discovery_baseline(expected_properties):

        print(
            "Discovery corpus is insufficient compared to "
            "the previous completed scrape. Marking this run "
            "incomplete; no properties will be marked inactive."
        )

        (
            supabase
            .table("scrape_runs")
            .update({
                "finished_at": "now()",
                "status": "incomplete",
                "properties_found": properties_found
            })
            .eq(
                "id",
                current_run_id
            )
            .execute()
        )

        current_run_id = None
        current_run_started_at = None

        return {
            "run_id": finishing_run_id,
            "source": "BuyRentKenya",
            "status": "incomplete"
        }

    completed_run_id = current_run_id


    # -----------------------------
    # FIND PREVIOUS COMPLETED RUN
    # -----------------------------

    previous_result = (
        supabase
        .table("scrape_runs")
        .select("id")
        .eq(
            "source",
            "BuyRentKenya"
        )
        .eq(
            "status",
            "completed"
        )
        .order(
            "id",
            desc=True
        )
        .limit(1)
        .execute()
    )


    previous_run_id = None

    if previous_result.data:

        previous_run_id = (
            previous_result.data[0]["id"]
        )


    # -----------------------------
    # MARK CURRENT RUN COMPLETED
    # -----------------------------

    (
        supabase
        .table("scrape_runs")
        .update({
            "finished_at": "now()",
            "completed_at": "now()",
            "status": "completed",
            "properties_found": properties_found
        })
        .eq(
            "id",
            completed_run_id
        )
        .execute()
    )


    print(
        f"Scrape run {completed_run_id} "
        f"completed with "
        f"{properties_found} properties"
    )


    # -----------------------------
    # INACTIVE CHECK
    # -----------------------------

    if previous_run_id is None:

        print(
            "This is the first completed "
            "snapshot. No properties will "
            "be marked inactive."
        )

    else:

        mark_missing_properties_inactive(
            previous_run_id,
            completed_run_id
        )


    current_run_id = None
    current_run_started_at = None

    return {
        "run_id": completed_run_id,
        "source": "BuyRentKenya",
        "status": "completed"
    }

# -----------------------------
# FAIL SCRAPE RUN
# -----------------------------

def fail_scrape_run(
    error_message,
    properties_found
):

    global current_run_id
    global current_run_started_at

    if current_run_id is None:
        return

    (
        supabase
        .table("scrape_runs")
        .update({
            "finished_at": "now()",
            "status": "failed",
            "properties_found": properties_found
        })
        .eq(
            "id",
            current_run_id
        )
        .execute()
    )

    print(
        f"Scrape run {current_run_id} failed: "
        f"{error_message}"
    )

    current_run_id = None
    current_run_started_at = None

# -----------------------------
# APARTMENT IDENTITY
# -----------------------------

def ensure_apartment_identity(source, listing_id):

    # Check whether this listing is already connected
    existing = (
        supabase
        .table("apartment_listings")
        .select("apartment_id")
        .eq("source", source)
        .eq("listing_id", int(listing_id))
        .limit(1)
        .execute()
    )

    if existing.data:
        return existing.data[0]["apartment_id"]

    # Create a new apartment identity
    apartment = (
        supabase
        .table("apartments")
        .insert({})
        .execute()
    )

    apartment_id = apartment.data[0]["id"]
    apartment_code = apartment.data[0]["apartment_code"]

    # Connect the listing to the apartment
    (
        supabase
        .table("apartment_listings")
        .insert({
            "apartment_id": apartment_id,
            "source": source,
            "listing_id": int(listing_id),
            "match_status": "unmatched"
        })
        .execute()
    )

    print(
        f"Created apartment identity "
        f"{apartment_code} for "
        f"{source} listing {listing_id}"
    )

    return apartment_id

# -----------------------------
# FLUSH
# -----------------------------

def flush():

    upload_batch()
