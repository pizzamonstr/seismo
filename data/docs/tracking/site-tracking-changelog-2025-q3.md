# Tephra Site and Tracking Change Log: Q3 2025

*Maintained by Theo Nakamura, Nakamura Web Studio. Every production release to tephra.ca is logged here.*

---

## 2025-07-01: Sale discount update
- End-of-Season Sale discounts increased to 40%.
- No tracking changes.

## 2025-07-10: Shipping pause banner
- Added a banner for the warehouse move: orders placed July 14 and 15 will ship from July 16.
- Banner removed July 16.
- No tracking changes.

## 2025-07-29: Checkout address autocomplete
- Enabled address autocomplete in checkout.
- No tracking changes.

## 2025-08-20: Conversions API gateway proposal sent
- Sent Priya and Jordan a proposal to move Meta Conversions API to a server-side gateway for better match quality. See "meta-capi-gateway-proposal-2025-08.md".

## 2025-09-09: Meta Conversions API moved to server-side gateway
- Switched Meta Conversions API from the Shopify Facebook and Instagram app's built-in connection to a server-side gateway.
- The gateway sends Purchase, AddToCart, InitiateCheckout, and ViewContent events with more customer information (hashed email, phone, and address), which should improve Event Match Quality.
- The browser pixel stays in place. Meta deduplicates browser and server events that share the same event name and `event_id`.
- Gateway `event_id` for Purchase is set from the checkout token.
- Checked after release: server events arriving in Events Manager. Event Match Quality for Purchase went from 6.1 to 8.4 within two days.
- Reviewed by: Jordan Leclerc

## 2025-09-01: End-of-Season Sale ended
- Removed sale discounts and the sale collection (sale ended August 31).
- No tracking changes.

## 2025-09-15: 2025/26 season launch
- Published product pages for the new season: Pylon splitboard, Owl pack, Spearhead poles, Wedge crampons, Portage straps, Pioneer repair kit, Anderson wax, Birken liners, Blowdown gaiters, women's Matier and Rohr.
- Published fall collection pages for Pylon, Fissile and Matier, with new hero images.
- New products added to the Google Shopping feed.
- No tracking changes.
