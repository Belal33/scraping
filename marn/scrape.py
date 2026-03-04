"""
MARN Marketplace Scraper
================================
Extracts all marketplace partners from marn.com/en/marketplace/.

Phase 1: Load cached HTML from data/marn_page_raw.json (MCP-fetched).
Phase 2: Parse partner cards from div.marketplacepartnerbox elements.
Phase 3: Fetch detail pages for each partner to enrich with extra info
         (location, fees, industry, website, full description).
Phase 4: Save to CSV.

Output: output/marn_marketplace.csv
"""
import csv
import json
import os
import re
import time
import urllib.request
import urllib.error
from scrapling import Selector

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

BASE_URL = "https://marn.com"
MARKETPLACE_URL = f"{BASE_URL}/en/marketplace/"

# MARN is a Saudi POS company
MARN_COUNTRIES = ["Saudi Arabia"]

RATE_LIMIT = 1.0  # seconds between detail page fetches


# ---------------------------------------------------------------------------
# Load HTML from cached MCP output
# ---------------------------------------------------------------------------
def load_html(html_file):
    """Load HTML from MCP-fetched JSON cache."""
    with open(html_file, "r", encoding="utf-8") as f:
        raw = f.read()

    try:
        data = json.loads(raw)
        if isinstance(data.get("content"), list):
            return data["content"][0]
        return data.get("content", raw)
    except (json.JSONDecodeError, KeyError):
        return raw


# ---------------------------------------------------------------------------
# Phase 2: Extract partner cards from marketplace HTML
# ---------------------------------------------------------------------------
def extract_partners(html):
    """Parse partner apps from div.marketplacepartnerbox elements."""
    page = Selector(html, url=MARKETPLACE_URL)
    partners = []
    seen = set()

    for box in page.css("div.marketplacepartnerbox"):
        # --- Name ---
        title_el = box.css("h6.marketplacepartnertitle")
        if not title_el:
            continue
        name = title_el[0].get_all_text(strip=True)
        if not name:
            continue

        # --- Detail URL (need it early for dedup) ---
        detail_url = ""
        link = box.css("a.button.border")
        if link:
            href = link[0].attrib.get("href", "")
            detail_url = href if href.startswith("http") else f"{BASE_URL}{href}"

        # Fix mislabeled partners by checking URL slug
        slug_match = re.search(r"/en/([^/]+)/?$", detail_url)
        slug = slug_match.group(1) if slug_match else name.lower().replace(" ", "-")

        # Use slug as unique key (handles duplicate names like 'Supy' -> 'hala-2')
        if slug in seen:
            continue
        seen.add(slug)

        # --- Logo URL ---
        logo_url = ""
        img = box.css("div.partnercolorbackground img")
        if img:
            logo_url = img[0].attrib.get("src", "")


        # --- Short Description ---
        desc_el = box.css("div.paragraph.greyish")
        description = ""
        if desc_el:
            description = desc_el[0].get_all_text(strip=True)

        partners.append({
            "name": name,
            "slug": slug,
            "url": detail_url,
            "logo_url": logo_url,
            "countries": "; ".join(MARN_COUNTRIES),
            "categories": "",
            "tags": "",
            "description": description[:500] if description else "",
            # Fields to be enriched from detail page
            "location": "",
            "fees": "",
            "industry": "",
            "website": "",
            "detail_description": "",
        })

    return partners


# ---------------------------------------------------------------------------
# Phase 3: Fetch and parse detail pages
# ---------------------------------------------------------------------------
def fetch_html(url, retries=3, timeout=30):
    """Fetch raw HTML from a URL using urllib."""
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except (urllib.error.URLError, urllib.error.HTTPError, OSError) as e:
            print(f"      ⚠ Attempt {attempt + 1}/{retries} failed for {url}: {e}")
            if attempt < retries - 1:
                time.sleep(2)
    return None


def parse_detail_page(html, url):
    """Extract extended info from a partner detail page."""
    page = Selector(html, url=url)
    info = {
        "location": "",
        "fees": "",
        "industry": "",
        "website": "",
        "detail_description": "",
    }

    # The detail page has a list of info items with headings like
    # "Company", "Location", "Fees", "Industry", "Website"
    # Each is in a <li> with an <h6> heading and adjacent text/link

    for li in page.css("ul li, div.partnerdescriptionr li, .partnerdetailbox li"):
        h6 = li.css("h6")
        if not h6:
            continue
        label = h6[0].get_all_text(strip=True).lower()

        # Get the value - text content after the h6
        value = li.get_all_text(strip=True)
        # Remove the label from the value
        if label in value.lower():
            value = value[len(label):].strip()

        if "location" in label:
            info["location"] = value
        elif "fee" in label:
            info["fees"] = value
        elif "industry" in label:
            info["industry"] = value
        elif "website" in label:
            # Try to get the link href
            link = li.css("a")
            if link:
                info["website"] = link[0].attrib.get("href", value)
            else:
                info["website"] = value

    # Get the longer description from the page body
    # The main description is usually in p.hero or div.content-width-large
    desc_el = page.css("p.hero")
    if desc_el:
        info["detail_description"] = desc_el[0].get_all_text(strip=True)[:1000]
    else:
        # Fallback: look in content-width-large
        desc_blocks = page.css("div.content-width-large")
        descriptions = []
        for block in desc_blocks:
            text = block.get_all_text(strip=True)
            if text and len(text) > 30:
                descriptions.append(text)
        if descriptions:
            info["detail_description"] = max(descriptions, key=len)[:1000]

    return info


