# Fraud Detection Policy — Velocity Thresholds

**Document type:** Internal policy
**Owner:** Fraud Operations

## Definitions

- **Velocity** — number of authorisation attempts on the same card or
  account within a sliding time window.
- **Amount velocity** — cumulative authorised amount within a sliding time
  window.

## Standard thresholds

| Window | Count threshold | Amount threshold (USD) |
| --- | --- | --- |
| 60 seconds | 4 | 750 |
| 5 minutes | 8 | 1,500 |
| 1 hour | 15 | 3,500 |
| 24 hours | 40 | 8,000 |

Breaching any cell in this table triggers **step-up authentication**, not an
immediate decline.

## Premium-cardholder overrides

For cardholders flagged as `segment=premium`, multiply every threshold by
1.5. Premium cardholders also receive a 10-second cool-down after a step-up
challenge instead of the standard 30-second cool-down.

## Merchant-category exceptions

For low-risk recurring merchants (categories 5411, 5814, 5912, 4111), the
60-second count threshold is raised from 4 to 7. This handles the common
case of contactless tap-to-pay being retried at terminals with intermittent
network connectivity.

## Operator override

Fraud operators may temporarily relax thresholds for a specific cardholder
via the operator console. Such overrides expire automatically after 72 hours
and are logged for audit.
