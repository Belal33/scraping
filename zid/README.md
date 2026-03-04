# Zid App Market Scraper

> **Source URL:** https://apps.zid.sa/en/applications

Scrapes all marketplace apps from [apps.zid.sa](https://apps.zid.sa/en/applications) via the **public REST API** and exports them to CSV with metadata.

## Output

| Field | Description |
|-------|-------------|
| `name` | App name (e.g. Cartat Whatsapp, Shrinkit, Thunder) |
| `slug` | App ID (numeric) |
| `url` | Full app detail page URL |
| `logo_url` | App icon image URL |
| `countries` | Zid operating countries (Saudi Arabia) |
| `categories` | App category |
| `tags` | Pricing type, trial info, discount, featured status |
| `description` | App description from API |
| `developer_name` | Developer/partner company name |
| `developer_email` | Developer contact email |
| `developer_url` | Developer website URL |
| `developer_phone` | Developer phone number |
| `avg_rating` | Average user rating (1-5) |
| `total_ratings` | Number of ratings |
| `pricing` | Pricing plan text |

## Directory Structure

```
zid/
├── README.md
├── scrape.py          # Main scraper script (API-based)
├── data/              # Cached raw data (intermediate)
│   ├── categories.json    # Category list from API
│   └── apps_raw.json     # Raw app data from API
└── output/            # Final output
    └── zid_apps.csv
```

## How It Works

The Zid App Market is a **Nuxt.js** app backed by a **public REST API** at `api.zid.sa/v1/market/public/`.

### API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /categories` | Returns all app categories with counts |
| `GET /apps?page=N&per_page=M&lang=en` | Returns paginated app list |

### Scraping Phases

1. **Fetch Categories** — GET `/categories` to retrieve all 13 category names and app counts
2. **Fetch Apps** — Paginate through `/apps?per_page=100` to collect all ~530+ apps
3. **Process Data** — Extract name, developer, description, rating, pricing, and category per app
4. **Save CSV** — Write to `output/zid_apps.csv`

## Usage

### Prerequisites

```bash
# No external dependencies needed! Uses Python stdlib (urllib, json, csv)
python3 --version  # Python 3.6+
```

### Run the scraper

```bash
cd zid/
python3 scrape.py
```

This will:
- Fetch categories and all apps via API (~6 API calls)
- Process and deduplicate app records
- Save CSV to `output/zid_apps.csv`

## Categories

| Category | App Count |
|----------|-----------|
| Shipping & Fulfilment | 204 |
| Marketing | 102 |
| Customer Support | 48 |
| Accounting | 35 |
| Inventory Management | 33 |
| Operations | 33 |
| Analytics & Reporting | 25 |
| Productivity | 20 |
| Payments | 9 |
| Campaign Tracking | 9 |
| Finding Products | 6 |
| Mobile Apps | 4 |
| Sales Channels | 4 |

## Countries

Saudi Arabia

## Notes

- Zid uses a **public REST API** — no scraping of HTML needed, all data comes from JSON.
- **No external dependencies** — uses only Python stdlib (urllib, json, csv).
- Unlike previous scrapers, this one can extract **per-app category** assignment.
- Developer/partner details (name, email, URL, phone) are included per app.
- Categories are returned in Arabic by the API; English names are mapped from the page UI.
- Rate limited to ~2 requests/second to be respectful.
