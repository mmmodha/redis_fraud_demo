# Policy & study corpus

Small, deterministic Markdown corpus loaded by the chatbot backend at startup
and embedded into a Redis vector index. Both the plain-RAG pipeline and the
Context Surface pipeline retrieve from this same corpus so the demo's
side-by-side comparison is fair.

| File | Category |
| --- | --- |
| `01-fraud-policy-overview.md` | Bank policy |
| `02-fraud-policy-foreign-travel.md` | Bank policy *(references Jane's scenario)* |
| `03-fraud-policy-velocity-thresholds.md` | Bank policy |
| `04-fraud-policy-step-up-auth.md` | Bank policy |
| `05-fraud-policy-new-device.md` | Bank policy *(references Alex's scenario)* |
| `06-study-card-not-present-trends.md` | Fraud study |
| `07-study-merchant-category-red-flags.md` | Fraud study |
| `08-study-cross-border-fraud-patterns.md` | Fraud study |
| `09-segment-premium-cardholders.md` | Customer segment |
| `10-segment-travel-friendly-cards.md` | Customer segment |
| `11-segment-new-account-handling.md` | Customer segment |
| `12-regulatory-kyc-summary.md` | Regulatory (synthetic) |
| `13-regulatory-aml-summary.md` | Regulatory (synthetic) |

All content is synthetic. Nothing here is copied from real bank policies,
real fraud research papers, or real regulator publications.
