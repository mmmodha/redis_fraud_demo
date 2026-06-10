# Study Summary — Card-Not-Present (CNP) Fraud Trends

**Document type:** Industry study summary (synthetic, for training)
**Period covered:** Notional 2023–2025 industry data

## Headline finding

Card-not-present transactions account for an estimated 72% of card fraud
loss by value across the industry, despite representing only 38% of
authorised volume. CNP fraud loss has grown at roughly twice the rate of
card-present fraud over the period, driven by account-takeover attacks and
phishing-led credential theft rather than physical card cloning.

## Risk drivers

The strongest predictors of CNP fraud in the dataset were:

1. New device fingerprint on the cardholder account.
2. Mismatch between billing address country and shipping address country.
3. Merchant categories 5732 (electronics), 5944 (jewelry), 6051
   (quasi-cash) and 5912 (pharmacy — high-value).
4. Multiple low-value test charges within 5 minutes of a large charge.
5. Use of a one-time email alias (sub-addressing or disposable domains)
   for the merchant account.

## Recommended controls

- Combine 3-D Secure with risk-based decisioning so low-risk CNP
  transactions skip the challenge entirely. Industry-wide, this approach
  has reduced CNP step-up rates by 60% without raising fraud loss.
- Apply device-trust scoring to the merchant-presented device fingerprint
  whenever the issuer is permitted to see it.
- Treat the combination of new device and high-risk merchant category as a
  decline-by-default rule for amounts over USD 1,000.

## Caveat

The data informing this summary is aggregated and anonymised. Specific
percentages should be treated as directional rather than authoritative.
