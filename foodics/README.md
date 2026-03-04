# Foodics Marketplace Scraper

> **Source URL:** https://www.foodics.com/marketplace/

Scrapes all marketplace app partners from [foodics.com/marketplace](https://www.foodics.com/marketplace/) and exports them to CSV with metadata.

## Output

| Field | Description |
|-------|-------------|
| `name` | App name (e.g. Wafeq, Deliverect, Jahez) |
| `slug` | URL slug identifier |
| `url` | Full partner detail page URL |
| `logo_url` | App logo image URL |
| `countries` | Foodics operating countries |
| `categories` | App categories (semicolon-separated) |
| `tags` | Tags (if available) |
| `description` | App description from marketplace listing |

## Directory Structure

```
foodics/
├── README.md
├── scrape.py          # Main scraper script
├── data/              # Cached raw data (intermediate)
│   ├── foodics_page_raw.json   # MCP-fetched HTML
│   └── partner_slugs.json      # Extracted partner slugs
└── output/            # Final output
    └── foodics_marketplace.csv
```

## How It Works

The Foodics marketplace page is a **WordPress + Elementor** site using **JetEngine** for custom post types and **JetSmartFilters** for category filtering. All apps are rendered server-side on a single page.

### Scraping Phases

1. **Fetch HTML** — Use [Scrapling MCP](https://github.com/D4Vinci/Scrapling) `fetch` to get the full page (saved to `data/foodics_page_raw.json`)
2. **Parse App Cards** — Extract data from `article.elementor-post` elements using scrapling `Selector`:
   - Name from `h3.elementor-post__title a`
   - Logo from `.elementor-post__thumbnail img`
   - Categories from CSS classes (`portfolio-types-*`)
   - Description from `.elementor-post__excerpt p`
   - Detail page URL from the title link
3. **Save CSV** — Write to `output/foodics_marketplace.csv`

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

Use the Scrapling MCP `fetch` to get the full HTML and save the output JSON to `data/foodics_page_raw.json`.

### Step 2: Run the scraper

```bash
source .venv/bin/activate
cd foodics/
python scrape.py
```

This will:
- Parse app cards from cached HTML
- Extract name, logo, categories, and description per app
- Save CSV to `output/foodics_marketplace.csv`

## Categories

| Category | Description |
|----------|-------------|
| Accounting | Financial and accounting integrations |
| Chat Bot | Chatbot solutions |
| Delivery Management | Delivery fleet/logistics management |
| Digital Menu | QR/digital menu solutions |
| Digital Receipts | E-receipt services |
| Digital Signage | Screen/display management |
| ERP | Enterprise resource planning |
| Food Aggregator | Food delivery platforms (Jahez, Careem, etc.) |
| Inventory Management | Stock and supply chain tools |
| Loyalty | Customer loyalty and rewards programs |
| Online Ordering | Direct online ordering systems |
| Ordering Platforms Management | Multi-platform order aggregation |
| Table Payments | Pay-at-table solutions |
| Table Reservation | Reservation management |

## Countries

Saudi Arabia, United Arab Emirates, Egypt, Kuwait, Jordan

## Notes

- Foodics uses **WordPress + Elementor** with **JetEngine** custom post types (Portfolio).
- Per-app category assignment is embedded in CSS classes on each `<article>` element, enabling precise categorization.
- All apps appear on a single page with no pagination.
- Countries are not per-app — Foodics operates across 5 MENA countries.
