"""
Shopify Partners Directory Scraper
====================================
Extracts all service partners from the Shopify Partners Directory
(Custom Apps & Integrations category).

Source: https://www.shopify.com/partners/directory/services/development-and-troubleshooting/custom-apps-integrations

Strategy: Server-rendered HTML pages, paginated via ?page=N (16 partners/page).
           No public API exists — we use string search + regex on HTML.

Output: output/shopify_partners.csv
"""
import csv
import json
import os
import re
import time
import urllib.request
import urllib.error

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

BASE_URL = "https://www.shopify.com/partners/directory/services/development-and-troubleshooting/custom-apps-integrations"
DETAIL_BASE = "https://www.shopify.com"

RATE_LIMIT = 1.0  # seconds between requests
SERVICE_CATEGORY = "Custom apps and integrations"

# The marker that identifies a partner card link in the HTML
CARD_HREF_MARKER = '/partners/directory/partner/'


# ---------------------------------------------------------------------------
# HTTP helper
# ---------------------------------------------------------------------------
def http_get(url, retries=3, timeout=30):
    """Make a GET request and return the response body as a string."""
    headers = {
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.9",
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }
    req = urllib.request.Request(url, headers=headers)

    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8")
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
            if attempt < retries - 1:
                wait = 2 ** (attempt + 1)
                print(f"      Retry {attempt + 1}/{retries}: {e} (waiting {wait}s)")
                time.sleep(wait)
            else:
                raise


# ---------------------------------------------------------------------------
# HTML Helpers
# ---------------------------------------------------------------------------
def strip_tags(text):
    """Remove HTML tags and comments."""
    text = re.sub(r"<!--.*?-->", "", text)
    text = re.sub(r"<[^>]+>", "", text)
    return text.strip()


def get_total_count(html):
    """Extract total partner count from the listing page HTML."""
    m = re.search(r'"totalResults"[,\s:]+(\d+)', html)
    if m:
        return int(m.group(1))
    m = re.search(r"of\s+(\d[\d,]*)\s*</span>", html)
    if m:
        return int(m.group(1).replace(",", ""))
    return 0


# ---------------------------------------------------------------------------
# Card Extraction (pure string search — no HTMLParser needed)
# ---------------------------------------------------------------------------
def find_card_boundaries(html):
    """
    Find partner card <a> blocks using string search.
    Returns list of (href, card_html) tuples.

    Strategy:
      - Search for href="/partners/directory/partner/" in the HTML
      - Find the enclosing <a ...> opening tag
      - Count open/close <a> tags to find the matching </a>
    """
    cards = []
    search_from = 0

    while True:
        # Find next partner link
        idx = html.find(CARD_HREF_MARKER, search_from)
        if idx == -1:
            break

        # Find the start of the <a tag containing this href
        a_start = html.rfind("<a ", idx - 200, idx)
        if a_start == -1:
            a_start = html.rfind("<a\n", idx - 200, idx)
        if a_start == -1:
            search_from = idx + 1
            continue

        # Extract href value
        href_match = re.search(r'href="([^"]*' + re.escape(CARD_HREF_MARKER) + r'[^"]*)"',
                               html[a_start:a_start + 500])
        if not href_match:
            search_from = idx + 1
            continue

        href = href_match.group(1)

        # Find matching </a> — count nested <a> tags
        depth = 1
        pos = html.find(">", a_start) + 1  # Skip past the opening <a ...>

        while depth > 0 and pos < len(html):
            next_open = html.find("<a ", pos)
            next_open2 = html.find("<a\n", pos)
            if next_open2 != -1 and (next_open == -1 or next_open2 < next_open):
                next_open = next_open2
            next_close = html.find("</a>", pos)

            if next_close == -1:
                break

            if next_open != -1 and next_open < next_close:
                depth += 1
                pos = next_open + 3
            else:
                depth -= 1
                if depth == 0:
                    card_html = html[a_start:next_close + 4]
                    cards.append((href, card_html))
                pos = next_close + 4

        search_from = pos if pos > search_from else idx + 1

    return cards


def parse_card(href, card_html):
    """Parse a single partner card HTML into a dict using regex."""
    slug = href.rstrip("/").split("/")[-1]

    partner = {
        "name": "",
        "slug": slug,
        "url": DETAIL_BASE + href if href.startswith("/") else href,
        "logo_url": "",
        "location": "",
        "countries": "",
        "categories": SERVICE_CATEGORY,
        "tags": "",
        "services": "",
        "rating": "",
        "review_count": "",
        "pricing": "",
    }

    # Name: <h3>...</h3>
    h3 = re.search(r"<h3[^>]*>(.*?)</h3>", card_html, re.DOTALL)
    if h3:
        partner["name"] = strip_tags(h3.group(1))
    if not partner["name"]:
        return None

    # Logo: <img src="...">
    img = re.search(r'<img[^>]+src="([^"]+)"', card_html)
    if img:
        partner["logo_url"] = img.group(1)

    # Rating: <span...>5.0</span>
    rating = re.search(r"<span[^>]*>(\d\.\d)</span>", card_html)
    if rating:
        partner["rating"] = rating.group(1)

    # Review count: (<!-- -->5046<!-- -->) or (5046)
    review = re.search(r"\((?:<!--\s*-->)?(\d+)(?:<!--\s*-->)?\)", card_html)
    if review:
        partner["review_count"] = review.group(1)

    # Location: <span>|</span>...<span>CITY, Country</span>
    loc = re.search(r'<span[^>]*>\|</span>\s*<span[^>]*>([^<]+)</span>', card_html)
    if loc:
        location = loc.group(1).strip()
        partner["location"] = location
        parts = location.split(",")
        if len(parts) >= 2:
            partner["countries"] = parts[-1].strip()
        else:
            partner["countries"] = location

    # Pricing: after "Price range for services"
    price = re.search(
        r'Price range for services</span>\s*<span[^>]*>([^<]+)</span>', card_html
    )
    if price:
        partner["pricing"] = price.group(1).strip()

    # Services: after >Services</span>
    svc = re.search(r'>Services</span>\s*<span[^>]*>(.*?)</span>', card_html, re.DOTALL)
    if svc:
        partner["services"] = strip_tags(svc.group(1))

    return partner


