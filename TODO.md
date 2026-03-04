# Scraping Tasks TODO

> Generated from `tasks_Needed.csv` on 2026-03-04

---

## General

- [ ] Build an automated monitor hook on these marketplaces
- [ ] Extract all Partners and add them to the list and mention which product it's related to

## Integration / Marketplace Scraping

- [x] **UrbanPiper** — Check integration page
  - 🔗 https://www.urbanpiper.com/integrations
  - 📋 Get all info by filters. Get Partner Details. Segment by countries, categories, tags.
  - ✅ Output: `urbanpiper/output/urbanpiper_integrations.csv`

- [x] **Deliverect** — Get integration page
  - 🔗 https://www.deliverect.com/en/integrations
  - 📋 Get all info by filters. Get Partner Details. Segment by countries, categories, tags.
  - ✅ Output: `deliverect/output/deliverect_integrations.csv`

- [x] **Foodics** — Get Marketplace
  - 🔗 https://www.foodics.com/marketplace/
  - 📋 Get all info by filters. Get Partner Details. Segment by countries, categories, tags.
  - ✅ Output: `foodics/output/foodics_marketplace.csv`

- [-] **TGA (Logistics Partners for Loops Track)** — Identify Licensed Companies
  - 🔗 https://www.tga.gov.sa/ar/LicensedCompanies
  - 📋 Get all info by filters. Get Partner Details. Segment by countries, categories, tags.

- [x] **Zid** — Get Apps
  - 🔗 https://apps.zid.sa/en/applications
  - 📋 Get all info by filters. Get Partner Details. Segment by countries, categories, tags.
  - ✅ Output: `zid/output/zid_apps.csv`

- [x] **Salla** — Get Apps
  - 🔗 https://apps.salla.sa/en/categories
  - 📋 Get all info by filters. Get Partner Details. Segment by countries, categories, tags.
  - ✅ Output: `salla/output/salla_apps.csv`

- [x] **Shopify** — Get Partner Apps
  - 🔗 https://www.shopify.com/partners/directory/services/development-and-troubleshooting/custom-apps-integrations
  - 📋 Get all info by filters. Get Partner Details. Segment by countries, categories, tags.
  - ✅ Output: `shopify/output/shopify_partners.csv` (2527 partners, 75 countries)

- [x] **Amazon SPN** — Get SPN Partners
  - 🔗 https://sellercentral.amazon.com/gspn
  - ✅ Output: `amazon_spn/output/amazon_spn_providers.csv` (148 unique providers, 18 categories, US→US)

- [x] **MARN** — Get Marketplace
  - 🔗 https://marn.com/en/marketplace/
  - 📋 Get all info by filters. Get Partner Details. Segment by countries, categories, tags.
  - ✅ Output: `marn/output/marn_marketplace.csv` (20 grid partners + 7 hero-logo-only, Arabic data enriched)
