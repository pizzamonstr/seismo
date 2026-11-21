# Proposal: Move Meta Conversions API to a Server-Side Gateway

*From: Theo Nakamura, Nakamura Web Studio*
*To: Priya Sandhu, Jordan Leclerc*
*Date: August 20, 2025*

## Summary

I recommend moving our Meta Conversions API (CAPI) connection from the Shopify app's built-in integration to a server-side gateway before the fall season. The main benefit is better Event Match Quality (EMQ), which helps Meta find buyers more efficiently.

## Why now

- Our Purchase EMQ is 6.1 out of 10. Tarn Digital says 8 or higher is a good target.
- The built-in integration sends limited customer information with each event.
- Fall is our biggest season. Better signal in September means Meta has learned more before October to December.

## What changes

| | Today | After the change |
|---|---|---|
| Browser pixel | Fires on the site | No change |
| Server events | Sent by the Shopify app | Sent by the gateway |
| Customer information sent | Email | Email, phone, address (all hashed) |
| Expected Purchase EMQ | 6.1 | 8 or higher |

## Risks

- **Duplicate events.** When we send the same purchase from both the browser and the server, Meta needs the same `event_id` on both to count it once. I'll configure the gateway to match.
- **A short learning period** for Meta campaigns after the switch. I'd expect a few days of noise at most.

## Cost

- Gateway hosting: about $60 CAD per month
- Setup: 6 hours

## Timeline

- Build and test: week of September 1, 2025
- Go live: September 9, 2025

## Decision needed

Priya, please confirm by August 29 and I'll schedule it.

---

*Reply from Priya Sandhu, August 22, 2025: Approved. Please go ahead for September 9. Loop in Tarn so they know to expect some noise.*
