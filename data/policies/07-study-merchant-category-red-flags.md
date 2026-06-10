# Study Summary — Merchant Category Red Flags

**Document type:** Industry study summary (synthetic, for training)

## High-risk categories

Across the industry, a small number of merchant category codes carry
disproportionately high fraud-loss ratios. The list below uses standard
4-digit MCCs.

| MCC | Description | Approximate loss ratio |
| --- | --- | --- |
| 5732 | Electronics stores | 4.1× portfolio average |
| 5944 | Jewelry & watches | 3.8× |
| 6051 | Quasi-cash & crypto exchanges | 5.7× |
| 7995 | Gambling | 6.2× |
| 5651 | Family clothing (luxury) | 2.4× |
| 7011 | Hotels & lodging | 1.6× (skewed by no-show charges) |

## Patterns worth noting

- **Electronics + new device + cross-border** is the single most reliable
  manual-review trigger in the dataset.
- **Quasi-cash and crypto** transactions carry the highest unit loss but
  are also the most likely to be successfully reversed within 24 hours;
  speed of intervention matters more than precision.
- **Hotels** carry a deceptively high loss ratio because legitimate
  pre-authorisation holds are often followed by stayover adjustments;
  models that compare authorisation amount to final settlement reduce false
  positives substantially.

## Low-risk categories

Categories 5411 (grocery), 5814 (coffee shops), 4111 (transit), 5541 (fuel)
and 5912 (pharmacy) consistently exhibit fraud-loss ratios below 0.3× the
portfolio average. These categories should attract more permissive
velocity thresholds and shorter step-up cool-downs.

## Use in this bank

The bank's fraud policies refer to the high-risk MCC list above as
"high-risk merchant categories" without enumerating the codes every time.
Treat MCC 5732, 5944, 6051 and 7995 as the canonical high-risk set unless
overridden by a more specific policy.
