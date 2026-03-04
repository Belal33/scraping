# Amazon SPN (Service Provider Network) Scraper

Scrapes service providers from Amazon's Service Provider Network.
**Source**: [sellercentral.amazon.com/gspn](https://sellercentral.amazon.com/gspn)

## Data Collected

| Field | Description |
|-------|-------------|
| `name` | Provider company name |
| `provider_id` | Amazon's unique UUID for the provider |
| `url` | Link to provider's detail page on SPN |
| `logo_url` | Provider's logo image URL |
| `price` | Starting price (e.g., "USD 49.00 per month") |
| `rating` | Star rating (0.0 – 5.0) |
| `reviews` | Number of customer reviews |
| `requests_received` | Social proof (e.g., "More than 100") |
| `categories` | Service categories (semicolon-separated) |
| `badges` | Badges like "Local Provider", "SPN Guarantee" |
| `specialities` | Provider's description/specialities |
| `sell_from` | Seller origin country (US) |
| `sell_in` | Seller target country (US) |

## Usage

```bash
# Run with venv (scrapling required)
cd /path/to/scraping
.venv/bin/python3 amazon_spn/scrape.py
```

- Fetches are cached in `data/` — delete cache files to re-fetch
- Output: `output/amazon_spn_providers.csv`

## Scope

- **Page 1 only** per category (12 providers each, pagination is JS-driven)
- **18 service categories** scraped
- **US → US** market only
- **148 unique providers** extracted (as of initial run)
