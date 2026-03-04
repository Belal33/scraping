"""
Zid App Market Scraper
================================
Extracts all marketplace app partners from apps.zid.sa/en/applications.

Phase 1: Fetch categories from the Zid public API.
Phase 2: Fetch all apps from the Zid public API (paginated, 100 per page).
Phase 3: Fetch app detail pages for extended descriptions (optional).
Phase 4: Merge data and save to CSV.

API Base: https://api.zid.sa/v1/market/public/
Endpoints:
  - /categories  → list of app categories
  - /apps?page=N&per_page=M&lang=en → paginated app list

Output: output/zid_apps.csv
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

API_BASE = "https://api.zid.sa/v1/market/public"
CATEGORIES_URL = f"{API_BASE}/categories"
APPS_URL = f"{API_BASE}/apps"
APP_DETAIL_URL = "https://apps.zid.sa/en/application"  # /en/application/{id}

PER_PAGE = 100
RATE_LIMIT = 0.5  # seconds between API calls

# Category ID → English name mapping (from page HTML)
CATEGORY_EN_NAMES = {
    5: "Shipping & Fulfilment",
    13: "Mobile Apps",
    10: "Marketing",
    9: "Customer Support",
    2: "Accounting",
    1: "Inventory Management",
    4: "Analytics & Reporting",
    11: "Productivity",
    6: "Finding Products",
    12: "Payments",
    8: "Operations",
    14: "Campaign Tracking",
    15: "Sales Channels",
}

# Zid's operating country
ZID_COUNTRIES = ["Saudi Arabia"]


# ---------------------------------------------------------------------------
# HTTP helpers (using stdlib to avoid dependency on requests)
# ---------------------------------------------------------------------------
def api_get(url, retries=3, timeout=30):
    """Make a GET request and return parsed JSON."""
    headers = {
        "Accept": "application/json",
        "Accept-Language": "en",
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
    }
    req = urllib.request.Request(url, headers=headers)

    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
            if attempt < retries - 1:
                print(f"      Retry {attempt + 1}/{retries}: {e}")
                time.sleep(2 ** attempt)
            else:
                raise


# ---------------------------------------------------------------------------
# Phase 1: Fetch categories
# ---------------------------------------------------------------------------
def fetch_categories():
    """Fetch all categories from the API."""
    data = api_get(CATEGORIES_URL)
    raw_cats = data.get("categories", {}).get("apps_by_category", [])

    categories = []
    for cat in raw_cats:
        cat_id = cat["id"]
        categories.append({
            "id": cat_id,
            "name_ar": cat["name"],
            "name_en": CATEGORY_EN_NAMES.get(cat_id, cat["name"]),
            "app_count": cat["application_count"],
        })

    return categories


# ---------------------------------------------------------------------------
# Phase 2: Fetch all apps (paginated)
# ---------------------------------------------------------------------------
def fetch_all_apps():
    """Fetch all apps from the API.

    The Zid API returns all apps in a single response regardless of per_page,
    so we make one request with a large per_page. If future API changes add
    real pagination, we handle that gracefully.
    """
    all_apps = []
    page = 1
    max_pages = 20  # Safety limit

    while page <= max_pages:
        url = f"{APPS_URL}?page={page}&per_page=1000&lang=en"
        print(f"      Fetching page {page}...", end="", flush=True)

        data = api_get(url, timeout=60)
        apps = data.get("apps", [])

        if not apps:
            print(" (empty, done)")
            break

        # Deduplicate by ID against already-fetched apps
        existing_ids = {a["id"] for a in all_apps}
        new_apps = [a for a in apps if a.get("id") not in existing_ids]

        if not new_apps:
            print(" (no new apps, done)")
            break

        all_apps.extend(new_apps)
        print(f" got {len(new_apps)} new apps (total: {len(all_apps)})")

        # If we got significantly fewer than expected, we're probably done
        if len(apps) < 500:
            break

        page += 1
        time.sleep(RATE_LIMIT)

    return all_apps


# ---------------------------------------------------------------------------
# Phase 3: Clean & parse pricing from HTML plan string
# ---------------------------------------------------------------------------
def clean_price(plan_html):
    """Extract clean pricing text from HTML plan string."""
    if not plan_html:
        return ""
    # Remove HTML tags
    clean = re.sub(r"<[^>]+>", "", plan_html)
    # Normalize whitespace
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean


# ---------------------------------------------------------------------------
# Phase 4: Build and save CSV
# ---------------------------------------------------------------------------
def build_records(apps, categories_map):
    """Transform raw API app objects into CSV-ready records."""
    records = []
    seen = set()

    for app in apps:
        app_id = app.get("id")
        if not app_id or app_id in seen:
            continue
        seen.add(app_id)

        name = app.get("name", "").strip()
        if not name:
            continue

        # Developer details
        developer = app.get("developer", {}) or {}
        developer_name = developer.get("name", app.get("developer_name", ""))
        developer_email = developer.get("email", "")
        developer_url = developer.get("url", "")
        developer_phone = developer.get("phone", "")

        # Category
        category_raw = app.get("category", "")

        # Rate
        rate_info = app.get("rate", {}) or {}
        avg_rate = rate_info.get("avg_rate", "")
        total_ratings = rate_info.get("total_rating", "")

        # Pricing
        plan_raw = app.get("plan", "")
        plan_text = clean_price(plan_raw)
        plan_discount = app.get("plan_discount")
        discount_str = f"{plan_discount}% discount" if plan_discount else ""

        # URLs
        icon_url = app.get("icon", "")
        app_page_url = f"https://apps.zid.sa/en/application/{app_id}"

        # Description
        short_desc = app.get("short_description", "")
        full_desc = app.get("public_description", "")
        description = full_desc[:500] if full_desc else short_desc

        # Tags: free/paid + trial info
        tags = []
        if app.get("plan_type") == 1 or "Free" in plan_text:
            tags.append("Free")
        elif app.get("plan_type") == 2:
            tags.append("Paid")
        if "Trial" in plan_text:
            tags.append("Trial")
        if app.get("is_featured"):
            tags.append("Featured")
        if app.get("is_embedded"):
            tags.append("Embedded")
        if discount_str:
            tags.append(discount_str)

        records.append({
            "name": name,
            "slug": str(app_id),
            "url": app_page_url,
            "logo_url": icon_url,
            "countries": "; ".join(ZID_COUNTRIES),
            "categories": category_raw,
            "tags": "; ".join(tags),
            "description": description,
            "developer_name": developer_name,
            "developer_email": developer_email,
            "developer_url": developer_url,
            "developer_phone": developer_phone,
            "avg_rating": avg_rate,
            "total_ratings": total_ratings,
            "pricing": plan_text,
        })

    return records


def save_csv(records, filepath):
    """Save records to CSV."""
    fieldnames = [
        "name", "slug", "url", "logo_url", "countries", "categories",
        "tags", "description", "developer_name", "developer_email",
        "developer_url", "developer_phone", "avg_rating", "total_ratings",
        "pricing",
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
    print("  Zid App Market Scraper")
    print("=" * 60)

    # --- Phase 1: Categories ---
    print("\n[1/4] Fetching categories...")
    categories = fetch_categories()
    categories_map = {c["id"]: c for c in categories}
    print(f"      Found {len(categories)} categories:")
    for c in categories:
        print(f"        {c['name_en']} ({c['app_count']} apps)")

    # Save categories for reference
    with open(os.path.join(DATA_DIR, "categories.json"), "w", encoding="utf-8") as f:
        json.dump(categories, f, indent=2, ensure_ascii=False)

    # --- Phase 2: Fetch all apps ---
    print(f"\n[2/4] Fetching all apps from API...")
    apps = fetch_all_apps()
    print(f"      Total apps fetched: {len(apps)}")

    if not apps:
        print("ERROR: No apps found!")
        return

    # Save raw API data for reference
    with open(os.path.join(DATA_DIR, "apps_raw.json"), "w", encoding="utf-8") as f:
        json.dump(apps, f, indent=2, ensure_ascii=False)

    # --- Phase 3: Build records ---
    print("\n[3/4] Processing app data...")
    records = build_records(apps, categories_map)
    print(f"      Processed {len(records)} unique apps")

    # --- Phase 4: Save ---
    print("\n[4/4] Saving CSV...")
    csv_path = os.path.join(OUTPUT_DIR, "zid_apps.csv")
    count = save_csv(records, csv_path)

    # --- Stats ---
    cat_counts = {}
    for r in records:
        cat = r["categories"]
        if cat:
            cat_counts[cat] = cat_counts.get(cat, 0) + 1

    with_desc = sum(1 for r in records if r["description"])
    with_dev = sum(1 for r in records if r["developer_name"])
    with_rating = sum(1 for r in records if r["avg_rating"])
    free_apps = sum(1 for r in records if "Free" in r["tags"])
    paid_apps = sum(1 for r in records if "Paid" in r["tags"])

    # --- Summary ---
    print(f"\n{'=' * 60}")
    print(f"  ✓ Saved {count} apps → {csv_path}")
    print(f"  Descriptions:  {with_desc}/{count}")
    print(f"  Developers:    {with_dev}/{count}")
    print(f"  Ratings:       {with_rating}/{count}")
    print(f"  Free:          {free_apps}")
    print(f"  Paid:          {paid_apps}")
    print(f"  Countries:     {', '.join(ZID_COUNTRIES)}")
    print(f"\n  Category Breakdown:")
    for cat, cnt in sorted(cat_counts.items(), key=lambda x: -x[1]):
        print(f"    {cat}: {cnt}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
