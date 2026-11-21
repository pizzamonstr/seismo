# Tephra Site and Tracking Change Log: Q4 2025

*Maintained by Theo Nakamura, Nakamura Web Studio. Every production release to tephra.ca is logged here.*

---

## 2025-10-08: Fix Purchase event deduplication (hotfix)
- Jordan reported on October 6 that Meta-reported purchases were much higher than Shopify orders from Meta traffic.
- Root cause: since the September 9 gateway change, the browser pixel sent `event_id` as the Shopify order ID, but the gateway sent the checkout token. Because the IDs did not match, Meta treated most browser and server Purchase events as separate purchases and counted them twice.
- Fix: the gateway now sends the Shopify order ID as `event_id` for Purchase, matching the browser pixel.
- Tested: test orders show one deduplicated Purchase in Events Manager.
- Note for reporting: Meta purchases and ROAS from September 9 to October 8 are inflated. Meta does not correct historical data.
- Reviewed by: Jordan Leclerc

## 2025-10-21: Black Friday landing page (draft)
- Built the draft Black Friday landing page with the Fissile splitboard as the hero offer.
- Not published yet.

## 2025-11-14: Sold-out badge on product cards
- Product cards now show a "Sold out" badge when every variant is out of stock (requested after Fissile sold out).
- No tracking changes.

## 2025-11-24: Black Friday landing page update
- Replaced the Fissile hero with Mackenzie airbag pack and Matier ski offers, at Priya's request.
- Published November 27 for launch at midnight on November 28.
- No tracking changes.

## 2025-12-15: Fissile back in stock
- Removed the sold-out state and added a "Back in stock" label on Fissile.
- No tracking changes.

## 2025-12-18: Tracking spec update
- Updated the tracking spec to v2.2 with the `event_id` rule for the Conversions API gateway.