def parse_listing_page(html):
    """Parse partner cards from a listing page HTML."""
    cards = find_card_boundaries(html)
    partners = []
    for href, card_html in cards:
        p = parse_card(href, card_html)
        if p:
            partners.append(p)
    return partners


# ---------------------------------------------------------------------------
# Scraping
# ---------------------------------------------------------------------------
def fetch_listing_pages(max_pages=200):
    """Fetch all listing pages and parse partner cards."""
    all_partners = []
    seen_slugs = set()

    print("      Fetching page 1...", end="", flush=True)
    first_html = http_get(BASE_URL)
    total = get_total_count(first_html)
    partners = parse_listing_page(first_html)

    for p in partners:
        if p["slug"] not in seen_slugs:
            seen_slugs.add(p["slug"])
            all_partners.append(p)

    print(f" got {len(partners)} partners (total reported: {total})")

    with open(os.path.join(DATA_DIR, "page_1.html"), "w", encoding="utf-8") as f:
        f.write(first_html)

    per_page = 16
    total_pages = (total + per_page - 1) // per_page if total > 0 else max_pages
    total_pages = min(total_pages, max_pages)

    print(f"      Total pages to fetch: {total_pages}")

    for page in range(2, total_pages + 1):
        url = f"{BASE_URL}?page={page}"
        print(f"      Fetching page {page}/{total_pages}...", end="", flush=True)

        try:
            html = http_get(url)
            partners = parse_listing_page(html)

            new_count = 0
            for p in partners:
                if p["slug"] not in seen_slugs:
                    seen_slugs.add(p["slug"])
                    all_partners.append(p)
                    new_count += 1

            print(f" got {len(partners)} ({new_count} new, total: {len(all_partners)})")

            if len(partners) == 0:
                print("      No more partners found, stopping.")
                break

        except Exception as e:
            print(f" ERROR: {e}")
            continue

        time.sleep(RATE_LIMIT)

    return all_partners, total


# ---------------------------------------------------------------------------
# CSV Output
# ---------------------------------------------------------------------------
def save_csv(records, filepath):
    """Save records to CSV."""
    fieldnames = [
        "name", "slug", "url", "logo_url", "location", "countries",
        "categories", "tags", "services", "rating", "review_count", "pricing",
    ]

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for r in records:
            writer.writerow(r)

    return len(records)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print("=" * 60)
    print("  Shopify Partners Directory Scraper")
    print("  Category: Custom Apps & Integrations")
    print("=" * 60)

    print("\n[1/2] Fetching all listing pages...")
    partners, total_reported = fetch_listing_pages()
    print(f"      Total partners scraped: {len(partners)}")

    if not partners:
        print("ERROR: No partners found!")
        return

    with open(os.path.join(DATA_DIR, "partners_raw.json"), "w", encoding="utf-8") as f:
        json.dump(partners, f, indent=2, ensure_ascii=False)

    print("\n[2/2] Saving CSV...")
    csv_path = os.path.join(OUTPUT_DIR, "shopify_partners.csv")
    count = save_csv(partners, csv_path)

    # Stats
    country_counts = {}
    for p in partners:
        country = p.get("countries", "")
        if country:
            country_counts[country] = country_counts.get(country, 0) + 1

    with_rating = sum(1 for p in partners if p.get("rating"))
    with_reviews = sum(1 for p in partners if p.get("review_count"))
    with_pricing = sum(1 for p in partners if p.get("pricing"))
    with_services = sum(1 for p in partners if p.get("services"))
    with_location = sum(1 for p in partners if p.get("location"))
    with_logo = sum(1 for p in partners if p.get("logo_url"))

    print(f"\n{'=' * 60}")
    print(f"  ✓ Saved {count} partners → {csv_path}")
    print(f"  Reported total: {total_reported}")
    print(f"  Scraped:        {count}")
    print(f"  With rating:    {with_rating}/{count}")
    print(f"  With reviews:   {with_reviews}/{count}")
    print(f"  With location:  {with_location}/{count}")
    print(f"  With pricing:   {with_pricing}/{count}")
    print(f"  With services:  {with_services}/{count}")
    print(f"  With logo:      {with_logo}/{count}")
    print(f"\n  Top 15 Countries:")
    for country, cnt in sorted(country_counts.items(), key=lambda x: -x[1])[:15]:
        print(f"    {country}: {cnt}")
    print(f"  Total countries: {len(country_counts)}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
