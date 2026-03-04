"""
Amazon SPN (Service Provider Network) Scraper
===============================================
Extracts service providers from Amazon's SPN directory.
https://sellercentral.amazon.com/gspn

Phase 1: Fetch page 1 HTML for each service category (cached to data/).
Phase 2: Parse provider cards from HTML using scrapling.Selector.
Phase 3: De-duplicate across categories, merge category lists.
Phase 4: Save to CSV.

Output: output/amazon_spn_providers.csv
"""
import csv
import json
import os
import re
import time
import html as html_mod

from scrapling.fetchers import Fetcher

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

BASE_URL = "https://sellercentral.amazon.com"
SELL_FROM = "US"
SELL_IN = "US"
LOCALE = "en_US"

# All 18 service categories from the SPN homepage
SERVICE_CATEGORIES = [
    "Account Management",
    "Accounting",
    "Advertising Optimization",
    "Cataloguing",
    "Compliance",
    "Enhanced Brand Content",
    "Excess Inventory",
    "FBA Preparation",
    "Imaging",
    "International Returns",
    "International Shipping",
    "IP Accelerator",
    "Manufacturing",
    "Storage",
    "Sustainability",
    "Taxes",
    "Training",
    "Translation",
]

# Star rating CSS class to numeric value mapping
def clean_text(text):
    """Normalize whitespace: replace newlines/tabs with spaces, collapse multiples."""
    return re.sub(r'\s+', ' ', text).strip()


STAR_RATING_MAP = {
    "a-star-5": 5.0,
    "a-star-4-5": 4.5,
    "a-star-4": 4.0,
    "a-star-3-5": 3.5,
    "a-star-3": 3.0,
    "a-star-2-5": 2.5,
    "a-star-2": 2.0,
    "a-star-1-5": 1.5,
    "a-star-1": 1.0,
    "a-star-0-5": 0.5,
    "a-star-0": 0.0,
}


def build_search_url(category):
    """Build the search page URL for a given service category."""
    from urllib.parse import quote
    cat_encoded = quote(category)
    return (
        f"{BASE_URL}/gspn/searchpage/{cat_encoded}"
        f"?sellFrom={SELL_FROM}&sellIn={SELL_IN}"
        f"&localeSelection={LOCALE}&sourcePage=HomePage"
    )


def cache_path(category):
    """Return the cache file path for a category."""
    safe_name = category.lower().replace(" ", "_")
    return os.path.join(DATA_DIR, f"{safe_name}.json")


