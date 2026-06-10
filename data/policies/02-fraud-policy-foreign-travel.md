# Fraud Detection Policy — Foreign Travel Transactions

**Document type:** Internal policy
**Owner:** Fraud Operations
**Applies to:** Card-present and card-not-present transactions where the
merchant country differs from the cardholder's stated home country.

## Why this policy exists

Foreign-travel transactions are a leading cause of false-positive declines.
Cardholders consistently report that a blocked card abroad is the single most
damaging customer experience the bank produces, more damaging than a missed
genuine fraud event of equal value. This policy therefore widens approval
tolerance when there is supporting context that the cardholder is genuinely
travelling.

## Definitions

- **Foreign transaction** — merchant country ≠ cardholder home country.
- **Cross-currency transaction** — transaction currency ≠ card billing
  currency.
- **Travel window** — a period during which a customer has signalled travel
  to a specific country, by any of the channels listed below.

## Travel signals (any one is sufficient)

A travel window is opened by any of:

1. A confirmed airline or hotel booking on the cardholder's account in the
   last 90 days, with destination country matching the merchant country.
2. A free-text travel intent captured by the chat or voice agent (e.g.
   "I'll be travelling 10–17 Nov to Singapore"). This is stored in agent
   memory and read on every relevant authorisation.
3. A self-service travel notice submitted via the mobile app.
4. Two or more prior approved transactions in the same merchant country in
   the last 180 days.

When at least one signal is present, the authorisation is **approved**
without step-up provided the other risk features are within normal bounds.

## Action when no travel signal is present

1. If the amount is below the cardholder's 90-day foreign p95, approve.
2. Otherwise, **step-up** via push notification. Never auto-decline a
   foreign transaction solely because it is foreign — that pattern accounts
   for the majority of historical false positives.

## Worked example

Cardholder Jane Doe, home country US, charges SGD 480 at a Singapore
boutique. Agent memory contains the note "travelling 10–17 Nov to
Singapore" and her account shows a Global Airways booking three weeks
earlier. Two travel signals are present, so the transaction is approved
without step-up.
