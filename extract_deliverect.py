"""
Deliverect Integrations Page Scraper
Extracts all partner details segmented by countries, categories, and tags.
Uses scrapling for fetching and parsing.
"""
import csv
import json
import os
import re
from scrapling.fetchers import StealthyFetcher


OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

URL = "https://www.deliverect.com/en/integrations"


def fetch_page():
    """Fetch the integrations page using StealthyFetcher."""
    print(f"Fetching {URL} ...")
    page = StealthyFetcher.fetch(
        URL,
        headless=True,
        network_idle=True,
    )
    print(f"Status: {page.status}")
    return page


def extract_next_data(page):
    """Try to extract __NEXT_DATA__ JSON from the page."""
    script = page.css("script#__NEXT_DATA__::text").get()
    if script:
        return json.loads(script)
    return None


def extract_filters(page):
    """Extract filter options (countries, categories, tags) from the page."""
    filters = {"countries": [], "categories": [], "tags": []}

    # Look for filter/dropdown sections in the page
    # The page has filter buttons/dropdowns for segmentation
    filter_sections = page.css(".c-filter-dropdown, .c-filter, .c-dropdown, [class*='filter']")
    print(f"Found {len(filter_sections)} filter sections")

    for section in filter_sections:
        section_text = section.get_all_text(strip=True) if hasattr(section, 'get_all_text') else ""
        print(f"  Filter section: {section_text[:100]}")

    return filters


def extract_partners_from_search_results(page):
    """Extract partner data from the search result list items."""
    partners = []

    # The page has search results with partner cards
    search_items = page.css(".c-search__item")
    print(f"Found {len(search_items)} search result items")

    for item in search_items:
        link = item.css("a.c-search-result")
        if not link:
            continue
        link = link[0]

        name_text = link.get_all_text(strip=True) if hasattr(link, 'get_all_text') else ""
        href = link.attrib.get("href", "")

        img = link.css("img")
        logo_url = ""
        if img:
            logo_url = img[0].attrib.get("src", "") or img[0].attrib.get("srcset", "").split(" ")[0] if img[0].attrib.get("srcset") else ""
            if not logo_url:
                logo_url = img[0].attrib.get("src", "")

        partners.append({
            "name": name_text.strip(),
            "url": f"https://www.deliverect.com{href}" if href.startswith("/") else href,
            "logo_url": logo_url,
        })

    return partners


def extract_integration_cards(page):
    """Extract partner data from integration card grid."""
    partners = []

    # Try various card selectors
    selectors = [
        ".c-integration-card",
        ".c-partner-card",
        "[class*='integration-card']",
        "[class*='partner-card']",
        ".c-card",
        "[class*='card']",
    ]

    for sel in selectors:
        cards = page.css(sel)
        if cards:
            print(f"Found {len(cards)} cards with selector: {sel}")
            for card in cards[:3]:
                print(f"  Card classes: {card.attrib.get('class', '')}")
                print(f"  Card text: {card.get_all_text(strip=True)[:100]}")
            break

    return partners


def extract_all_partner_links(page):
    """Extract all integration partner links from any part of the page."""
    partners = []
    seen = set()

    # All links that point to /en/integrations/<slug>
    all_links = page.css("a[href*='/integrations/']")
    print(f"Found {len(all_links)} links matching /integrations/")

    for link in all_links:
        href = link.attrib.get("href", "")
        # Only actual partner pages (not category pages)
        if not re.match(r"^/en/integrations/[a-z0-9]", href):
            continue
        # Skip category/filter pages
        skip_slugs = [
            "pos-systems", "delivery-channels", "online-ordering",
            "in-house-dining-apps", "fulfilment", "loyalty",
        ]
        slug = href.split("/")[-1] if "/" in href else ""
        if slug in skip_slugs:
            continue

        if href in seen:
            continue
        seen.add(href)

        # Get partner name from link text or img alt
        name = link.get_all_text(strip=True) if hasattr(link, 'get_all_text') else ""
        if not name:
            img = link.css("img")
            if img:
                name = img[0].attrib.get("alt", "") or img[0].attrib.get("title", "")

        logo_url = ""
        img = link.css("img")
        if img:
            logo_url = img[0].attrib.get("src", "")

        partners.append({
            "name": name.strip(),
            "url": f"https://www.deliverect.com{href}" if href.startswith("/") else href,
            "logo_url": logo_url,
        })

    return partners


