# Regulatory Summary — Anti-Money-Laundering (AML)

**Document type:** Regulatory guidance summary (synthetic, for training)
**Disclaimer:** This is an internal training summary written for the
demo. It is not a substitute for the bank's official AML manual or for
external counsel.

## Scope

AML controls focus on detecting and reporting the use of the bank's
products to move the proceeds of crime. They overlap with fraud controls
but have different objectives: fraud controls protect the bank and its
customers from unauthorised loss; AML controls protect the financial
system from misuse and the bank from regulatory penalty.

## Typologies the bank monitors

The bank's AML team monitors all customer activity for the typologies
below. A confirmed match produces a Suspicious Activity Report (SAR)
filed with the relevant financial-intelligence unit within 30 days.

1. **Structuring** — repeated transactions just below a reporting
   threshold, typically USD 10,000 in domestic markets.
2. **Rapid funnelling** — funds entering and leaving the account inside
   72 hours with no apparent economic purpose.
3. **Geographic mismatch** — sustained transactional activity in a
   country unrelated to the customer's declared residence or business.
4. **Mule indicators** — sudden onset of inbound transfers from many
   unrelated counterparties followed by outbound transfers to a small
   number of beneficiaries.
5. **High-risk corridor activity** — transfers to or from jurisdictions
   on the bank's enhanced-monitoring list, regardless of amount.

## Interaction with fraud decisions

AML is a separate workflow from real-time authorisation. The fraud agent
must not surface AML reasoning in customer-facing messages, and AML
investigators must not see the fraud agent's free-text reasoning unless
specifically requested through the case-management system. The two
workflows share underlying transaction data via Postgres and Redis but
operate under separate access controls.

## Record keeping

All authorisation decisions, step-up challenges, and SAR investigations
are retained for a minimum of 7 years.
