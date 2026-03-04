# Shopify Partners Directory Scraper

> **Source URL:** https://www.shopify.com/partners/directory/services/development-and-troubleshooting/custom-apps-integrations

Scrapes all service partners from the [Shopify Partners Directory](https://www.shopify.com/partners/directory/services/development-and-troubleshooting/custom-apps-integrations) (Custom Apps & Integrations category) and exports them to CSV.

## Output

| Field | Description |
|-------|-------------|
| `name` | Partner company/individual name |
| `slug` | URL slug identifier |
| `url` | Full partner detail page URL |
| `logo_url` | Partner logo image URL |
| `location` | City + Country (e.g. "Dallas, United States") |
| `countries` | Country name extracted from location |
| `categories` | Service category ("Custom apps and integrations") |
| `tags` | Partner tier badge if available |
| `services` | Services offered (from listing card) |
| `rating` | Average star rating (1-5) |
| `review_count` | Number of reviews |
| `pricing` | Price range text |

## Directory Structure

```
shopify/
├── README.md
├── scrape.py              # Main scraper script (HTML parsing)
├── data/                  # Cached raw data (intermediate)
│   ├── page_1.html        # First page HTML (debug)
│   └── partners_raw.json  # Raw parsed partner data
└── output/                # Final output
    └── shopify_partners.csv
```

## How It Works

The Shopify Partners Directory is a **server-rendered HTML** page with no public API.

### Data Source

| Parameter | Value |
|-----------|-------|
| Base URL | `…/services/development-and-troubleshooting/custom-apps-integrations` |
| Pagination | `?page=N` (16 partners/page) |
| Total | ~2,527 partners across ~158 pages |

### Scraping Phases

1. **Fetch Listing Pages** — Paginate through all `?page=N` pages
2. **Parse HTML** — Extract partner cards using Python's `html.parser` (stdlib)
3. **Save CSV** — Write to `output/shopify_partners.csv`

### Filter Parameters (for manual exploration)

| Filter | Param | Example Values |
|--------|-------|----------------|
| Location | `locationCodes` | `loc-us`, `loc-gb`, `loc-ae`, `loc-sa` |
| Partner Tier | `partnerTiers` | `tier_select`, `tier_plus`, `tier_premier`, `tier_platinum` |
| Industry | `industryHandles` | `clothing_fashion`, `food_drink`, `health_beauty` |
| Language | `languageCodes` | `lang-en`, `lang-ar`, `lang-fr` |
| Price Range | `minPrice`, `maxPrice` | numeric (USD) |

## Usage

### Prerequisites

```bash
# No external dependencies needed! Uses Python stdlib only.
python3 --version  # Python 3.6+
```

### Run the scraper

```bash
cd shopify/
python3 scrape.py
```

This will:
- Fetch all ~158 listing pages (~2.5 min with 1s rate limit)
- Parse partner cards from HTML
- Save CSV to `output/shopify_partners.csv`

## Notes

- **No API** — Shopify serves HTML only for this directory, unlike Zid/Foodics which have JSON APIs.
- **No external dependencies** — uses only Python stdlib (`urllib`, `html.parser`, `csv`, `json`).
- **Rate limited** at 1 request/second to be respectful.
- The scraper currently fetches the **listing page data only**. To get extended detail (full bio, all services), uncomment the detail-fetching line in `main()`.
- ~76 countries and ~2,500+ partners are available in this category alone.