def scrape_partner_detail(url):
    """Scrape a single partner detail page for countries, categories, tags."""
    try:
        page = StealthyFetcher.fetch(url, headless=True, network_idle=True)
    except Exception as e:
        print(f"  Error fetching {url}: {e}")
        return {"countries": [], "categories": [], "tags": [], "description": ""}

    data = {
        "countries": [],
        "categories": [],
        "tags": [],
        "description": "",
    }

    # Try to extract __NEXT_DATA__ for structured info
    next_data = extract_next_data(page)
    if next_data:
        try:
            page_props = next_data.get("props", {}).get("pageProps", {})
            partner = page_props.get("partner", page_props.get("integration", {}))
            if partner:
                data["countries"] = [c.get("name", c) if isinstance(c, dict) else str(c)
                                     for c in partner.get("countries", partner.get("availableCountries", []))]
                data["categories"] = [c.get("name", c) if isinstance(c, dict) else str(c)
                                      for c in partner.get("categories", partner.get("category", []))]
                data["tags"] = [t.get("name", t) if isinstance(t, dict) else str(t)
                                for t in partner.get("tags", [])]
                data["description"] = partner.get("description", partner.get("shortDescription", ""))
                return data
        except Exception:
            pass

    # Fallback: parse from visible page content
    # Look for country/category/tag labels
    labels = page.css(".c-tag, .c-badge, .c-chip, [class*='tag'], [class*='badge'], [class*='chip']")
    for label in labels:
        text = label.get_all_text(strip=True) if hasattr(label, 'get_all_text') else ""
        if text:
            data["tags"].append(text)

    # Description from hero/intro section
    hero_desc = page.css(".c-hero__content p::text, .c-partner__description::text, [class*='description'] p::text")
    if hero_desc:
        data["description"] = " ".join(hero_desc.getall()).strip()

    return data


def save_to_csv(partners, filename):
    """Save partner data to CSV."""
    filepath = os.path.join(OUTPUT_DIR, filename)

    if not partners:
        print(f"No partners to save to {filename}")
        return

    # Determine all fieldnames
    fieldnames = list(partners[0].keys())

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for partner in partners:
            # Convert lists to semicolon-separated strings
            row = {}
            for k, v in partner.items():
                if isinstance(v, list):
                    row[k] = "; ".join(str(x) for x in v)
                else:
                    row[k] = v
            writer.writerow(row)

    print(f"Saved {len(partners)} partners to {filepath}")


def main():
    # Step 1: Fetch the main integrations page
    page = fetch_page()

    # Step 2: Try __NEXT_DATA__ first (most reliable)
    next_data = extract_next_data(page)
    if next_data:
        print("Found __NEXT_DATA__ - extracting structured data...")
        try:
            page_props = next_data.get("props", {}).get("pageProps", {})
            # Save raw data for debugging
            with open(os.path.join(OUTPUT_DIR, "pageProps.json"), "w") as f:
                json.dump(page_props, f, indent=2)
            print(f"Saved pageProps.json ({len(json.dumps(page_props))} bytes)")

            # Extract partners from structured data
            all_partners = page_props.get("partners", page_props.get("integrations", []))
            if all_partners:
                print(f"Found {len(all_partners)} partners in __NEXT_DATA__")
                partners = []
                for p in all_partners:
                    name = p.get("name", p.get("title", ""))
                    slug = p.get("slug", "")
                    countries = [c.get("name", c) if isinstance(c, dict) else str(c)
                                 for c in p.get("countries", p.get("availableCountries", []))]
                    categories = [c.get("name", c) if isinstance(c, dict) else str(c)
                                  for c in p.get("categories", p.get("category", []))]
                    tags = [t.get("name", t) if isinstance(t, dict) else str(t)
                            for t in p.get("tags", [])]
                    logo = ""
                    if "logo" in p and isinstance(p["logo"], dict):
                        logo = p["logo"].get("url", "")
                    elif "logo" in p:
                        logo = str(p["logo"])

                    partners.append({
                        "name": name,
                        "slug": slug,
                        "url": f"https://www.deliverect.com/en/integrations/{slug}",
                        "logo_url": logo,
                        "countries": countries,
                        "categories": categories,
                        "tags": tags,
                        "description": p.get("description", p.get("shortDescription", "")),
                    })

                save_to_csv(partners, "deliverect_integrations.csv")
                return
        except Exception as e:
            print(f"Error processing __NEXT_DATA__: {e}")

    # Step 3: Fallback - extract partner links from HTML
    print("No __NEXT_DATA__ found or failed to parse. Extracting from HTML...")
    partners_basic = extract_all_partner_links(page)
    print(f"Found {len(partners_basic)} unique partner links from HTML")

    if not partners_basic:
        print("No partners found! Dumping page HTML for debugging...")
        with open(os.path.join(OUTPUT_DIR, "debug_page.html"), "w") as f:
            f.write(page.html_content if hasattr(page, 'html_content') else str(page))
        return

    # Step 4: Scrape each partner detail page for countries/categories/tags
    full_partners = []
    total = len(partners_basic)
    for i, partner in enumerate(partners_basic):
        print(f"[{i+1}/{total}] Scraping details for: {partner['name']}")
        details = scrape_partner_detail(partner["url"])
        full_partners.append({
            "name": partner["name"],
            "url": partner["url"],
            "logo_url": partner["logo_url"],
            "countries": details["countries"],
            "categories": details["categories"],
            "tags": details["tags"],
            "description": details["description"],
        })

    save_to_csv(full_partners, "deliverect_integrations.csv")
    print("Done!")


if __name__ == "__main__":
    main()
