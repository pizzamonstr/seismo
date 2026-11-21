# Tephra Site and Tracking Change Log: Q2 2025

*Maintained by Theo Nakamura, Nakamura Web Studio. Every production release to tephra.ca is logged here.*

---

## 2025-04-09: Custom pixel documentation
- Added the custom audience pixel to the tracking spec (now v2.1) so it is not lost in future theme work.
- No functional changes.

## 2025-04-22: Review app update
- Updated the product reviews app to the latest version.
- No tracking changes.

## 2025-05-06: GA4 Consent Mode v2 update
- Updated the cookie banner and GA4 configuration to Consent Mode v2, to meet the updated consent requirements.
- When a visitor declines analytics cookies, GA4 no longer records a full session. Some of these sessions are modelled by Google, and some are not counted.
- Expected effect: GA4 session counts will be lower than before. Shopify sessions, orders, and revenue are not affected.
- Meta pixel and Google Ads tags also respect the consent choice.
- Reviewed by: Jordan Leclerc

## 2025-05-12: End-of-Season Sale
- Set up the End-of-Season Sale collection and automatic discounts (25% off last season's Matier, Rohr, Fissile, Plinth, Bridge, Keyhole and Meadows). 150 Fissile boards held back from the sale.
- No tracking changes.

## 2025-06-17: Base layer size guide
- Added a size guide pop-up to Keyhole and Meadows product pages.
- No tracking changes.