def enrich_partners(partners):
    """Fetch detail pages and enrich partner data."""
    total = len(partners)
    cache_file = os.path.join(DATA_DIR, "detail_cache.json")

    # Load existing cache
    cache = {}
    if os.path.exists(cache_file):
        with open(cache_file, "r", encoding="utf-8") as f:
            cache = json.load(f)

    enriched = 0
    for i, partner in enumerate(partners):
        url = partner.get("url", "")
        if not url:
            continue

        print(f"      [{i+1}/{total}] {partner['name']}...", end=" ")

        # Check cache first
        if url in cache:
            html = cache[url]
            print("(cached)", end=" ")
        else:
            html = fetch_html(url)
            if html:
                cache[url] = html
                # Save cache after each fetch
                with open(cache_file, "w", encoding="utf-8") as f:
                    json.dump(cache, f, ensure_ascii=False)
            time.sleep(RATE_LIMIT)

        if html:
            info = parse_detail_page(html, url)
            partner.update(info)
            enriched += 1
            print(f"✓ {info.get('industry', 'N/A')}")
        else:
            print("✗ (failed)")

    return enriched


# ---------------------------------------------------------------------------
# Save CSV
# ---------------------------------------------------------------------------
def save_csv(partners, filepath):
    """Save partner data to CSV matching standard format."""
    fieldnames = [
        "name", "slug", "url", "logo_url", "countries", "categories",
        "tags", "description", "location", "fees", "industry", "website",
        "detail_description",
    ]

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for p in partners:
            writer.writerow(p)

    return len(partners)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print("=" * 60)
    print("  MARN Marketplace Scraper")
    print("=" * 60)

    html_file = os.path.join(DATA_DIR, "marn_page_raw.json")
    if not os.path.exists(html_file):
        print(f"\nERROR: Cached HTML not found at {html_file}")
        print("Please fetch the page first using Scrapling MCP fetch")
        print(f"and save the output to {html_file}")
        return

    # --- Load HTML ---
    print("\n[1/4] Loading cached HTML...")
    html = load_html(html_file)
    print(f"      HTML size: {len(html):,} chars")

    # --- Extract partners ---
    print("\n[2/4] Extracting marketplace partners...")
    partners = extract_partners(html)
    print(f"      Found {len(partners)} unique partners")

    if not partners:
        print("ERROR: No partners found!")
        return

    # Print partner names for verification
    for p in partners:
        print(f"      • {p['name']}: {p['url']}")

    # --- Enrich with detail pages ---
    print("\n[3/4] Fetching detail pages for enrichment...")
    enriched = enrich_partners(partners)
    print(f"      Enriched {enriched}/{len(partners)} partners")

    # --- Save ---
    print("\n[4/4] Saving CSV...")
    csv_path = os.path.join(OUTPUT_DIR, "marn_marketplace.csv")
    count = save_csv(partners, csv_path)

    # --- Stats ---
    with_loc = sum(1 for p in partners if p.get("location"))
    with_fees = sum(1 for p in partners if p.get("fees"))
    with_industry = sum(1 for p in partners if p.get("industry"))
    with_website = sum(1 for p in partners if p.get("website"))
    with_desc = sum(1 for p in partners if p.get("detail_description"))

    # Industry breakdown
    industry_counts = {}
    for p in partners:
        ind = p.get("industry", "").strip()
        if ind:
            industry_counts[ind] = industry_counts.get(ind, 0) + 1

    print(f"\n{'=' * 60}")
    print(f"  ✓ Saved {count} partners → {csv_path}")
    print(f"  Locations:     {with_loc}/{count}")
    print(f"  Fees:          {with_fees}/{count}")
    print(f"  Industries:    {with_industry}/{count}")
    print(f"  Websites:      {with_website}/{count}")
    print(f"  Descriptions:  {with_desc}/{count}")
    print(f"  Countries:     {', '.join(MARN_COUNTRIES)}")
    if industry_counts:
        print(f"\n  Industry Breakdown:")
        for ind, cnt in sorted(industry_counts.items(), key=lambda x: -x[1]):
            print(f"    {ind}: {cnt}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
