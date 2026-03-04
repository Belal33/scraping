"""
Foodics Marketplace Scraper
================================
Extracts all marketplace app partners from foodics.com/marketplace.

Phase 1: Load cached HTML from data/foodics_page_raw.json (MCP-fetched).
Phase 2: Parse partner cards from article.elementor-post elements.
Phase 3: Extract filter categories from jet-radio-list inputs.
Phase 4: Save to CSV.

Output: output/foodics_marketplace.csv
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

BASE_URL = "https://www.foodics.com"
MARKETPLACE_URL = f"{BASE_URL}/marketplace/"

# Map CSS class suffixes to human-readable category names
CATEGORY_MAP = {
    "accounting": "Accounting",
    "chat-bot": "Chat Bot",
    "delivery-management": "Delivery Management",
    "digital-menu": "Digital Menu",
    "digital-receipts": "Digital Receipts",
    "digital-signage": "Digital Signage",
    "erp": "ERP",
    "food-aggregator": "Food Aggregator",
    "inventory-management": "Inventory Management",
    "loyalty": "Loyalty",
    "online-ordering": "Online Ordering",
    "ordering-platforms-management": "Ordering Platforms Management",
    "table-payments": "Table Payments",
    "table-reservation": "Table Reservation",
}

# Foodics operating countries (from site header)
FOODICS_COUNTRIES = [
    "Saudi Arabia", "United Arab Emirates", "Egypt", "Kuwait", "Jordan",
]


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
# Phase 2: Extract partner apps from HTML
# ---------------------------------------------------------------------------
def extract_partners(html):
    """Parse partner apps from article.elementor-post elements."""
    page = Selector(html, url=MARKETPLACE_URL)
    partners = []
    seen = set()

    for article in page.css("article.elementor-post"):
        classes = article.attrib.get("class", "")

        # --- Name ---
        title_el = article.css("h3.elementor-post__title a")
        if not title_el:
            continue
        name = title_el[0].get_all_text(strip=True)
        if not name or name in seen:
            continue
        seen.add(name)

        # --- URL & Slug ---
        href = title_el[0].attrib.get("href", "")
        slug_match = re.search(r"/portfolio/([^/]+)/?$", href)
        slug = slug_match.group(1) if slug_match else name.lower().replace(" ", "-")
        url = href if href.startswith("http") else f"{BASE_URL}{href}"

        # --- Logo URL ---
        img = article.css(".elementor-post__thumbnail img")
        logo_url = ""
        if img:
            logo_url = img[0].attrib.get("src", "")

        # --- Categories from CSS classes ---
        categories = []
        for cls_suffix, cat_name in CATEGORY_MAP.items():
            if f"portfolio-types-{cls_suffix}" in classes:
                categories.append(cat_name)

        # --- Description ---
        desc_el = article.css(".elementor-post__excerpt p")
        description = ""
        if desc_el:
            description = desc_el[0].get_all_text(strip=True)
        if not description:
            # Fallback to div text
            desc_div = article.css(".elementor-post__excerpt")
            if desc_div:
                description = desc_div[0].get_all_text(strip=True)

        partners.append({
            "name": name,
            "slug": slug,
            "url": url,
            "logo_url": logo_url,
            "countries": "; ".join(FOODICS_COUNTRIES),
            "categories": "; ".join(categories),
            "tags": "",
            "description": description[:500] if description else "",
        })

    return partners


# ---------------------------------------------------------------------------
# Phase 3: Extract filter categories
# ---------------------------------------------------------------------------
def extract_filters(html):
    """Extract available category filter options from JetSmartFilters."""
    page = Selector(html, url=MARKETPLACE_URL)
    filters = {"categories": []}

    for radio in page.css(".jet-radio-list__input"):
        label = radio.attrib.get("data-label", "")
        if label and label != "All":
            filters["categories"].append(label)

    return filters


# ---------------------------------------------------------------------------
# Save CSV
# ---------------------------------------------------------------------------
def save_csv(partners, filepath):
    """Save partner data to CSV matching standard format."""
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
    print("  Foodics Marketplace Scraper")
    print("=" * 60)

    html_file = os.path.join(DATA_DIR, "foodics_page_raw.json")
    if not os.path.exists(html_file):
        print(f"\nERROR: Cached HTML not found at {html_file}")
        print("Please fetch the page first using Scrapling MCP fetch")
        print(f"and save the output to {html_file}")
        return

    # --- Load HTML ---
    print("\n[1/3] Loading cached HTML...")
    html = load_html(html_file)
    print(f"      HTML size: {len(html):,} chars")

    # --- Extract partners ---
    print("\n[2/3] Extracting marketplace apps...")
    partners = extract_partners(html)
    print(f"      Found {len(partners)} unique apps")

    if not partners:
        print("ERROR: No apps found!")
        return

    # --- Extract filters ---
    filters = extract_filters(html)
    cats = filters["categories"]
    print(f"      Categories ({len(cats)}): {', '.join(cats)}")

    # Save partner list for reference
    with open(os.path.join(DATA_DIR, "partner_slugs.json"), "w") as f:
        json.dump([{"name": p["name"], "slug": p["slug"]} for p in partners], f, indent=2)

    # --- Stats ---
    with_cat = sum(1 for p in partners if p["categories"])
    with_desc = sum(1 for p in partners if p["description"])

    # Category breakdown
    cat_counts = {}
    for p in partners:
        for c in p["categories"].split("; "):
            if c:
                cat_counts[c] = cat_counts.get(c, 0) + 1

    # --- Save ---
    print("\n[3/3] Saving CSV...")
    csv_path = os.path.join(OUTPUT_DIR, "foodics_marketplace.csv")
    count = save_csv(partners, csv_path)

    # --- Summary ---
    print(f"\n{'=' * 60}")
    print(f"  ✓ Saved {count} apps → {csv_path}")
    print(f"  Categories:    {with_cat}/{count}")
    print(f"  Descriptions:  {with_desc}/{count}")
    print(f"  Countries:     {', '.join(FOODICS_COUNTRIES)}")
    print(f"\n  Category Breakdown:")
    for cat, cnt in sorted(cat_counts.items(), key=lambda x: -x[1]):
        print(f"    {cat}: {cnt}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
