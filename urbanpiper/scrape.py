"""
UrbanPiper Integrations Scraper
================================
Extracts all integration partner details from urbanpiper.com/integrations.

Phase 1: Fetch the full JS-rendered integrations page via Scrapling MCP
         and save the HTML locally for parsing.
Phase 2: Parse partner cards from cached HTML using scrapling Selector.
Phase 3: Extract filter options (categories, countries) from the page.

Output: output/urbanpiper_integrations.csv
"""
import csv
import json
import os
import re
from scrapling import Selector

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

BASE_URL = "https://www.urbanpiper.com"
INTEGRATIONS_URL = f"{BASE_URL}/integrations"

# Known categories on the page
VALID_CATEGORIES = {
    "POS Systems", "Fulfilment", "Delivery platforms",
    "Online Ordering", "Delivery Platforms", "Online ordering",
    "POS Sytems",  # typo on their site
}

# Known countries
KNOWN_COUNTRIES = {
    "Australia", "Bahrain", "Belgium", "Canada", "Chile", "Colombia",
    "Egypt", "Global", "India", "Ireland", "Jordan", "Kenya", "Kuwait",
    "Mexico", "Oman", "Qatar", "Saudi Arabia", "Sri Lanka",
    "United Arab Emirates", "United Kingdom", "United States",
}


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
# Phase 2: Extract partner cards from HTML
# ---------------------------------------------------------------------------
def extract_partners(html):
    """Parse partner cards from the Webflow CMS HTML structure."""
    page = Selector(html, url=INTEGRATIONS_URL)
    partners = []
    seen = set()

    for item in page.css(".integration-collection-list-item-search"):
        # --- Name ---
        name_el = item.css(".integration-grid-name-v1")
        name = name_el[0].get_all_text(strip=True) if name_el else ""
        if not name or name in seen:
            continue
        seen.add(name)

        # --- Logo URL ---
        img = item.css(".integration-grid-image-v1")
        logo_url = img[0].attrib.get("src", "") if img else ""

        # --- Categories ---
        cat_els = item.css('.integration-grid-system-v1')
        categories = []
        for el in cat_els:
            classes = el.attrib.get("class", "")
            # Skip invisible/empty category slots
            if "w-condition-invisible" in classes or "w-dyn-bind-empty" in classes:
                continue
            text = el.get_all_text(strip=True)
            if text and text in VALID_CATEGORIES:
                categories.append(text)
        # Deduplicate
        categories = list(dict.fromkeys(categories))

        # Also check the non-v1 category field
        cat_fallback = item.css('.integration-grid-system')
        for el in cat_fallback:
            classes = el.attrib.get("class", "")
            if "w-dyn-bind-empty" in classes:
                continue
            text = el.get_all_text(strip=True)
            if text and text in VALID_CATEGORIES and text not in categories:
                categories.append(text)

        # --- Status ---
        status_el = item.css(".integration-grid-status")
        status = status_el[0].get_all_text(strip=True) if status_el else ""

        # --- Countries ---
        country_els = item.css(".integration-country-names")
        countries = []
        for el in country_els:
            text = el.get_all_text(strip=True)
            if text and text != "No items found.":
                countries.append(text)

        # --- Is Global ---
        is_global = "Global" in countries

        # --- Slug ---
        slug = name.lower()
        for ch in [" ", "/", "(", ")"]:
            slug = slug.replace(ch, "-")
        slug = re.sub(r"-+", "-", slug).strip("-")

        partners.append({
            "name": name,
            "slug": slug,
            "url": INTEGRATIONS_URL,
            "logo_url": logo_url,
            "countries": "; ".join(countries),
            "categories": "; ".join(categories),
            "tags": status,
            "description": "",
        })

    return partners


# ---------------------------------------------------------------------------
# Phase 3: Extract filter options
# ---------------------------------------------------------------------------
def extract_filters(html):
    """Extract available category and country filter options."""
    page = Selector(html, url=INTEGRATIONS_URL)
    filters = {"categories": [], "countries": []}

    # Categories from filter
    for el in page.css(".integration-filter-categories"):
        for btn in el.css("a, div[fs-cmsfilter-field]"):
            text = btn.get_all_text(strip=True)
            if text and text not in ("All Integrations", "Select here..", "All countries", ""):
                if text in VALID_CATEGORIES and text not in filters["categories"]:
                    filters["categories"].append(text)
                elif text in KNOWN_COUNTRIES and text not in filters["countries"]:
                    filters["countries"].append(text)

    # If countries not found in filter, extract from the partner cards
    if not filters["countries"]:
        for el in page.css(".integration-country-names"):
            text = el.get_all_text(strip=True)
            if text and text in KNOWN_COUNTRIES and text not in filters["countries"]:
                filters["countries"].append(text)

    return filters


# ---------------------------------------------------------------------------
# Save CSV
# ---------------------------------------------------------------------------
def save_csv(partners, filepath):
    """Save partner data to CSV matching deliverect format."""
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
    print("  UrbanPiper Integrations Scraper")
    print("=" * 60)

    html_file = os.path.join(DATA_DIR, "urbanpiper_page_raw.json")
    if not os.path.exists(html_file):
        print(f"\nERROR: Cached HTML not found at {html_file}")
        print("Please fetch the page first using Scrapling MCP fetch/stealthy_fetch")
        print(f"and save the output to {html_file}")
        return

    # --- Load HTML ---
    print("\n[1/3] Loading cached HTML...")
    html = load_html(html_file)
    print(f"      HTML size: {len(html):,} chars")

    # --- Extract partners ---
    print("\n[2/3] Extracting partner cards...")
    partners = extract_partners(html)
    print(f"      Found {len(partners)} unique partners")

    if not partners:
        print("ERROR: No partners found!")
        return

    # --- Extract filters ---
    filters = extract_filters(html)
    cats = filters["categories"]
    countries = filters["countries"]
    print(f"      Categories ({len(cats)}): {', '.join(cats)}")
    print(f"      Countries ({len(countries)}): {', '.join(countries)}")

    # Save partner slugs for reference
    with open(os.path.join(DATA_DIR, "partner_slugs.json"), "w") as f:
        json.dump([{"name": p["name"], "slug": p["slug"]} for p in partners], f, indent=2)

    # --- Stats ---
    with_cat = sum(1 for p in partners if p["categories"])
    with_country = sum(1 for p in partners if p["countries"])
    live = sum(1 for p in partners if "Live" in p["tags"])
    upcoming = sum(1 for p in partners if "Upcoming" in p["tags"])

    # --- Save ---
    print("\n[3/3] Saving CSV...")
    csv_path = os.path.join(OUTPUT_DIR, "urbanpiper_integrations.csv")
    count = save_csv(partners, csv_path)

    # --- Summary ---
    print(f"\n{'=' * 60}")
    print(f"  ✓ Saved {count} partners → {csv_path}")
    print(f"  Categories:   {with_cat}/{count}")
    print(f"  Countries:    {with_country}/{count}")
    print(f"  Live:         {live}")
    print(f"  Upcoming:     {upcoming}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
