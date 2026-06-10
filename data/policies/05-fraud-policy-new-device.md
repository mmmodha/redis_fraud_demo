# Fraud Detection Policy — New Device Handling

**Document type:** Internal policy
**Owner:** Fraud Operations & Identity

## Definition

A **new device** is a device fingerprint that has not been associated with
the cardholder for at least 30 days. This includes:

- A device never previously seen on the account.
- A device seen previously but more than 30 days ago.
- A previously known device whose hardware fingerprint has materially
  changed (OS major version skip, root/jailbreak detected, attestation
  failure).

## Risk multipliers

A new device alone is not sufficient to decline a transaction. It is a
multiplier applied to other risk signals:

| Combined signal | Multiplier on base risk score |
| --- | --- |
| New device only | 1.3 |
| New device + foreign country | 2.0 |
| New device + high-risk MCC | 2.0 |
| New device + foreign country + high-risk MCC | 3.5 |
| New device + foreign country + high-risk MCC + amount > USD 1,000 | 5.0 — decline by default |

The combined signal of **new device + new country + high-risk merchant
category** is the strongest single fraud predictor in the bank's portfolio.
When the amount also exceeds USD 1,000 the transaction is declined by
default and the account is placed in step-up-for-everything mode for the
next 24 hours.

## Worked example

Cardholder Alex Chen, home country US, normally transacts on a single
macOS device with low-risk merchants. A USD 2,400 charge arrives from a
Sao Paulo electronics merchant on an unknown Android device. All three
multipliers apply and the amount exceeds USD 1,000, so the authorisation
is declined and the account flagged for step-up.

## Device-trust uplift

The risk multipliers decay over time. After 30 days of consistent
authorised use, a new device becomes a "trusted device" and the multiplier
returns to 1.0.
