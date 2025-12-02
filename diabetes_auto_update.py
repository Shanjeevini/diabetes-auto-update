import os
import time
import json
import csv
from datetime import datetime
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

# ===========================
# CONFIG
# ===========================

BASE_DIR = "guidelines"
os.makedirs(BASE_DIR, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; DiabetesAutoUpdater/1.0; +email@example.com)"
}

DEBUG_LOG = os.path.join(BASE_DIR, "debug_log.txt")
PDF_INDEX = os.path.join(BASE_DIR, "pdf_index.csv")
SEEN_URLS_FILE = os.path.join(BASE_DIR, "downloaded_pdfs.json")

# For RSS (optional, you can add real feeds later)
RSS_FEEDS = [
    # "https://diabetesjournals.org/care/rss/current",
    # "https://www.thelancet.com/journals/landia/rss",
]

# Global state
seen_urls = set()
new_downloads = []  # list of dicts: {source, filename, url}


# ===========================
# LOGGING & INDEX HELPERS
# ===========================

def log(msg: str):
    print(msg)
    with open(DEBUG_LOG, "a", encoding="utf-8") as f:
        f.write(f"{datetime.utcnow().isoformat()} - {msg}\n")


def init_logs():
    # Reset debug log each run
    open(DEBUG_LOG, "w").close()

    # Create CSV header if not exists
    if not os.path.exists(PDF_INDEX):
        with open(PDF_INDEX, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["source", "filename", "url", "download_date"])


