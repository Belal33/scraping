"""
Enrich the Deliverect integrations CSV with categories and countries
extracted from the JS-rendered HTML page data.

Strategy:
- Categories: extracted from the c-filter section of the page
- Countries: extracted from the c-filter section of the page
- Per-partner category data: since the page uses JS filtering and doesn't
  embed category-per-partner in HTML, we add the available categories list
  as a reference and note that Deliverect's structure groups all partners
  under a single filtering view without per-partner category tags.
"""
import csv
import json
import os
import re
from scrapling import Selector

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")


def extract_filters_from_html():
    """Extract filter categories and countries from the cached HTML."""
    raw_file = os.path.join(OUTPUT_DIR, "deliverect_page_raw.json")
    with open(raw_file, "r", encoding="utf-8") as f:
        data = json.loads(f.read())

    html = data["content"][0] if isinstance(data.get("content"), list) else data.get("content", "")
    page = Selector(html, url="https://www.deliverect.com/en/integrations")

    filters = {"categories": [], "countries": []}

    # Extract from filter sections
    filter_sections = page.css(".c-filter")
    for fs in filter_sections:
        title_el = fs.css(".c-filter__title")
        if not title_el:
            continue
        title = title_el[0].get_all_text(strip=True)

        # Get button/link texts
        buttons = fs.css("button, a")
        items = []
        for b in buttons:
            text = b.get_all_text(strip=True)
            if text and text != title and text != "All integrations":
                items.append(text)

        if "Categor" in title:
            filters["categories"] = items
        elif "Countr" in title:
            filters["countries"] = items

    return filters


def extract_search_partners():
    """Extract partners from search results with clean names."""
    raw_file = os.path.join(OUTPUT_DIR, "deliverect_page_raw.json")
    with open(raw_file, "r", encoding="utf-8") as f:
        data = json.loads(f.read())

    html = data["content"][0] if isinstance(data.get("content"), list) else data.get("content", "")
    page = Selector(html, url="https://www.deliverect.com/en/integrations")

    # Category slugs to skip
    skip_slugs = {
        "pos-systems", "delivery-channels", "online-ordering",
        "in-house-dining-apps", "fulfilment", "loyalty", "retail",
        "on-site-ordering", "inventory-management", "analytics",
        "payments", "kiosk", "digital-signage", "restaurant-ai-integrations",
    }

    partners = {}
    items = page.css(".c-search__item")
    for item in items:
        link = item.css("a.c-search-result")
        if not link:
            continue
        link = link[0]

        href = link.attrib.get("href", "")
        match = re.match(r"^/en/integrations/([a-zA-Z0-9][a-zA-Z0-9\-]*)$", href)
        if not match:
            continue

        slug = match.group(1)
        if slug in skip_slugs:
            continue

        # Get clean name from img alt or text
        img = link.css("img")
        name = ""
        logo_url = ""
        if img:
            name = img[0].attrib.get("alt", "") or img[0].attrib.get("title", "")
            logo_url = img[0].attrib.get("src", "")

        if not name:
            name = link.get_all_text(strip=True)

        partners[slug] = {
            "name": name.strip(),
            "slug": slug,
            "logo_url": logo_url,
        }

    return partners


def main():
    print("Enriching Deliverect integrations data...")

    # 1. Get filter lists
    filters = extract_filters_from_html()
    print(f"Categories ({len(filters['categories'])}): {filters['categories']}")
    print(f"Countries ({len(filters['countries'])}): {filters['countries']}")

    # 2. Get clean partner names from search items
    search_partners = extract_search_partners()
    print(f"Search partners: {len(search_partners)}")

    # 3. Read existing CSV
    csv_path = os.path.join(OUTPUT_DIR, "deliverect_integrations.csv")
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        existing = list(reader)

    print(f"Existing CSV rows: {len(existing)}")

    # 4. Enrich with clean names and add countries list
    enriched = []
    countries_str = "; ".join(filters["countries"])
    categories_str = "; ".join(filters["categories"])

    for row in existing:
        slug = row["slug"]

        # Fix name if it ends with " logo"
        if slug in search_partners:
            row["name"] = search_partners[slug]["name"]
            if not row["logo_url"] or row["logo_url"].startswith("/_next"):
                row["logo_url"] = search_partners[slug]["logo_url"] or row["logo_url"]

        # Add countries (from filter - these are the available countries)
        if not row.get("countries"):
            row["countries"] = countries_str

        # Add categories (from filter - these are the Deliverect categories)
        if not row.get("categories"):
            row["categories"] = categories_str

        enriched.append(row)

    # 5. Add any partners from search that aren't in our CSV yet
    existing_slugs = {r["slug"] for r in enriched}
    for slug, p_data in search_partners.items():
        if slug not in existing_slugs:
            enriched.append({
                "name": p_data["name"],
                "slug": slug,
                "url": f"https://www.deliverect.com/en/integrations/{slug}",
                "logo_url": p_data["logo_url"],
                "countries": countries_str,
                "categories": categories_str,
                "tags": "",
                "description": "",
            })

    # 6. Save enriched CSV
    fieldnames = ["name", "slug", "url", "logo_url", "countries", "categories", "tags", "description"]
    out_path = os.path.join(OUTPUT_DIR, "deliverect_integrations.csv")
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in enriched:
            writer.writerow(row)

    print(f"\n✓ Saved {len(enriched)} partners → {out_path}")

    # Summary
    with_desc = sum(1 for r in enriched if r.get("description"))
    print(f"  With descriptions: {with_desc}/{len(enriched)}")
    print(f"  Categories: {categories_str[:80]}...")
    print(f"  Countries: {countries_str[:80]}...")


if __name__ == "__main__":
    main()
