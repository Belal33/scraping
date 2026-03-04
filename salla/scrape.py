"""
Salla App Store Scraper
================================
Extracts all marketplace app partners from apps.salla.sa.

Uses the internal Salla Marketplace API:
  - Apps:       https://api.salla.dev/marketplace/v1/apps?page=N
  - Categories: https://api.salla.dev/marketplace/v1/categories

Phase 1: Fetch categories from the API.
Phase 2: Paginate through all apps (12 per page).
Phase 3: For each app, fetch its detail page for extended info.
Phase 4: Build the final CSV.

Dependencies: stdlib only (urllib, json, csv, os, time, re, sys).
"""
import csv
import json
import os
import re
import sys
import time
import urllib.request
import urllib.error

# ── Configuration ──────────────────────────────────────────────────────────
API_BASE = "https://api.salla.dev/marketplace/v1"
APPS_URL = f"{API_BASE}/apps"
CATEGORIES_URL = f"{API_BASE}/categories"
APP_DETAIL_URL = "https://apps.salla.sa/en/app"  # /en/app/{id}

PER_PAGE = 12  # API default, cannot be changed
RATE_LIMIT = 0.5  # seconds between API calls

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")

SALLA_COUNTRIES = ["Saudi Arabia"]


# ── HTTP helpers ───────────────────────────────────────────────────────────
def api_get(url, retries=3, timeout=30):
    """Make a GET request and return parsed JSON."""
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://apps.salla.sa/",
    }
    req = urllib.request.Request(url, headers=headers)
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
            if attempt < retries - 1:
                wait = 2 ** attempt
                print(f"    ⚠ Retry {attempt + 1}/{retries} for {url}: {e}")
                time.sleep(wait)
            else:
                print(f"    ✗ Failed after {retries} attempts: {url}")
                raise


def fetch_html(url, retries=3, timeout=30):
    """Fetch raw HTML from a URL."""
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Accept": "text/html",
        "Accept-Language": "en-US,en;q=0.9",
    }
    req = urllib.request.Request(url, headers=headers)
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8")
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
            if attempt < retries - 1:
                wait = 2 ** attempt
                print(f"    ⚠ Retry {attempt + 1}/{retries}: {e}")
                time.sleep(wait)
            else:
                return ""


# ── Phase 1: Fetch categories ────────────────────────────────────────────
def fetch_categories():
    """Fetch all categories from the API."""
    print("  Fetching categories...")
    data = api_get(CATEGORIES_URL)
    categories = data.get("data", [])
    cat_map = {}
    for cat in categories:
        slug = cat.get("slug", "")
        en_name = cat.get("name", {}).get("en", slug)
        cat_map[slug] = en_name
    print(f"  Found {len(cat_map)} categories")
    return cat_map


# ── Phase 2: Fetch all apps (paginated) ──────────────────────────────────
def fetch_all_apps():
    """Fetch all apps via the paginated API."""
    page = 1
    all_apps = []
    total_pages = None

    while True:
        url = f"{APPS_URL}?page={page}"
        print(f"  Page {page}" + (f"/{total_pages}" if total_pages else "") + "...", end="", flush=True)

        data = api_get(url)
        apps = data.get("data", [])
        pagination = data.get("pagination", {})

        if total_pages is None:
            total_pages = pagination.get("totalPages", 1)
            total_apps = pagination.get("total", 0)
            print(f" ({len(apps)} apps, {total_apps} total across {total_pages} pages)")
        else:
            print(f" ({len(apps)} apps)")

        all_apps.extend(apps)

        if page >= total_pages or not apps:
            break

        page += 1
        time.sleep(RATE_LIMIT)

    return all_apps


# ── Phase 3: Parse detail pages for extended info ─────────────────────────
def parse_detail_page(html):
    """Extract extended info from app detail page HTML."""
    detail = {}

    # Developer website
    website_match = re.search(
        r'<h6[^>]*>\s*Website\s*</h6>.*?<a[^>]*href="(https?://[^"]+)"[^>]*>\s*Homepage',
        html, re.DOTALL
    )
    detail["developer_url"] = website_match.group(1) if website_match else ""

    # Phone
    phone_match = re.search(r'href="tel:([^"]+)"', html)
    detail["developer_phone"] = phone_match.group(1) if phone_match else ""

    # Email
    email_match = re.search(r'href="mailto:([^"]+)"', html)
    detail["developer_email"] = email_match.group(1) if email_match else ""

    # Long description
    desc_match = re.search(
        r'<article class="entry-detail">(.*?)</article>', html, re.DOTALL
    )
    if desc_match:
        desc = re.sub(r'<[^>]+>', ' ', desc_match.group(1))
        desc = re.sub(r'\s+', ' ', desc).strip()
        detail["long_description"] = desc[:500]
    else:
        detail["long_description"] = ""

    return detail


