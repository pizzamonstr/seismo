# Tephra Site and Tracking Change Log: Q1 2025

*Maintained by Theo Nakamura, Nakamura Web Studio. Every production release to tephra.ca is logged here.*

---

## 2025-01-08: Size chart update
- Updated Plinth boot size chart with half sizes 24.5 to 30.5.
- No tracking changes.

## 2025-01-21: Product page image zoom fix
- Fixed image zoom not working on mobile Safari for Matier and Rohr product pages.
- No tracking changes.

## 2025-02-03: Mackenzie airbag pack launch page
- Published the Mackenzie product page and "Pull the Handle" landing page for the launch.
- Added the Mackenzie collection to the main navigation.
- No tracking changes.

## 2025-02-11: Basalt theme migration (theme v4.2)
- Migrated the store from theme v3.8 to the new Basalt theme (v4.2) for faster page loads and a cleaner product page layout.
- Page speed: mobile Lighthouse score improved from 41 to 73.
- Rebuilt header, footer, and cart drawer in Basalt sections.
- Removed legacy scripts from theme.liquid as part of the cleanup. Remaining third-party scripts are loaded through apps or the Shopify Customer Events panel.
- Checked after release: GA4 purchase events, Meta pixel purchase events, and Google Ads conversions all firing on test orders.
- Reviewed by: Jordan Leclerc

## 2025-02-26: Free shipping threshold banner
- Added a site-wide banner: free shipping on orders over $150.
- No tracking changes.

## 2025-03-20: Restore custom audience events (hotfix)
- Priya reported on March 18 that Meta retargeting audiences AG-30 and ENG-60 had shrunk sharply.
- Root cause: the custom audience builder script (fires the `AvyGearView` and `Engaged60s` custom events to Meta) lived in theme.liquid in the old theme. It was removed in the February 11 theme migration because it was not documented as an active script.
- Fix: rebuilt the script as a custom pixel in Shopify Customer Events, so it no longer depends on the theme.
- Tested: both custom events now firing in Meta Events Manager.
- Note: audiences use a 30-day window, so they will take about four weeks to fully rebuild.
- Reviewed by: Jordan Leclerc

## 2025-03-27: Spring touring collection page
- Published the Spring Touring collection (Rohr, Cerise skins, Meadows base layer).
- No tracking changes.
