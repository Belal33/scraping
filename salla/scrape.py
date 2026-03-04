"""
Helper script to extract apps from MCP-fetched HTML pages.
Reads the saved MCP response files, parses them, and saves the results.

This is the step 1 of the scraping pipeline:
  1. Fetch pages via MCP → save as mcp_pages_*.json
  2. Run this script → produces data/apps_listing.json
  3. Fetch detail pages via MCP → save as mcp_details_*.json  
  4. Run scrape.py --parse → produces output/salla_apps.csv
"""
import json
import os
import re
import sys
import glob

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")


def unescape_html(text):
    """Unescape common HTML entities."""
    text = text.replace("&amp;", "&")
    text = text.replace("&lt;", "<")
    text = text.replace("&gt;", ">")
    text = text.replace("&quot;", '"')
    text = text.replace("&#39;", "'")
    text = text.replace("&nbsp;", " ")
    return text.strip()


def parse_listing_apps(html):
    """Parse app cards from listing page HTML."""
    apps = []
    app_blocks = re.split(r'<div class="app-item\s', html)

    for block in app_blocks[1:]:
        app = {}

        # App ID
        id_match = re.search(r'href="/en/app/(\d+)\?category=all"', block)
        if not id_match:
            id_match = re.search(r'href="/en/app/(\d+)', block)
        if not id_match:
            continue

        app_id = id_match.group(1)
        app["id"] = app_id
        app["url"] = f"https://apps.salla.sa/en/app/{app_id}"

        # Name
        name_match = re.search(
            r'<h2[^>]*>.*?<a[^>]*>.*?<span>(.*?)</span>', block, re.DOTALL
        )
        app["name"] = unescape_html(name_match.group(1)) if name_match else ""

        # Logo
        logo_match = re.search(
            r'class="appLogo[^"]*"[^>]*style=\'[^\']*url\("([^"]+)"\)', block
        )
        app["logo_url"] = logo_match.group(1) if logo_match else ""

        # Developer
        dev_match = re.search(r'href="/en/company/(\d+)"[^>]*>(.*?)</a>', block)
        if dev_match:
            app["developer_id"] = dev_match.group(1)
            app["developer_name"] = unescape_html(dev_match.group(2))
        else:
            app["developer_id"] = ""
            app["developer_name"] = ""

        # Pricing
        price_match = re.search(
            r'<div class="[^"]*text-sm leading-5 text-gray-500[^"]*">\s*<span>(.*?)</span>',
            block, re.DOTALL
        )
        if price_match:
            price_text = re.sub(r'<[^>]+>', '', price_match.group(1))
            app["pricing"] = unescape_html(price_text.strip())
        else:
            app["pricing"] = ""

        # Rating
        yellow_stars = len(re.findall(r'sicon-star2[^"]*text-yellow-400', block))
        app["avg_rating"] = str(yellow_stars) if yellow_stars > 0 else ""

        ratings_match = re.search(r'\((\d+)\s*Ratings?\)', block)
        app["total_ratings"] = ratings_match.group(1) if ratings_match else "0"

        # Description
        desc_match = re.search(
            r'<p class="line-clamp[^"]*">(.*?)</p>', block, re.DOTALL
        )
        if desc_match:
            desc = re.sub(r'<[^>]+>', '', desc_match.group(1))
            app["description"] = unescape_html(desc.strip())
        else:
            app["description"] = ""

        # Categories
        categories = []
        tag_matches = re.findall(r'<span class="fix-font">(.*?)</span>', block)
        for tag in tag_matches:
            cat = unescape_html(tag)
            if cat and cat not in categories:
                categories.append(cat)
        app["categories"] = categories

        if app["name"]:
            apps.append(app)

    return apps


def parse_detail_page(html):
    """Extract extended info from an app detail page."""
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
        detail["long_description"] = unescape_html(desc[:500])
    else:
        detail["long_description"] = ""

    return detail


def parse_mcp_response(filepath):
    """Parse a file containing one or more MCP JSON responses.
    
    The file may contain multiple JSON objects concatenated together
    (one per URL fetched).
    """
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # Split into individual JSON objects
    results = []
    decoder = json.JSONDecoder()
    idx = 0
    while idx < len(content):
        content_stripped = content[idx:].lstrip()
        if not content_stripped:
            break
        try:
            obj, end_idx = decoder.raw_decode(content_stripped)
            results.append(obj)
            idx += (len(content[idx:]) - len(content_stripped)) + end_idx
        except json.JSONDecodeError:
            break

    return results


