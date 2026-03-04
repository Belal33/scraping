# MARN Marketplace Scraper

Scrapes the [MARN Marketplace](https://marn.com/en/marketplace/) for integration partner data.

## How It Works

1. **Phase 1** – Loads cached HTML from `data/marn_page_raw.json` (MCP-fetched)
2. **Phase 2** – Parses partner cards from `div.marketplacepartnerbox` elements
3. **Phase 3** – Fetches each partner's detail page for enrichment (location, fees, industry, website, full description)
4. **Phase 4** – Saves to CSV

## Output

- `output/marn_marketplace.csv` — 20 marketplace partners

### Fields

| Field | Description |
|-------|-------------|
| `name` | Partner name |
| `slug` | URL slug |
| `url` | Detail page URL |
| `logo_url` | Partner logo image URL |
| `countries` | Operating countries (Saudi Arabia) |
| `categories` | Category tags |
| `tags` | Additional tags |
| `description` | Short description from listing page |
| `location` | Company location (from detail page) |
| `fees` | Pricing info (from detail page) |
| `industry` | Industry category (from detail page) |
| `website` | Partner website URL (from detail page) |
| `detail_description` | Full description (from detail page) |

## Usage

```bash
# From the scraping root directory
.venv/bin/python3 marn/scrape.py
```

## Data Refresh

To refresh the cached HTML, use the Scrapling MCP `fetch` tool on `https://marn.com/en/marketplace/` with `extraction_type=html` and save the output to `data/marn_page_raw.json`.
