# UrbanPiper Integrations Scraper

> **Source URL:** https://www.urbanpiper.com/integrations

Scrapes all integration partners from [urbanpiper.com/integrations](https://www.urbanpiper.com/integrations) and exports them to CSV with metadata.

## Output

| Field | Description |
|-------|-------------|
| `name` | Partner name (e.g. Uber Eats, Square, Foodics) |
| `logo_url` | Partner logo image URL |
| `categories` | Integration category (POS Systems, Delivery platforms, etc.) |
| `statuses` | Partner status (Live or Upcoming) |
| `countries` | Countries where the partner operates (pipe-separated) |
| `is_global` | Whether the partner is globally available |
| `partner_url` | Source page URL |

**Latest run:** 182 partners • 4 categories • 21 countries

## Directory Structure

```
urbanpiper/
├── README.md
├── data/              # Cached raw data (intermediate)
└── output/            # Final output
    └── urbanpiper_integrations.csv
```

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