# ---------------------------------------------------------------------------
# Phase 1: Fetch HTML (with caching)
# ---------------------------------------------------------------------------
def fetch_category(category, force=False):
    """Fetch the search results HTML for a category. Uses cache if available."""
    cp = cache_path(category)
    if not force and os.path.exists(cp):
        with open(cp, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("html", "")

    url = build_search_url(category)
    print(f"    Fetching: {url}")

    page = Fetcher.get(
        url,
        stealthy_headers=True,
        follow_redirects=True,
    )

    html_content = ""
    if page.status == 200:
        # The response body contains the raw HTML
        html_content = page.body.decode("utf-8", errors="replace") if isinstance(page.body, bytes) else str(page.body)
    else:
        print(f"    ⚠ HTTP {page.status}")
        return ""

    # Save cache
    with open(cp, "w", encoding="utf-8") as f:
        json.dump({"url": url, "category": category, "html": html_content}, f)

    time.sleep(1.5)  # Polite delay
    return html_content


# ---------------------------------------------------------------------------
# Phase 2: Parse provider cards
# ---------------------------------------------------------------------------
def extract_providers_from_html(html_content, category):
    """Parse provider cards from the search results HTML."""
    from scrapling import Selector
    page = Selector(html_content)
    providers = []

    # Find all provider card links
    for link in page.css("a.a-link-normal"):
        href = link.attrib.get("href", "")
        if "/gspn/provider-details/" not in href:
            continue

        card = link.css("div.provider-info-card")
        if not card:
            continue
        card = card[0]

        provider_id = card.attrib.get("data-providerid", "")
        if not provider_id:
            continue

        # --- Name ---
        name_el = card.css("span.a-size-medium.a-color-base")
        name = clean_text(name_el[0].get_all_text(strip=True)) if name_el else ""
        if not name:
            continue

        # --- Logo URL ---
        logo_el = card.css("img.provider-card-logo")
        logo_url = logo_el[0].attrib.get("src", "") if logo_el else ""

        # --- Price ---
        price_el = card.css("div.provider-card-price")
        price_text = ""
        if price_el:
            price_text = clean_text(price_el[0].get_all_text(strip=True))
            # Clean up: "Starts at USD 49.00 per month" -> "USD 49.00 per month"
            price_text = price_text.replace("Starts at", "").strip()

        # --- Star Rating ---
        rating = ""
        star_el = card.css("i.a-icon-star")
        if star_el:
            star_classes = star_el[0].attrib.get("class", "")
            for cls_name, val in STAR_RATING_MAP.items():
                if cls_name in star_classes:
                    rating = str(val)
                    break

        # --- Reviews & Requests received ---
        # Use regex on the card's raw HTML for reliability
        # The card HTML contains: "417<span...></span>Reviews" in rating-review divs
        reviews = ""
        requests_received = ""
        rating_divs = card.css("div.provider-card-rating-review")
        for rdiv in rating_divs:
            # Get the raw HTML of this div for regex matching
            raw_html = str(rdiv)
            text = clean_text(rdiv.get_all_text(strip=True))

            # Check for requests received
            if "requests received" in text.lower() or "requests received" in raw_html.lower():
                match = re.search(r'(\d[\d,]*)', text)
                if match:
                    requests_received = f"More than {match.group(1)}"
            # Check for reviews (pattern: NUMBER + Reviews in the HTML)
            elif "review" in text.lower() or "Review" in raw_html:
                # Try to extract from raw HTML first (more reliable)
                rev_match = re.search(r'>(\d[\d,]*)<', raw_html)
                if rev_match:
                    reviews = rev_match.group(1)
                else:
                    # Fallback to text
                    match = re.search(r'(\d[\d,]*)', text)
                    if match:
                        reviews = match.group(1)

        # --- Specialities (from title attribute) ---
        specialities = ""
        spec_div = card.css("div.specialitySection")
        if spec_div:
            parent = spec_div[0].parent
            if parent:
                specialities = parent.attrib.get("title", "")
            if not specialities:
                # Fallback: get text content
                specialities = spec_div[0].get_all_text(strip=True)
                specialities = specialities.replace("Specialities:", "").strip()

        # --- Badges ---
        badges = []
        badge_spans = card.css("span.badge-styling")
        for bs in badge_spans:
            classes = bs.attrib.get("class", "")
            if "aok-hidden" not in classes:
                badge_text = bs.get_all_text(strip=True)
                if badge_text:
                    badges.append(badge_text)

        # --- Detail URL ---
        detail_url = href
        if not detail_url.startswith("http"):
            detail_url = f"{BASE_URL}{detail_url}"
        # Unescape HTML entities
        detail_url = html_mod.unescape(detail_url)

        providers.append({
            "name": html_mod.unescape(name),
            "provider_id": provider_id,
            "url": detail_url,
            "logo_url": logo_url,
            "price": price_text,
            "rating": rating,
            "reviews": reviews,
            "requests_received": requests_received,
            "categories": category,
            "badges": "; ".join(badges),
            "specialities": clean_text(html_mod.unescape(specialities)) if specialities else "",
            "sell_from": SELL_FROM,
            "sell_in": SELL_IN,
        })

    return providers


# ---------------------------------------------------------------------------
# Phase 3: Merge & de-duplicate
# ---------------------------------------------------------------------------
def merge_providers(all_providers):
    """Merge providers across categories, combining category lists."""
    merged = {}
    for p in all_providers:
        pid = p["provider_id"]
        if pid in merged:
            # Add category to existing
            existing_cats = set(merged[pid]["categories"].split("; "))
            existing_cats.add(p["categories"])
            merged[pid]["categories"] = "; ".join(sorted(existing_cats))
        else:
            merged[pid] = dict(p)
    return list(merged.values())


# ---------------------------------------------------------------------------
# Phase 4: Save CSV
# ---------------------------------------------------------------------------
def save_csv(providers, filepath):
    """Save provider data to CSV."""
    fieldnames = [
        "name", "provider_id", "url", "logo_url", "price",
        "rating", "reviews", "requests_received", "categories",
        "badges", "specialities", "sell_from", "sell_in",
    ]
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for p in sorted(providers, key=lambda x: x["name"].lower()):
            writer.writerow(p)
    return len(providers)


# ---------------------------------------------------------------------------
# Extract total count from page
# ---------------------------------------------------------------------------
def extract_total_count(html_content):
    """Extract 'We found N providers' count from page."""
    match = re.search(r'We found\s+(\d[\d,]*)\s+providers?', html_content)
    if match:
        return int(match.group(1).replace(",", ""))
    return 0


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print("=" * 60)
    print("  Amazon SPN (Service Provider Network) Scraper")
    print("=" * 60)
    print(f"  Sell From: {SELL_FROM}")
    print(f"  Sell In:   {SELL_IN}")
    print(f"  Categories: {len(SERVICE_CATEGORIES)}")
    print()

    all_providers = []
    category_stats = {}

    for i, category in enumerate(SERVICE_CATEGORIES, 1):
        print(f"[{i}/{len(SERVICE_CATEGORIES)}] {category}...")

        try:
            html = fetch_category(category)
            if not html:
                print(f"    ⚠ No HTML received, skipping")
                continue

            total = extract_total_count(html)
            providers = extract_providers_from_html(html, category)
            category_stats[category] = {
                "total_available": total,
                "extracted": len(providers),
            }
            print(f"    Found {len(providers)} on page 1 (of {total} total)")
            all_providers.extend(providers)

        except Exception as e:
            print(f"    ❌ Error: {e}")
            category_stats[category] = {"total_available": 0, "extracted": 0}

    # --- Merge ---
    print(f"\n{'=' * 60}")
    print(f"  Merging & de-duplicating...")
    merged = merge_providers(all_providers)
    print(f"  Total raw: {len(all_providers)}")
    print(f"  Unique providers: {len(merged)}")

    if not merged:
        print("❌ No providers found!")
        return

    # --- Save CSV ---
    csv_path = os.path.join(OUTPUT_DIR, "amazon_spn_providers.csv")
    count = save_csv(merged, csv_path)

    # --- Save stats ---
    stats_path = os.path.join(DATA_DIR, "category_stats.json")
    with open(stats_path, "w") as f:
        json.dump(category_stats, f, indent=2)

    # --- Summary ---
    print(f"\n{'=' * 60}")
    print(f"  ✓ Saved {count} unique providers → {csv_path}")
    print(f"\n  Category Breakdown:")
    for cat, stats in sorted(category_stats.items()):
        print(f"    {cat}: {stats['extracted']}/{stats['total_available']}")

    # Multi-category providers
    multi_cat = sum(1 for p in merged if "; " in p["categories"])
    with_rating = sum(1 for p in merged if p["rating"])
    with_reviews = sum(1 for p in merged if p["reviews"])
    print(f"\n  Multi-category providers: {multi_cat}")
    print(f"  With ratings: {with_rating}/{count}")
    print(f"  With reviews: {with_reviews}/{count}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
