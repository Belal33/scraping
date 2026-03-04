# Deliverect Integrations Scraper

> **Source URL:** https://www.deliverect.com/en/integrations

Scrapes all integration partners from [deliverect.com/en/integrations](https://www.deliverect.com/en/integrations) and exports them to CSV with metadata.

## Output

| Field | Description |
|-------|-------------|
| `name` | Partner name (e.g. Uber Eats, Square, DoorDash) |
| `slug` | URL slug identifier |
| `url` | Full partner detail page URL |
| `logo_url` | Partner logo image URL |
| `countries` | Available countries from Deliverect filters |
| `categories` | Integration categories from Deliverect filters |
| `tags` | Tags (if available) |
| `description` | Partner description from meta tags |

**Latest run:** 600 partners • 9 categories • 20 countries

## Directory Structure

```
deliverect/
├── README.md
├── scrape.py          # Main scraper script
├── data/              # Cached raw data (intermediate)
│   ├── deliverect_page_raw.json   # MCP-fetched HTML
│   ├── sample_pageProps.json      # Next.js pageProps sample
│   └── partner_slugs.json         # Extracted partner slugs
└── output/            # Final output
    └── deliverect_integrations.csv
```

## How It Works

The Deliverect integrations page is a **Next.js app** powered by **DatoCMS**. It renders 600+ partners via client-side JavaScript with filter buttons for categories and countries.

### Scraping Phases

1. **Fetch HTML** — Use [Scrapling MCP](https://github.com/D4Vinci/Scrapling) `stealthy_fetch` to get the full JS-rendered page (saved to `data/deliverect_page_raw.json`)
2. **Extract Slugs** — Parse all partner links from `<li class="c-search__item">` elements using scrapling `Selector`
3. **Fetch Descriptions** — HTTP-fetch each partner detail page via scrapling `Fetcher` and extract description from `__NEXT_DATA__` meta tags
4. **Enrich & Save** — Add categories (9) and countries (20) from the filter sections, save to CSV

## Usage

### Prerequisites

```bash
# Create/activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install scrapling
pip install "scrapling[all]"
```

### Step 1: Fetch the page (first time only)

The page requires JavaScript rendering. Use the Scrapling MCP `stealthy_fetch` to get the full HTML and save the output JSON to `data/deliverect_page_raw.json`.

### Step 2: Run the scraper

```bash
source .venv/bin/activate
cd deliverect/
python scrape.py
```

This will:
- Parse partner slugs from cached HTML
- Fetch each partner's detail page for descriptions (~600 requests, ~3 min)
- Save enriched CSV to `output/deliverect_integrations.csv`

## Categories

| Category | Description |
|----------|-------------|
| POS systems | Point-of-sale integrations |
| 3rd-party marketplace | Delivery platforms (Uber Eats, DoorDash, etc.) |
| 3rd-party dispatch | Fulfillment/dispatch services |
| Online ordering | Direct online ordering solutions |
| On-site ordering | In-house dining/kiosk apps |
| Loyalty & CRM | Customer loyalty and marketing tools |
| KDS, inventory & reporting | Kitchen display, stock management |
| Payment platforms | Payment processing integrations |
| AI integrations | AI automation tools |

## Countries

Australia, Belgium, Canada, France, Germany, Global, Hong Kong, Italy, LATAM, Mexico, Middle East, Netherlands, Nordics, Portugal, Singapore, Spain, Sweden, Switzerland, United Kingdom, United States

## Notes

- Deliverect uses **client-side JS filtering** — all partners appear in a single list with filter toggle buttons. Per-partner category assignment is not exposed in the HTML/API, so the CSV lists all available categories and countries.
- Rate limited to ~3 requests/second to be respectful.
- The `data/` directory caches intermediate files to avoid re-fetching.
