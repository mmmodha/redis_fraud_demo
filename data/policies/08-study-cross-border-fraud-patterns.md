# Study Summary — Cross-Border Fraud Patterns

**Document type:** Industry study summary (synthetic, for training)

## Headline

Cross-border transactions — those where merchant country and cardholder
home country differ — account for roughly 18% of authorised volume but
about 31% of fraud loss by value. The over-representation is concentrated
in card-not-present cross-border activity; card-present cross-border
transactions, typically performed by genuine travellers, carry a fraud
ratio close to the portfolio average.

## Two distinct populations

The study identifies two populations within cross-border activity that
should not be treated the same:

1. **Genuine travellers.** Recognised by a coherent sequence of
   transactions: airline booking, hotel booking, local low-value spends
   (cafes, transit, taxis) in the destination country. Fraud ratio close
   to home-country baseline.
2. **Synthetic-traveller fraud.** A single high-value foreign transaction
   with no preceding travel-pattern signals. Fraud ratio 12× the genuine
   traveller population.

The single biggest reduction in foreign-travel false positives in the
study came from issuers that began consulting agent memory and chat
history for self-declared travel intent before deciding on a foreign
transaction. Those issuers cut foreign-travel decline rates by about half
while keeping fraud loss flat.

## Foreign-currency vs. foreign-country

Foreign-currency transactions executed on home soil (e.g. an online
booking with a foreign-currency merchant) carry only a 1.4× loss ratio.
The geographic mismatch is a stronger signal than the currency mismatch
on its own.

## Implications

- Always read agent memory for travel intent before declining a foreign
  transaction.
- Where travel-pattern evidence exists, lower step-up rate aggressively.
- Where no travel-pattern evidence exists, prefer step-up over decline
  unless other risk multipliers also fire.