def add_pdf_index(source: str, filename: str, url: str):
    with open(PDF_INDEX, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([source, filename, url, datetime.utcnow().isoformat()])


def load_seen_urls():
    global seen_urls
    if os.path.exists(SEEN_URLS_FILE):
        try:
            with open(SEEN_URLS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            seen_urls = set(data)
            log(f"[INFO] Loaded {len(seen_urls)} previously seen URLs")
        except Exception as e:
            log(f"[WARN] Failed to load seen URLs: {e}")
            seen_urls = set()
    else:
        seen_urls = set()
        log("[INFO] No previous seen URL file, starting fresh")


def save_seen_urls():
    try:
        with open(SEEN_URLS_FILE, "w", encoding="utf-8") as f:
            json.dump(sorted(list(seen_urls)), f, indent=2)
        log(f"[INFO] Saved {len(seen_urls)} seen URLs")
    except Exception as e:
        log(f"[WARN] Failed to save seen URLs: {e}")


# ===========================
# HTTP & PARSING HELPERS
# ===========================

def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)


def safe_filename(url: str) -> str:
    parsed = urlparse(url)
    name = parsed.path.split("/")[-1] or "file.pdf"
    name = name.split("?")[0]
    if not name.lower().endswith(".pdf"):
        name += ".pdf"
    return name


def get_soup(url: str):
    try:
        log(f"[FETCH] {url}")
        resp = requests.get(url, headers=HEADERS, timeout=30)
        if resp.status_code != 200:
            log(f"[WARN] Status {resp.status_code} for {url}")
            return None
        return BeautifulSoup(resp.text, "html.parser")
    except Exception as e:
        log(f"[ERROR] Failed to fetch {url}: {e}")
        return None


def find_pdf_links(soup, base_url: str, require_diabetes_word: bool = True):
    """
    Find PDF links on a page. If require_diabetes_word is True,
    keep only those where 'diabet' appears in text or href.
    """
    pdf_urls = set()
    if not soup:
        return pdf_urls

    for a in soup.find_all("a", href=True):
        href_raw = a["href"]
        href = href_raw.lower()
        text = (a.get_text() or "").lower()

        if require_diabetes_word and ("diabet" not in href and "diabet" not in text):
            continue

        if ".pdf" in href:
            full_url = urljoin(base_url, href_raw)
            pdf_urls.add(full_url)

    log(f"[INFO] Found {len(pdf_urls)} PDF links on {base_url}")
    return pdf_urls


def download_file(url: str, folder: str, source: str):
    global seen_urls, new_downloads

    ensure_dir(folder)
    filename = safe_filename(url)
    local_path = os.path.join(folder, filename)

    # If we've already seen this URL in previous runs, skip
    if url in seen_urls:
        log(f"[SKIP] Already known URL: {url}")
        return

    # If file already exists but URL not recorded, still treat as seen
    if os.path.exists(local_path):
        log(f"[SKIP] File exists but URL not tracked, marking as seen: {local_path}")
        seen_urls.add(url)
        return

    try:
        log(f"[DOWNLOAD] {url}")
        resp = requests.get(url, headers=HEADERS, timeout=45)
        if resp.status_code == 200:
            with open(local_path, "wb") as f:
                f.write(resp.content)
            log(f"[SAVED] {local_path}")

            # Mark as seen + new
            seen_urls.add(url)
            new_downloads.append({
                "source": source,
                "filename": filename,
                "url": url,
            })

            add_pdf_index(source, filename, url)
        else:
            log(f"[WARN] Status {resp.status_code} for {url}")
    except Exception as e:
        log(f"[ERROR] Download failed for {url}: {e}")


# ===========================
# SCRAPERS FOR EACH SOURCE
# ===========================

def update_ada():
    log("\n=== ADA (American Diabetes Association) ===")
    folder = os.path.join(BASE_DIR, "ADA")
    ensure_dir(folder)

    seed_urls = [
        "https://diabetesjournals.org/care/issue",
        "https://diabetesjournals.org/care",
    ]

    all_links = set()
    for url in seed_urls:
        soup = get_soup(url)
        # ADA is already diabetes-specific → no keyword restriction
        links = find_pdf_links(soup, url, require_diabetes_word=False)
        all_links.update(links)
        time.sleep(2)

    for link in sorted(all_links):
        download_file(link, folder, source="ADA")


def update_who():
    log("\n=== WHO (World Health Organization) ===")
    folder = os.path.join(BASE_DIR, "WHO")
    ensure_dir(folder)

    seed_urls = [
        "https://www.who.int/health-topics/diabetes",
        "https://www.who.int/publications",
    ]

    all_links = set()
    for url in seed_urls:
        soup = get_soup(url)
        links = find_pdf_links(soup, url, require_diabetes_word=True)
        all_links.update(links)
        time.sleep(2)

    for link in sorted(all_links):
        download_file(link, folder, source="WHO")


def update_idf():
    log("\n=== IDF (International Diabetes Federation) ===")
    folder = os.path.join(BASE_DIR, "IDF")
    ensure_dir(folder)

    seed_urls = [
        "https://idf.org/our-activities",
        "https://idf.org/resources",
    ]

    all_links = set()
    for url in seed_urls:
        soup = get_soup(url)
        links = find_pdf_links(soup, url, require_diabetes_word=True)
        all_links.update(links)
        time.sleep(2)

    for link in sorted(all_links):
        download_file(link, folder, source="IDF")


def update_nice():
    log("\n=== NICE (UK Guidelines) ===")
    folder = os.path.join(BASE_DIR, "NICE")
    ensure_dir(folder)

    search_url = "https://www.nice.org.uk/search?q=diabetes&ps=100&productType=Guidance"
    soup = get_soup(search_url)
    if not soup:
        return

    guidance_links = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        text = (a.get_text() or "").lower()
        if "/guidance/" in href and "diabet" in text:
            full = urljoin(search_url, href)
            guidance_links.add(full)

    log(f"[INFO] Found {len(guidance_links)} NICE guidance pages")

    all_pdfs = set()
    for g_url in guidance_links:
        sub_soup = get_soup(g_url)
        pdfs = find_pdf_links(sub_soup, g_url, require_diabetes_word=False)
        all_pdfs.update(pdfs)
        time.sleep(2)

    for link in sorted(all_pdfs):
        download_file(link, folder, source="NICE")


def update_mohfw():
    log("\n=== MOHFW (India) ===")
    folder = os.path.join(BASE_DIR, "MOHFW")
    ensure_dir(folder)

    seed_urls = [
        "https://main.mohfw.gov.in",
        # You can add more diabetes-specific URLs here as you find them
    ]

    all_links = set()
    for url in seed_urls:
        soup = get_soup(url)
        links = find_pdf_links(soup, url, require_diabetes_word=True)
        all_links.update(links)
        time.sleep(2)

    for link in sorted(all_links):
        download_file(link, folder, source="MOHFW")


# ===========================
# PubMed (metadata only, optional)
# ===========================

def update_pubmed():
    """
    Fetch recent diabetes-related article metadata from PubMed
    and store them in a JSON file. No PDFs here, only metadata.
    """
    log("\n=== PubMed (Metadata) ===")
    folder = os.path.join(BASE_DIR, "PubMed")
    ensure_dir(folder)

    today = datetime.utcnow().strftime("%Y/%m/%d")
    term = f"diabetes mellitus[majr] AND {today}[pdat]"

    search_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    summary_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"

    params = {
        "db": "pubmed",
        "term": term,
        "retmode": "json",
        "retmax": "50",
        "sort": "pub date",
    }

    try:
        log(f"[PUBMED] Searching: {term}")
        r = requests.get(search_url, params=params, headers=HEADERS, timeout=30)
        r.raise_for_status()
        data = r.json()
        ids = data.get("esearchresult", {}).get("idlist", [])
        log(f"[PUBMED] Found {len(ids)} IDs")

        if not ids:
            return

        params_summary = {
            "db": "pubmed",
            "id": ",".join(ids),
            "retmode": "json",
        }
        rs = requests.get(summary_url, params=params_summary, headers=HEADERS, timeout=30)
        rs.raise_for_status()
        summary_data = rs.json()

        out_path = os.path.join(folder, f"pubmed_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(summary_data, f, indent=2)
        log(f"[PUBMED] Saved metadata to {out_path}")
    except Exception as e:
        log(f"[PUBMED ERROR] {e}")


# ===========================
# RSS (optional, for journals)
# ===========================

def update_rss():
    if not RSS_FEEDS:
        log("\n=== RSS ===")
        log("[INFO] No RSS feeds configured. Edit RSS_FEEDS in the script if needed.")
        return

    log("\n=== RSS Feeds ===")
    folder = os.path.join(BASE_DIR, "RSS")
    ensure_dir(folder)

    try:
        import feedparser
    except ImportError:
        log("[ERROR] feedparser not installed. Add it to pip install in workflow.")
        return

    all_entries = []

    for feed_url in RSS_FEEDS:
        log(f"[RSS] Fetching: {feed_url}")
        d = feedparser.parse(feed_url)
        for entry in d.entries:
            link = entry.get("link", "")
            title = entry.get("title", "")
            published = entry.get("published", "")

            all_entries.append({
                "feed": feed_url,
                "title": title,
                "link": link,
                "published": published,
            })

            if link and link.lower().endswith(".pdf"):
                download_file(link, folder, source="RSS")

    if all_entries:
        out_path = os.path.join(folder, f"rss_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(all_entries, f, indent=2)
        log(f"[RSS] Saved {len(all_entries)} entries to {out_path}")


# ===========================
# EMAIL NOTIFICATION (GMAIL SMTP)
# ===========================

def send_email_if_new():
    """
    Send an email using Gmail SMTP if there are new downloads.
    Credentials must come from environment variables:
      GMAIL_USER, GMAIL_APP_PASSWORD, ALERT_EMAIL_TO
    """
    if not new_downloads:
        log("[EMAIL] No new files, not sending email.")
        return

    gmail_user = os.environ.get("GMAIL_USER")
    gmail_pass = os.environ.get("GMAIL_APP_PASSWORD")
    alert_to = os.environ.get("ALERT_EMAIL_TO", gmail_user)

    if not gmail_user or not gmail_pass or not alert_to:
        log("[EMAIL] Missing GMAIL_USER, GMAIL_APP_PASSWORD, or ALERT_EMAIL_TO. Cannot send email.")
        return

    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart

    subject = f"[Diabetes Auto Update] {len(new_downloads)} new file(s) downloaded"
    body_lines = [
        "New diabetes-related guideline files have been downloaded:\n"
    ]
    for item in new_downloads:
        body_lines.append(
            f"- Source: {item['source']}, File: {item['filename']}, URL: {item['url']}"
        )

    body_lines.append("\nThis email was sent automatically by the GitHub Actions updater.")
    body = "\n".join(body_lines)

    msg = MIMEMultipart()
    msg["From"] = gmail_user
    msg["To"] = alert_to
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        log("[EMAIL] Connecting to Gmail SMTP...")
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(gmail_user, gmail_pass)
            server.sendmail(gmail_user, [alert_to], msg.as_string())
        log(f"[EMAIL] Notification sent to {alert_to}")
    except Exception as e:
        log(f"[EMAIL ERROR] {e}")


# ===========================
# MAIN
# ===========================

if __name__ == "__main__":
    print("\n==============================")
    print("  DIABETES AUTO UPDATE START  ")
    print("  Time (UTC):", datetime.utcnow())
    print("==============================\n")

    init_logs()
    load_seen_urls()

    update_ada()
    update_who()
    update_idf()
    update_nice()
    update_mohfw()
    update_pubmed()
    update_rss()

    save_seen_urls()
    send_email_if_new()

    print("\n==============================")
    print("           ALL DONE           ")
    print("==============================\n")
