"""
Deliverect Integrations Scraper
Phase 1: Parse partner slugs from MCP-fetched JS-rendered HTML
Phase 2: Fetch each partner detail page via HTTP for structured data
"""
import csv
import json
import os
import re
import sys
import time
from scrapling import Selector
from scrapling.fetchers import Fetcher

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)
BASE_URL = "https://www.deliverect.com"

# Category slugs to skip (these are category pages, not partners)
SKIP_SLUGS = {
    "pos-systems", "delivery-channels", "online-ordering",
    "in-house-dining-apps", "fulfilment", "loyalty", "retail",
    "on-site-ordering", "inventory-management", "analytics",
    "payments", "kiosk", "digital-signage", "restaurant-ai-integrations",
}


def phase1_extract_slugs():
    """Extract partner slugs from the MCP-fetched HTML."""
    raw_file = os.path.join(OUTPUT_DIR, "deliverect_page_raw.json")
    if not os.path.exists(raw_file):
        print(f"ERROR: {raw_file} not found. Fetch the page first via Scrapling MCP.")
        sys.exit(1)

    print("  Loading cached HTML...")
    with open(raw_file, "r", encoding="utf-8") as f:
        raw = f.read()

    # Parse the MCP JSON wrapper
    try:
        data = json.loads(raw)
        html = data["content"][0] if isinstance(data.get("content"), list) else data.get("content", raw)
    except (json.JSONDecodeError, KeyError):
        html = raw

    print(f"  HTML size: {len(html):,} chars")
    page = Selector(html, url="https://www.deliverect.com/en/integrations")

    partners = []
    seen = set()

    # Find all links to /en/integrations/<slug>
    all_links = page.css("a[href]")
    for link in all_links:
        href = link.attrib.get("href", "")
        match = re.match(r"^/en/integrations/([a-zA-Z0-9][a-zA-Z0-9\-]*)$", href)
        if not match:
            continue

        slug = match.group(1)
        if slug in SKIP_SLUGS or slug in seen:
            continue
        seen.add(slug)

        # Get name
        name = ""
        img = link.css("img")
        if img:
            name = img[0].attrib.get("alt", "") or img[0].attrib.get("title", "")
        if not name:
            texts = link.css("::text").getall()
            name = " ".join(t.strip() for t in texts if t.strip())

        # Get logo
        logo_url = ""
        if img:
            logo_url = img[0].attrib.get("src", "")

        partners.append({
            "name": name.strip(),
            "slug": slug,
            "logo_url": logo_url,
        })

    return partners


def extract_dast_text(dast_obj):
    """Extract plain text from DatoCMS Structured Text (DAST)."""
    if isinstance(dast_obj, str):
        return dast_obj

    if not isinstance(dast_obj, dict):
        return str(dast_obj) if dast_obj else ""

    # Handle {"value": {"schema":"dast", "document":{...}}}
    if "value" in dast_obj:
        return extract_dast_text(dast_obj["value"])

    texts = []
    doc = dast_obj.get("document", dast_obj)
    for child in doc.get("children", []):
        if child.get("type") == "paragraph":
            for span in child.get("children", []):
                if span.get("type") == "span":
                    texts.append(span.get("value", ""))
        elif child.get("type") == "span":
            texts.append(child.get("value", ""))

    return " ".join(texts).strip()