def enrich_apps_with_details(apps_list, batch_size=10):
    """Fetch detail pages for each app and enrich with extra info."""
    enriched_count = 0
    total = len(apps_list)

    for i, app in enumerate(apps_list):
        app_id = app.get("id")
        if not app_id:
            continue

        url = f"{APP_DETAIL_URL}/{app_id}"
        pct = (i + 1) / total * 100
        print(f"\r  Detail [{i+1}/{total}] ({pct:.0f}%) {app.get('name', {}).get('en', '')}...", end="", flush=True)

        html = fetch_html(url)
        if html:
            detail = parse_detail_page(html)
            app.update(detail)
            enriched_count += 1

        time.sleep(RATE_LIMIT)

    print(f"\n  Enriched {enriched_count}/{total} apps with detail page info")


# ── Phase 4: Build pricing string from plans ─────────────────────────────
def extract_pricing(app):
    """Build a human-readable pricing string from API plan data."""
    plan_type = app.get("plan_type", "")
    plans = app.get("plans", [])
    trial = app.get("plan_trial")

    if plan_type == "free" or not plans:
        return "Free"

    parts = []
    for plan in plans:
        name_en = plan.get("name", {}).get("en", "")
        price = plan.get("price", 0)
        recurring = plan.get("recurring", "")
        old_price = plan.get("old_price")

        if recurring == "free":
            parts.append(f"{name_en}: Free")
        elif recurring == "one-time":
            parts.append(f"{name_en}: {price} SAR")
        else:
            parts.append(f"{name_en}: {price} SAR/{recurring}")

    pricing_str = " | ".join(parts) if parts else plan_type

    if trial:
        pricing_str = f"{trial}-day trial, {pricing_str}"

    return pricing_str


# ── Phase 5: Build and save CSV ───────────────────────────────────────────
def build_records(apps, categories_map):
    """Transform raw API app objects into CSV-ready records."""
    records = []
    seen_ids = set()

    for app in apps:
        app_id = app.get("id")
        if not app_id or app_id in seen_ids:
            continue
        seen_ids.add(app_id)

        # Name (prefer English)
        name_obj = app.get("name", {})
        name = name_obj.get("en", "") if isinstance(name_obj, dict) else str(name_obj)
        if not name.strip():
            continue

        # Categories
        cat_slugs = app.get("categories", [])
        cat_names = []
        for cat in cat_slugs:
            if isinstance(cat, dict):
                en = cat.get("name", {}).get("en", cat.get("slug", ""))
                cat_names.append(en)
            elif isinstance(cat, str):
                cat_names.append(categories_map.get(cat, cat))

        # Company / Developer
        company = app.get("company", {}) or {}
        company_name_raw = company.get("name", "")
        if isinstance(company_name_raw, str):
            # Decode unicode escapes if present
            try:
                company_name = company_name_raw.encode().decode("unicode_escape")
            except (UnicodeDecodeError, UnicodeEncodeError):
                company_name = company_name_raw
        else:
            company_name = company_name_raw

        # Description
        desc_obj = app.get("short_description", {})
        description = desc_obj.get("en", "") if isinstance(desc_obj, dict) else str(desc_obj)
        long_desc = app.get("long_description", "")
        if long_desc:
            description = long_desc

        # Logo
        logo = app.get("logo", {})
        logo_url = logo.get("url", "") if isinstance(logo, dict) else ""

        # Rating
        rating = app.get("rating", 0)
        reviews_count = app.get("reviews_count", 0)

        # Pricing
        pricing = extract_pricing(app)

        # Tags
        tags = []
        plan_type = app.get("plan_type", "")
        if plan_type == "free":
            tags.append("Free")
        elif plan_type == "recurring":
            tags.append("Paid")
            tags.append("Subscription")
        elif plan_type == "on_demand":
            tags.append("Paid")
            tags.append("On Demand")
        elif plan_type == "one_time":
            tags.append("Paid")
            tags.append("One-Time")
        if app.get("plan_trial"):
            tags.append("Free Trial")
        if app.get("one_click_installation"):
            tags.append("One-Click Install")

        records.append({
            "name": name.strip(),
            "slug": str(app_id),
            "url": f"https://apps.salla.sa/en/app/{app_id}",
            "logo_url": logo_url,
            "countries": "; ".join(SALLA_COUNTRIES),
            "categories": "; ".join(cat_names),
            "tags": "; ".join(tags),
            "description": description.strip(),
            "developer_name": company_name,
            "developer_id": str(company.get("id", "")),
            "developer_url": app.get("developer_url", ""),
            "developer_phone": app.get("developer_phone", ""),
            "developer_email": app.get("developer_email", ""),
            "avg_rating": str(rating) if rating else "",
            "total_ratings": str(reviews_count),
            "pricing": pricing,
        })

    return records


