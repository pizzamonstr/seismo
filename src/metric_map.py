"""General marketing knowledge: terms and what moves each metric."""

import re

GLOSSARY = """Marketing terms:
- CPA: cost per acquisition, ad spend divided by conversions \
(also cost per purchase).
- CAC: customer acquisition cost, ad spend divided by new \
customers. Blended CAC uses all ad spend.
- ROAS: return on ad spend, revenue divided by ad spend.
- MER: marketing efficiency ratio, total revenue divided by total \
ad spend. aMER uses new customer revenue only.
- AOV: average order value.
- CPM: cost per 1,000 impressions. CTR: click-through rate. \
CPC: cost per click.
- Frequency: how many times the average person saw an ad.
- Prospecting: ads to new people. Retargeting: ads to people who \
already visited or engaged, built from custom audiences that \
pixel events feed.
- PMax: Google Performance Max. CAPI: Meta Conversions API.
- BFCM: Black Friday and Cyber Monday.
- Platform-reported numbers come from Meta or Google and can \
double count or miss sales. Shopify numbers are actual orders."""

GENERAL_CAUSES = [
    "site or theme changes",
    "tracking or pixel changes",
    "budget changes",
    "promotions",
    "stock problems",
    "seasonality",
]

METRIC_DRIVERS = {
    "retargeting": [
        "custom audience size", "pixel events", "tracking scripts",
        "frequency", "site traffic",
    ],
    "prospecting": [
        "creative", "targeting", "CPM", "budget", "new audiences",
    ],
    "cpa": [
        "conversions tracked", "audience size", "bids", "budget",
        "creative", "conversion rate",
    ],
    "cac": [
        "new customers", "ad spend", "returning customer share",
        "promotions",
    ],
    "roas": [
        "revenue tracked", "attribution", "discounts",
        "average order value",
    ],
    "mer": ["total Shopify revenue", "total ad spend"],
    "conversion rate": [
        "site changes", "checkout", "page speed", "stock",
        "promotions", "traffic quality",
    ],
    "orders": [
        "traffic", "conversion rate", "stock", "promotions",
        "seasonality",
    ],
    "revenue": [
        "orders", "average order value", "discounts", "stock",
        "launches", "seasonality", "channel mix changes",
        "budget shifts between campaigns", "brand search",
    ],
    "sales": [
        "orders", "average order value", "discounts", "stock",
        "launches", "seasonality", "channel mix changes",
        "budget shifts between campaigns", "brand search",
    ],
    "aov": ["discounts", "product mix", "promotions"],
    "sessions": [
        "GA4 consent mode", "tracking changes", "traffic sources",
    ],
    "traffic": [
        "GA4 consent mode", "tracking changes", "campaigns",
        "traffic sources",
    ],
    "cpm": ["auction competition", "seasonality", "audience size"],
    "ctr": ["creative", "ad fatigue", "frequency"],
    "frequency": ["audience size", "budget", "creative refresh"],
    "conversions": [
        "pixel", "Conversions API", "deduplication", "attribution",
    ],
    "purchases": [
        "pixel", "Conversions API", "deduplication", "attribution",
    ],
    "branded search": [
        "Performance Max", "brand cannibalization", "attribution",
    ],
    "email": [
        "Klaviyo flows", "list size", "send frequency",
        "deliverability",
    ],
}


METRIC_ALIASES = {
    "cost per acquisition": "cpa",
    "cost per purchase": "cpa",
    "customer acquisition cost": "cac",
    "acquisition cost": "cac",
    "return on ad spend": "roas",
    "marketing efficiency ratio": "mer",
    "average order value": "aov",
    "click-through rate": "ctr",
    "click through rate": "ctr",
    "cost per thousand": "cpm",
    "performance max": "branded search",
    "pmax": "branded search",
    "klaviyo": "email",
    "remarketing": "retargeting",
}


def find_metrics(question):
    """List the metrics a question names, using aliases too."""
    lowered = question.lower()
    metrics = []
    for metric in METRIC_DRIVERS:
        if re.search(r"\b" + metric + r"\b", lowered):
            metrics.append(metric)
    for alias in METRIC_ALIASES:
        metric = METRIC_ALIASES[alias]
        if alias in lowered and metric not in metrics:
            metrics.append(metric)
    return metrics


def find_drivers(question):
    """List the usual causes for the metrics a question names."""
    drivers = []
    for metric in find_metrics(question):
        for driver in METRIC_DRIVERS[metric]:
            if driver not in drivers:
                drivers.append(driver)
    for cause in GENERAL_CAUSES:
        if cause not in drivers:
            drivers.append(cause)
    return drivers


def build_cause_text(question):
    """Write a second search that looks for likely causes."""
    drivers = find_drivers(question)
    return f"{question} Possible causes: {', '.join(drivers)}."