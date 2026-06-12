import type { HeroProfile } from "./types";

// Mirrors data/heroes.py TRIGGERS — same canonical transactions the backend
// scores when given a hero customer_id. ``bio`` + ``scenario`` carry the
// Wave 7f+ locked stage copy (quiz-mode hero cards).
export const HEROES: HeroProfile[] = [
  {
    key: "mike",
    customer_id: "cust_mike",
    card_id: "card_mike_visa",
    cardLast4: "1234",
    name: "Mike Rivera",
    firstName: "Mike",
    bio: "Austin, TX. Card ending 1234. Tech consultant. Active customer with a predictable rhythm — weekly coffee runs at Radio Coffee, weekend H-E-B groceries, occasional gas top-ups. Zero past disputes in 12 months.",
    scenario: "Mike's card was just tapped at Radio Coffee, Austin for $6.75.",
    expectedVerdict: "approve",
    homeCity: "Austin",
    homeCountry: "US",
    transaction: {
      amount: 6.75,
      currency: "USD",
      merchant_id: "merch_mike_coffee",
      merchant_name: "Radio Coffee & Beer",
      country: "US",
      city: "Austin",
      is_foreign: false,
      is_card_present: true,
    },
  },
  {
    key: "jane",
    customer_id: "cust_jane",
    card_id: "card_jane_visa",
    cardLast4: "7788",
    name: "Jane Doe",
    firstName: "Jane",
    bio: "San Francisco, CA. Card ending 7788. Strategy consultant at a global firm. Card sees occasional international use during client travel. Frequent SFO airport spender. Zero past disputes in 12 months.",
    scenario:
      "Jane's card was just tapped at Orchard Luxe Boutique, Singapore for S$1,820.",
    expectedVerdict: "approve",
    homeCity: "San Francisco",
    homeCountry: "US",
    transaction: {
      amount: 1820,
      currency: "SGD",
      merchant_id: "merch_jane_boutique_sg",
      merchant_name: "Orchard Luxe Boutique",
      country: "SG",
      city: "Singapore",
      is_foreign: true,
      is_card_present: true,
    },
  },
  {
    key: "alex",
    customer_id: "cust_alex",
    card_id: "card_alex_visa",
    cardLast4: "3344",
    name: "Alex Chen",
    firstName: "Alex",
    bio: "San Francisco, CA. Card ending 3344. Software engineer at a Bay Area startup. Frequent online electronics buyer — laptops, monitors, peripherals. Five-year customer with auto-pay on file. Zero past disputes in 12 months.",
    scenario:
      "Alex's card just attempted $1,240 at an electronics merchant in São Paulo, Brazil.",
    expectedVerdict: "block",
    homeCity: "San Francisco",
    homeCountry: "US",
    transaction: {
      amount: 1240,
      currency: "USD",
      merchant_id: "merch_alex_electronics_br",
      merchant_name: "MegaTech Eletronicos",
      country: "BR",
      city: "Sao Paulo",
      is_foreign: true,
      is_card_present: false,
    },
  },
  {
    key: "sarah",
    customer_id: "cust_sarah",
    card_id: "card_sarah_visa",
    cardLast4: "9911",
    name: "Sarah Kim",
    firstName: "Sarah",
    bio: "Seattle, WA. Card ending 9911. Marketing manager at a software company. Quarterly business trips, mostly East Coast. Active customer with no past disputes in 18 months.",
    scenario:
      "Sarah's card was just tapped at Tiffany & Co Manhattan for $1,450.",
    expectedVerdict: "review",
    homeCity: "Seattle",
    homeCountry: "US",
    transaction: {
      amount: 1450,
      currency: "USD",
      merchant_id: "merch_sarah_tiffany_ny",
      merchant_name: "Tiffany & Co Manhattan",
      country: "US",
      city: "New York",
      is_foreign: false,
      is_card_present: true,
    },
  },
];

export function heroByCustomer(id: string): HeroProfile | undefined {
  return HEROES.find((h) => h.customer_id === id);
}
