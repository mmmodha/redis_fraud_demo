# Fraud Detection Policy — Step-Up Authentication

**Document type:** Internal policy
**Owner:** Fraud Operations & Identity

## Purpose

Step-up authentication is the bank's preferred response to an ambiguous
authorisation. It moves the burden of proof to the cardholder for a few
seconds rather than declining outright, and historically converts more than
70% of ambiguous decisions into a successful approval.

## When step-up is triggered

Any one of the following raises a step-up flag:

- Velocity thresholds (see velocity policy) breached.
- Foreign transaction without a travel signal (see foreign-travel policy).
- New device + amount over USD 250.
- High-risk merchant category (jewelry, electronics, quasi-cash, gambling)
  on a card that has no history with that category in the last 180 days.
- Agent verdict of `review` rather than `approve` or `decline`.

## Step-up channels (in order of preference)

1. **Push notification** to the mobile app with biometric confirmation.
   Median completion time 8 seconds. Used for ≈85% of all challenges.
2. **3-D Secure** browser challenge for card-not-present web transactions.
3. **One-time passcode by SMS** as a last resort. SMS is deprecated for new
   enrolments due to SIM-swap risk.
4. **Outbound voice callback** for transactions over USD 5,000 or for
   cardholders who have opted into voice verification.

## Outcomes

- Successful step-up → authorisation approves, decision logged with the
  challenge method used.
- Failed or timed-out step-up → authorisation declines, card placed in
  `review` state for 24 hours, customer notified via email and push.
- Three consecutive step-up failures within 60 minutes → card temporarily
  blocked, mandatory call to the contact centre to reinstate.

## Cardholder experience

Step-ups must complete in under 30 seconds end-to-end including network
round-trips. Step-up rate per cardholder per month is a quarterly KPI; the
target is below 1.5%.
