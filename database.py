import time

from supabase import create_client

from config import SUPABASE_URL, SUPABASE_KEY
from logger import log


supabase = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)

BATCH_SIZE = 100
batch = []


def save_property(property_data):

    batch.append(property_data)

    print(f"Batch size = {len(batch)}")

    if len(batch) >= BATCH_SIZE:
        upload_batch()

def upload_batch():

    global batch

    if not batch:
        return

    for attempt in range(3):

        try:

            print(f"Uploading {len(batch)} properties...")

            supabase.table("properties").upsert(batch).execute()

            log(f"Uploaded {len(batch)} properties")

            batch.clear()

            return

        except Exception as e:

            print(f"Upload failed (attempt {attempt + 1}): {e}")

            time.sleep(10)

    log("Batch upload failed after 3 attempts")


def flush():

    upload_batch()