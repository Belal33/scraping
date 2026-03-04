# UrbanPiper Integrations Scraper

> **Source URL:** https://www.urbanpiper.com/integrations

Scrapes all integration partners from [urbanpiper.com/integrations](https://www.urbanpiper.com/integrations) and exports them to CSV with metadata.

## Output

| Field | Description |
|-------|-------------|
| `name` | Partner name (e.g. Uber Eats, Square, Foodics) |
| `slug` | URL slug identifier |
| `url` | Source page URL |
| `logo_url` | Partner logo image URL |
| `countries` | Countries where the partner operates (semicolon-separated) |
| `categories` | Integration categories (semicolon-separated) |
| `tags` | Partner status (Live or Upcoming) |
| `description` | Partner description (not available on this page) |

**Latest run:** 182 partners • 4 categories • 21 countries

## Directory Structure

```
urbanpiper/
├── README.md
├── scrape.py          # Main scraper script
├── data/              # Cached raw data (intermediate)
│   ├── urbanpiper_page_raw.json   # MCP-fetched HTML
│   └── partner_slugs.json         # Extracted partner slugs
└── output/            # Final output
    └── urbanpiper_integrations.csv
```

## How It Works

The UrbanPiper integrations page is a **Webflow CMS** site. It renders 180+ partners with a client-side filter system using [Finsweet CMS Filter](https://finsweet.com/attributes/cms-filter).

### Scraping Phases

1. **Fetch HTML** — Use [Scrapling MCP](https://github.com/D4Vinci/Scrapling) `fetch` to get the full JS-rendered page (saved to `data/urbanpiper_page_raw.json`)
2. **Parse Partner Cards** — Extract data from `.integration-collection-list-item-search` elements using scrapling `Selector`:
   - Name from `.integration-grid-name-v1`
   - Logo from `.integration-grid-image-v1`
   - Categories from `.integration-grid-system-v1`
   - Status from `.integration-grid-status`
   - Countries from `.integration-country-names`
3. **Save CSV** — Write to `output/urbanpiper_integrations.csv`

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

The page requires JavaScript rendering. Use the Scrapling MCP `fetch` to get the full HTML and save the output JSON to `data/urbanpiper_page_raw.json`.

### Step 2: Run the scraper

```bash
source .venv/bin/activate
cd urbanpiper/
python scrape.py
```

This will:
- Parse partner cards from cached HTML
- Extract name, logo, categories, status, and countries per partner
- Save CSV to `output/urbanpiper_integrations.csv`

## Categories

| Category | Count |
|----------|-------|
| POS Systems | 124 |
| Delivery platforms | 37 |
| Online Ordering | 12 |
| Fulfilment | 8 |

## Countries

Australia, Bahrain, Belgium, Canada, Chile, Colombia, Egypt, Global, India, Ireland, Jordan, Kenya, Kuwait, Mexico, Oman, Qatar, Saudi Arabia, Sri Lanka, United Arab Emirates, United Kingdom, United States

## Data Quality

- **182/182** logos ✓
- **180/182** categories (Instashop and Smiles have no category on the source page)
- **172/182** countries (10 "Upcoming" partners have no country listed on source)
- **167 Live** / **15 Upcoming** partners
- **1 Global** partner (Odoo)

## Notes

- UrbanPiper uses **Webflow CMS** with **Finsweet CMS Filter** for client-side filtering.
- Per-partner category and country data is embedded directly in each card, so extraction is precise.
- No individual partner detail pages exist, so descriptions are not available.
