# Customer-Segment Guidance — New Account Handling

**Document type:** Customer-experience guidance
**Applies to:** Cardholders whose account is less than 90 days old.

## Why new accounts need special handling

New accounts lack the historical baseline that risk models rely on. They
are also disproportionately targeted by account-opening fraud and
synthetic-identity fraud. Treating new accounts with the same risk model
as established accounts either produces a high false-positive rate (if
thresholds are tight) or a high fraud-loss rate (if thresholds are
loose). This guidance describes the bank's middle path.

## Authorisation defaults for the first 30 days

- Maximum single-transaction amount: USD 1,500. Anything higher requires
  step-up regardless of risk score.
- Maximum 24-hour authorised amount: USD 4,000.
- Foreign transactions: **step-up by default** for the first 30 days
  regardless of travel signals. Travel-pattern context starts to
  contribute to the decision only after day 30.
- High-risk MCC transactions: decline if amount > USD 500.

## Authorisation defaults for days 31–90

- Standard velocity thresholds apply.
- Foreign transactions follow the standard foreign-travel policy.
- High-risk MCC transactions follow the standard merchant-category
  guidance.
- Step-up is still preferred to decline for any ambiguous decision.

## Graduation

After 90 days of authorised activity without confirmed fraud, the account
graduates to the standard portfolio defaults. Graduation is automatic and
does not require operator action.

## Cross-references

- KYC policy: a new-account flag is cleared only after KYC level 2 is
  complete; an account with KYC level 1 stays on new-account defaults
  indefinitely.
- Velocity policy: thresholds in this document override the standard
  velocity table for the first 30 days.