def process_listing_files():
    """Process all MCP listing page files and extract apps."""
    all_apps = []
    seen_ids = set()

    # Process all mcp_pages_*.json files
    files = sorted(glob.glob(os.path.join(DATA_DIR, "mcp_pages_*.json")))
    if not files:
        print("No mcp_pages_*.json files found in data/")
        return []

    for filepath in files:
        print(f"  Processing {os.path.basename(filepath)}...")
        responses = parse_mcp_response(filepath)

        for resp in responses:
            url = resp.get("url", "")
            content_list = resp.get("content", [])
            html = "".join(content_list) if content_list else ""

            if not html:
                print(f"    Empty content for {url}")
                continue

            apps = parse_listing_apps(html)
            new_count = 0
            for app in apps:
                if app["id"] not in seen_ids:
                    seen_ids.add(app["id"])
                    all_apps.append(app)
                    new_count += 1

            page_match = re.search(r'page=(\d+)', url)
            page_num = page_match.group(1) if page_match else "?"
            print(f"    Page {page_num}: {len(apps)} apps ({new_count} new, total: {len(all_apps)})")

    return all_apps


def process_detail_files(apps_list):
    """Process MCP detail page files and enrich apps."""
    app_map = {a["id"]: a for a in apps_list}

    files = sorted(glob.glob(os.path.join(DATA_DIR, "mcp_details_*.json")))
    if not files:
        print("  No mcp_details_*.json files found (skipping enrichment)")
        return apps_list

    enriched = 0
    for filepath in files:
        print(f"  Processing {os.path.basename(filepath)}...")
        responses = parse_mcp_response(filepath)

        for resp in responses:
            url = resp.get("url", "")
            content_list = resp.get("content", [])
            html = "".join(content_list) if content_list else ""

            if not html:
                continue

            # Extract app ID from URL
            id_match = re.search(r'/app/(\d+)', url)
            if not id_match:
                continue

            app_id = id_match.group(1)
            if app_id in app_map:
                detail = parse_detail_page(html)
                app_map[app_id].update(detail)
                enriched += 1

    print(f"  Enriched {enriched} apps with detail page info")
    return list(app_map.values())


def build_csv(apps_list, csv_path):
    """Build and save CSV from apps list."""
    import csv

    fieldnames = [
        "name", "slug", "url", "logo_url", "countries", "categories",
        "tags", "description", "developer_name", "developer_url",
        "developer_phone", "developer_email", "avg_rating", "total_ratings",
        "pricing",
    ]

    records = []
    seen = set()
    for app in apps_list:
        app_id = app.get("id")
        if not app_id or app_id in seen:
            continue
        seen.add(app_id)

        name = app.get("name", "").strip()
        if not name:
            continue

        pricing = app.get("pricing", "")
        tags = []
        if "Free" in pricing and "Paid" not in pricing:
            tags.append("Free")
        elif pricing and "Free" not in pricing:
            tags.append("Paid")
        if "Free" in pricing and "Paid" in pricing:
            tags.append("Freemium")

        description = app.get("long_description") or app.get("description", "")

        records.append({
            "name": name,
            "slug": str(app_id),
            "url": app.get("url", ""),
            "logo_url": app.get("logo_url", ""),
            "countries": "Saudi Arabia",
            "categories": "; ".join(app.get("categories", [])),
            "tags": "; ".join(tags),
            "description": description,
            "developer_name": app.get("developer_name", ""),
            "developer_url": app.get("developer_url", ""),
            "developer_phone": app.get("developer_phone", ""),
            "developer_email": app.get("developer_email", ""),
            "avg_rating": app.get("avg_rating", ""),
            "total_ratings": app.get("total_ratings", "0"),
            "pricing": pricing,
        })

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for r in records:
            writer.writerow(r)

    return records


def main():
    print("=" * 60)
    print("  Salla App Store — Parse MCP Data")
    print("=" * 60)

    # Step 1: Parse listing pages
    print("\n[1/3] Parsing listing pages...")
    all_apps = process_listing_files()
    print(f"\n      Total unique apps: {len(all_apps)}")

    # Save listing data
    listing_path = os.path.join(DATA_DIR, "apps_listing.json")
    with open(listing_path, "w", encoding="utf-8") as f:
        json.dump(all_apps, f, indent=2, ensure_ascii=False)
    print(f"      Saved → {listing_path}")

    # Step 2: Enrich with detail pages (if available)
    print("\n[2/3] Enriching with detail pages...")
    all_apps = process_detail_files(all_apps)

    enriched_path = os.path.join(DATA_DIR, "apps_enriched.json")
    with open(enriched_path, "w", encoding="utf-8") as f:
        json.dump(all_apps, f, indent=2, ensure_ascii=False)

    # Step 3: Build CSV
    print("\n[3/3] Building CSV...")
    csv_path = os.path.join(OUTPUT_DIR, "salla_apps.csv")
    records = build_csv(all_apps, csv_path)

    # Stats
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

    print(f"\n{'=' * 60}")
    print(f"  ✓ Saved {len(records)} apps → {csv_path}")
    print(f"  Descriptions:  {with_desc}/{len(records)}")
    print(f"  Developers:    {with_dev}/{len(records)}")
    print(f"  Dev Emails:    {with_email}/{len(records)}")
    print(f"  Free:          {free_apps}")
    print(f"  Paid:          {paid_apps}")
    print(f"\n  Category Breakdown:")
    for cat, cnt in sorted(cat_counts.items(), key=lambda x: -x[1]):
        print(f"    {cat}: {cnt}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