def save_csv(records, filepath):
    """Save records to CSV."""
    fieldnames = [
        "name", "slug", "url", "logo_url", "countries", "categories",
        "tags", "description", "developer_name", "developer_id",
        "developer_url", "developer_phone", "developer_email",
        "avg_rating", "total_ratings", "pricing",
    ]

    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(records)

    print(f"  ✓ Saved {len(records)} records → {filepath}")


# ── Main ──────────────────────────────────────────────────────────────────
def main():
    print("=" * 60)
    print("  Salla App Store Scraper")
    print("=" * 60)

    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Phase 1: Fetch categories
    print("\n[1/4] Fetching categories...")
    categories_map = fetch_categories()

    # Save categories
    cat_path = os.path.join(DATA_DIR, "categories.json")
    with open(cat_path, "w", encoding="utf-8") as f:
        json.dump(categories_map, f, indent=2, ensure_ascii=False)

    # Phase 2: Fetch all apps
    print("\n[2/4] Fetching all apps...")
    all_apps = fetch_all_apps()
    print(f"\n  Total apps fetched: {len(all_apps)}")

    # Save raw API data
    raw_path = os.path.join(DATA_DIR, "apps_raw.json")
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump(all_apps, f, indent=2, ensure_ascii=False)
    print(f"  Saved raw data → {raw_path}")

    # Phase 3: Enrich with detail pages (optional — can be slow)
    skip_details = "--skip-details" in sys.argv
    if not skip_details:
        print(f"\n[3/4] Fetching detail pages ({len(all_apps)} apps)...")
        print("  (Use --skip-details to skip this step)")
        enrich_apps_with_details(all_apps)

        enriched_path = os.path.join(DATA_DIR, "apps_enriched.json")
        with open(enriched_path, "w", encoding="utf-8") as f:
            json.dump(all_apps, f, indent=2, ensure_ascii=False)
    else:
        print("\n[3/4] Skipping detail page enrichment (--skip-details)")

    # Phase 4: Build CSV
    print("\n[4/4] Building CSV...")
    records = build_records(all_apps, categories_map)
    csv_path = os.path.join(OUTPUT_DIR, "salla_apps.csv")
    save_csv(records, csv_path)

    # ── Stats ──
    cat_counts = {}
    for r in records:
        for cat in r["categories"].split("; "):
            cat = cat.strip()
            if cat:
                cat_counts[cat] = cat_counts.get(cat, 0) + 1

    with_desc = sum(1 for r in records if r["description"])
    with_dev = sum(1 for r in records if r["developer_name"])
    with_email = sum(1 for r in records if r["developer_email"])
    free_apps = sum(1 for r in records if "Free" in r["tags"])
    paid_apps = sum(1 for r in records if "Paid" in r["tags"])
    trial_apps = sum(1 for r in records if "Free Trial" in r["tags"])

    print(f"\n{'=' * 60}")
    print(f"  ✓ COMPLETE: {len(records)} apps → {csv_path}")
    print(f"  Descriptions:  {with_desc}/{len(records)}")
    print(f"  Developers:    {with_dev}/{len(records)}")
    print(f"  Dev Emails:    {with_email}/{len(records)}")
    print(f"  Free:          {free_apps}")
    print(f"  Paid:          {paid_apps}")
    print(f"  Free Trial:    {trial_apps}")
    print(f"\n  Category Breakdown:")
    for cat, cnt in sorted(cat_counts.items(), key=lambda x: -x[1]):
        print(f"    {cat}: {cnt}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
