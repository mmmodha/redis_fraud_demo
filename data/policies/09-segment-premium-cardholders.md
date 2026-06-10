# Customer-Segment Guidance — Premium Cardholders

**Document type:** Customer-experience guidance
**Owner:** Cards Product & Fraud Operations
**Applies to:** Cardholders flagged `segment=premium`.

## Why premium customers are different

Premium cardholders generate roughly 4× the interchange revenue per active
card compared to the standard portfolio. A declined transaction for a
premium cardholder is therefore much more costly than for a standard
cardholder, both in direct lost interchange and in retention risk.
Internal exit-survey data shows that "card declined unexpectedly" is the
second-most common reason premium cardholders close accounts, after
"better rewards available elsewhere".

## Guidance for authorisation decisions

1. **Prefer step-up over decline** for ambiguous decisions. Premium
   cardholders complete step-up challenges at a 92% success rate vs. 78%
   for the standard portfolio; the upside on completion is high.
2. **Wider velocity tolerances.** All velocity thresholds are multiplied
   by 1.5 for premium cardholders (see velocity policy).
3. **Faster cool-down.** After a successful step-up, the cool-down before
   the next challenge is 10 seconds (vs. 30 for standard).
4. **Concierge handoff for hard declines.** When a transaction is declined
   for a premium cardholder, automatically open a contact-centre task with
   the cardholder's preferred channel and time of day pre-filled.

## Travel expectations

Premium cardholders travel internationally about 3.5× more than the
standard portfolio. Treat foreign transactions with a strong bias toward
approval whenever any travel signal is present (see foreign-travel
policy).

## Communication

When a premium cardholder is stepped up or declined, the customer-facing
message should never expose internal risk reasons. Use the standard
phrasing in the customer-communication style guide: "We just need to
double-check this transaction with you" rather than "We blocked your card".
