from datetime import datetime

def log(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print(f"[{timestamp}] {message}")

    with open("property_scraper.log", "a") as f:
        f.write(f"[{timestamp}] {message}\n")