def phase2_fetch_details(partners):
    """Fetch each partner detail page for countries/categories/tags."""
    results = []
    total = len(partners)
    errors = 0

    for i, p in enumerate(partners):
        slug = p["slug"]
        url = f"{BASE_URL}/en/integrations/{slug}"
        print(f"  [{i+1}/{total}] {p['name'] or slug}", end="", flush=True)

        detail = {
            "name": p["name"],
            "slug": slug,
            "url": url,
            "logo_url": p.get("logo_url", ""),
            "countries": "",
            "categories": "",
            "tags": "",
            "description": "",
        }

        try:
            page = Fetcher.get(url)
            if page.status != 200:
                print(f" ✗ {page.status}")
                errors += 1
                results.append(detail)
                continue

            # Extract __NEXT_DATA__
            script_text = page.css("script#__NEXT_DATA__::text").get()
            if not script_text:
                print(" ✗ no data")
                errors += 1
                results.append(detail)
                continue

            nd = json.loads(script_text)
            pp = nd.get("props", {}).get("pageProps", {})
            page_obj = pp.get("page", {})
            comps = page_obj.get("components", [])

            # --- Extract categories from components ---
            categories = []
            for comp in comps:
                tn = comp.get("__typename", "")
                # IntegrationsFiltering has the category list
                if "IntegrationsFiltering" in tn:
                    for cat in comp.get("categories", []):
                        cat_title = cat.get("title", "")
                        if cat_title:
                            categories.append(cat_title)

                # Integration detail blocks may have category info
                if "IntegrationDetail" in tn or "PartnerDetail" in tn:
                    cat_val = comp.get("category", comp.get("categories", ""))
                    if isinstance(cat_val, list):
                        categories.extend(c.get("title", str(c)) if isinstance(c, dict) else str(c) for c in cat_val)
                    elif isinstance(cat_val, str) and cat_val:
                        categories.append(cat_val)

            # --- Extract countries from enabled markets ---
            countries = []
            enabled_markets = page_obj.get("enabledMarkets", [])
            for m in enabled_markets:
                iso = m.get("countryIsoCode", "")
                if iso and iso != "XX":
                    countries.append(iso)

            # --- Extract tags ---
            tags = []
            meta = page_obj.get("metaTags", {})
            kw = meta.get("keywords", "")
            if kw:
                tags = [t.strip() for t in kw.split(",") if t.strip()]

            # --- Description ---
            desc = meta.get("description", "")
            if not desc:
                # Try from hero component
                for comp in comps:
                    if "Hero" in comp.get("__typename", ""):
                        desc = extract_dast_text(comp.get("content", comp.get("description", "")))
                        if desc:
                            break

            # --- Also check for partner-specific integration data ---
            # Some pages have specific integration details in components
            for comp in comps:
                tn = comp.get("__typename", "")
                if "IntegrationHero" in tn or "PartnerHero" in tn:
                    # May have specific category/tag assignments
                    comp_cats = comp.get("categories", comp.get("types", []))
                    if isinstance(comp_cats, list):
                        for c in comp_cats:
                            title = c.get("title", "") if isinstance(c, dict) else str(c)
                            if title and title not in categories:
                                categories.append(title)

                    comp_tags = comp.get("tags", [])
                    if isinstance(comp_tags, list):
                        for t in comp_tags:
                            tag = t.get("title", t.get("name", "")) if isinstance(t, dict) else str(t)
                            if tag and tag not in tags:
                                tags.append(tag)

                    comp_countries = comp.get("countries", comp.get("availableIn", []))
                    if isinstance(comp_countries, list):
                        for c in comp_countries:
                            cn = c.get("name", c.get("title", "")) if isinstance(c, dict) else str(c)
                            if cn and cn not in countries:
                                countries.append(cn)

            detail["countries"] = "; ".join(countries)
            detail["categories"] = "; ".join(categories)
            detail["tags"] = "; ".join(tags)
            detail["description"] = desc[:500] if desc else ""

            marker = "✓" if (countries or categories or tags) else "~"
            print(f" {marker}")

        except Exception as e:
            print(f" ✗ error: {e}")
            errors += 1

        results.append(detail)

        # Rate limit
        if i < total - 1:
            time.sleep(0.3)

    print(f"\n  Completed: {total - errors} ok, {errors} errors")
    return results


def save_csv(partners, filename):
    """Save to CSV."""
    filepath = os.path.join(OUTPUT_DIR, filename)
    fieldnames = ["name", "slug", "url", "logo_url", "countries", "categories", "tags", "description"]

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for p in partners:
            writer.writerow(p)

    print(f"\n✓ Saved {len(partners)} partners → {filepath}")
    return filepath


def main():
    print("=" * 60)
    print("  Deliverect Integrations Scraper")
    print("=" * 60)

    # Phase 1: Extract slugs
    print("\n[Phase 1] Extracting partner slugs from cached HTML...")
    partners = phase1_extract_slugs()
    print(f"  ✓ Found {len(partners)} unique partners")

    if not partners:
        print("ERROR: No partners found!")
        return

    # Save slugs list for reference
    slugs_path = os.path.join(OUTPUT_DIR, "partner_slugs.json")
    with open(slugs_path, "w") as f:
        json.dump(partners, f, indent=2)
    print(f"  Saved slugs → {slugs_path}")

    # Phase 2: Fetch details
    print(f"\n[Phase 2] Fetching detail pages ({len(partners)} partners)...")
    full_data = phase2_fetch_details(partners)

    # Phase 3: Save CSV
    print("\n[Phase 3] Saving CSV...")
    csv_path = save_csv(full_data, "deliverect_integrations.csv")

    # Summary
    print("\n" + "=" * 60)
    with_c = sum(1 for p in full_data if p["countries"])
    with_cat = sum(1 for p in full_data if p["categories"])
    with_t = sum(1 for p in full_data if p["tags"])
    with_d = sum(1 for p in full_data if p["description"])
    print(f"  Total: {len(full_data)} partners")
    print(f"  With countries:    {with_c}")
    print(f"  With categories:   {with_cat}")
    print(f"  With tags:         {with_t}")
    print(f"  With description:  {with_d}")
    print("=" * 60)


if __name__ == "__main__":
    main()
