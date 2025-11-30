import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime

# ------------------------------
#  Create base folder
# ------------------------------
BASE_DIR = "guidelines"
os.makedirs(BASE_DIR, exist_ok=True)

def download_file(url, folder):
    """Download a file only if not already downloaded."""
    os.makedirs(folder, exist_ok=True)
    local_filename = os.path.join(folder, url.split("/")[-1])

    if os.path.exists(local_filename):
        print(f"[SKIP] Already downloaded: {local_filename}")
        return

    print(f"[DOWNLOAD] {url}")
    r = requests.get(url, timeout=20)
    if r.status_code == 200:
        with open(local_filename, "wb") as f:
            f.write(r.content)
        print(f"[SAVED] {local_filename}")
    else:
        print(f"[FAILED] Status Code: {r.status_code}")

# ------------------------------
#  1. ADA Standards of Care
# ------------------------------
def update_ada():
    print("\n=== Updating ADA Guidelines ===")

    url = "https://diabetesjournals.org/care/issue"
    folder = os.path.join(BASE_DIR, "ADA")

    try:
        page = requests.get(url, timeout=20)
        soup = BeautifulSoup(page.text, "html.parser")

        pdf_links = [
            a["href"] for a in soup.find_all("a", href=True)
            if ("pdf" in a["href"] and "diabetesjournals" in a["href"])
        ]

        pdf_links = list(set(pdf_links))  # remove duplicates

        for link in pdf_links:
            if not link.startswith("http"):
                link = "https://diabetesjournals.org" + link
            download_file(link, folder)

    except Exception as e:
        print("ADA update failed:", e)

# ------------------------------
#  2. WHO Diabetes Guidelines
# ------------------------------
def update_who():
    print("\n=== Updating WHO Diabetes Guidelines ===")

    url = "https://www.who.int/publications"
    folder = os.path.join(BASE_DIR, "WHO")

    try:
        page = requests.get(url, timeout=20)
        soup = BeautifulSoup(page.text, "html.parser")

        pdf_links = [
            a["href"] for a in soup.find_all("a", href=True)
            if ("diabetes" in a.text.lower() and ".pdf" in a["href"])
        ]

        for link in pdf_links:
            if not link.startswith("http"):
                link = "https://www.who.int" + link
            download_file(link, folder)

    except Exception as e:
        print("WHO update failed:", e)

# ------------------------------
#  3. Indian MOHFW Diabetes Guidelines
# ------------------------------
def update_mohfw():
    print("\n=== Updating Indian MOHFW Guidelines ===")

    url = "https://main.mohfw.gov.in"
    folder = os.path.join(BASE_DIR, "MOHFW")

    try:
        page = requests.get(url, timeout=20)
        soup = BeautifulSoup(page.text, "html.parser")

        pdf_links = [
            a["href"] for a in soup.find_all("a", href=True)
            if (".pdf" in a["href"] and "diabetes" in a["href"].lower())
        ]

        for link in pdf_links:
            if not link.startswith("http"):
                link = "https://main.mohfw.gov.in" + link
            download_file(link, folder)

    except Exception as e:
        print("MOHFW update failed:", e)

# ------------------------------
#  4. NICE Guidelines (UK)
# ------------------------------
def update_nice():
    print("\n=== Updating NICE Guidelines ===")

    url = "https://www.nice.org.uk/guidance"
    folder = os.path.join(BASE_DIR, "NICE")

    try:
        page = requests.get(url, timeout=20)
        soup = BeautifulSoup(page.text, "html.parser")

        pdf_links = [
            a["href"] for a in soup.find_all("a", href=True)
            if (".pdf" in a["href"] and ("diabetes" in a.text.lower()))
        ]

        for link in pdf_links:
            if not link.startswith("http"):
                link = "https://www.nice.org.uk" + link
            download_file(link, folder)

    except Exception as e:
        print("NICE update failed:", e)

# ------------------------------
#  MAIN PROCESS
# ------------------------------
if __name__ == "__main__":
    print("\n==============================")
    print(" DIABETES AUTO UPDATE STARTED ")
    print(" Time:", datetime.now())
    print("==============================\n")

    update_ada()
    update_who()
    update_mohfw()
    update_nice()

    print("\n==============================")
    print("      UPDATE COMPLETED")
    print("==============================\n")
