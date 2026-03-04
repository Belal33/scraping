"""
Deliverect Integrations Scraper
================================
Extracts all integration partner details from deliverect.com/en/integrations.

Phase 1: Fetch the full JS-rendered integrations page via Scrapling MCP
         and save the HTML locally for parsing.
Phase 2: Parse partner slugs from cached HTML using scrapling Selector.
Phase 3: Fetch each partner detail page via HTTP for descriptions.
Phase 4: Enrich with categories and countries from filter sections.

Output: output/deliverect_integrations.csv
"""
import csv
import json
import os
import re
import time
from scrapling import Selector
from scrapling.fetchers import Fetcher

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

BASE_URL = "https://www.deliverect.com"
INTEGRATIONS_URL = f"{BASE_URL}/en/integrations"

# Category slugs to skip (these are filter pages, not partner pages)
SKIP_SLUGS = {
    "pos-systems", "delivery-channels", "online-ordering",
    "in-house-dining-apps", "fulfilment", "loyalty", "retail",
    "on-site-ordering", "inventory-management", "analytics",
    "payments", "kiosk", "digital-signage", "restaurant-ai-integrations",
}

# Rate limit between HTTP requests (seconds)
RATE_LIMIT = 0.3


# ---------------------------------------------------------------------------
# Phase 1 & 2: Extract partner slugs from cached HTML
# ---------------------------------------------------------------------------
def extract_partners_from_html(html_file):
    """Parse partner slugs from the MCP-fetched JS-rendered HTML."""
    with open(html_file, "r", encoding="utf-8") as f:
        raw = f.read()

    # Handle MCP JSON wrapper: {"status": 200, "content": ["<html>..."]}
    try:
        data = json.loads(raw)
        html = data["content"][0] if isinstance(data.get("content"), list) else data.get("content", raw)
    except (json.JSONDecodeError, KeyError):
        html = raw

    page = Selector(html, url=INTEGRATIONS_URL)

    partners = []
    seen = set()

    for item in page.css(".c-search__item"):
        link = item.css("a.c-search-result")
        if not link:
            continue
        link = link[0]

        href = link.attrib.get("href", "")
        match = re.match(r"^/en/integrations/([a-zA-Z0-9][a-zA-Z0-9\-]*)$", href)
        if not match:
            continue

        slug = match.group(1)
        if slug in SKIP_SLUGS or slug in seen:
            continue
        seen.add(slug)

        # Name from img alt/title or text
        img = link.css("img")
        name = ""
        logo_url = ""
        if img:
            name = img[0].attrib.get("alt", "") or img[0].attrib.get("title", "")
            logo_url = img[0].attrib.get("src", "")
        if not name:
            name = link.get_all_text(strip=True)

        partners.append({
            "name": name.strip(),
            "slug": slug,
            "logo_url": logo_url,
        })

    return partners


def extract_filters_from_html(html_file):
    """Extract category and country filter options from the cached HTML."""
    with open(html_file, "r", encoding="utf-8") as f:
        raw = f.read()

    try:
        data = json.loads(raw)
        html = data["content"][0] if isinstance(data.get("content"), list) else data.get("content", raw)
    except (json.JSONDecodeError, KeyError):
        html = raw

    page = Selector(html, url=INTEGRATIONS_URL)
    filters = {"categories": [], "countries": []}

    for fs in page.css(".c-filter"):
        title_el = fs.css(".c-filter__title")
        if not title_el:
            continue
        title = title_el[0].get_all_text(strip=True)

        items = []
        for b in fs.css("button, a"):
            text = b.get_all_text(strip=True)
            if text and text != title and text != "All integrations":
                items.append(text)

        if "Categor" in title:
            filters["categories"] = items
        elif "Countr" in title:
            filters["countries"] = items

    return filters


# ---------------------------------------------------------------------------
# Phase 3: Fetch partner detail pages for descriptions
# ---------------------------------------------------------------------------
def fetch_partner_description(slug):
    """Fetch a partner detail page and extract description from __NEXT_DATA__."""
    url = f"{BASE_URL}/en/integrations/{slug}"
    try:
        page = Fetcher.get(url)
        if page.status != 200:
            return ""

        script_text = page.css("script#__NEXT_DATA__::text").get()
        if not script_text:
            return ""

        nd = json.loads(script_text)
        meta = nd.get("props", {}).get("pageProps", {}).get("page", {}).get("metaTags", {})
        return meta.get("description", "")

    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Phase 4: Save CSV
# ---------------------------------------------------------------------------
def save_csv(partners, filepath):
    """Save enriched partner data to CSV."""
    fieldnames = ["name", "slug", "url", "logo_url", "countries", "categories", "tags", "description"]

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
    print("  Deliverect Integrations Scraper")
    print("=" * 60)

    html_file = os.path.join(DATA_DIR, "deliverect_page_raw.json")
    if not os.path.exists(html_file):
        print(f"\nERROR: Cached HTML not found at {html_file}")
        print("Please fetch the page first using Scrapling MCP stealthy_fetch")
        print(f"and save the output to {html_file}")
        return

    # --- Phase 1+2: Extract partners and filters ---
    print("\n[1/4] Extracting partners from cached HTML...")
    partners = extract_partners_from_html(html_file)
    print(f"      Found {len(partners)} unique partners")

    print("\n[2/4] Extracting filter categories and countries...")
    filters = extract_filters_from_html(html_file)
    print(f"      Categories ({len(filters['categories'])}): {', '.join(filters['categories'])}")
    print(f"      Countries ({len(filters['countries'])}): {', '.join(filters['countries'])}")

    if not partners:
        print("ERROR: No partners found!")
        return

    # Save slugs for reference
    with open(os.path.join(DATA_DIR, "partner_slugs.json"), "w") as f:
        json.dump(partners, f, indent=2)

    # --- Phase 3: Fetch descriptions ---
    print(f"\n[3/4] Fetching descriptions for {len(partners)} partners...")
    countries_str = "; ".join(filters["countries"])
    categories_str = "; ".join(filters["categories"])
    enriched = []
    errors = 0

    for i, p in enumerate(partners):
        slug = p["slug"]
        print(f"      [{i+1}/{len(partners)}] {p['name']}", end="", flush=True)

        desc = fetch_partner_description(slug)
        enriched.append({
            "name": p["name"],
            "slug": slug,
            "url": f"{BASE_URL}/en/integrations/{slug}",
            "logo_url": p["logo_url"],
            "countries": countries_str,
            "categories": categories_str,
            "tags": "",
            "description": desc[:500] if desc else "",
        })

        if desc:
            print(" ✓")
        else:
            print(" ~")
            errors += 1

        if i < len(partners) - 1:
            time.sleep(RATE_LIMIT)

    print(f"      Done: {len(partners) - errors} with desc, {errors} without")

    # --- Phase 4: Save ---
    print("\n[4/4] Saving CSV...")
    csv_path = os.path.join(OUTPUT_DIR, "deliverect_integrations.csv")
    count = save_csv(enriched, csv_path)

    # --- Summary ---
    print(f"\n{'=' * 60}")
    print(f"  ✓ Saved {count} partners → {csv_path}")
    with_d = sum(1 for p in enriched if p["description"])
    print(f"  Descriptions: {with_d}/{count}")
    print(f"  Categories:   {len(filters['categories'])}")
    print(f"  Countries:    {len(filters['countries'])}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
