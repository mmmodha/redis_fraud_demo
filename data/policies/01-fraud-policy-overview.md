# Fraud Detection Policy — Overview

**Document type:** Internal policy
**Owner:** Fraud Operations
**Applies to:** All card products (debit, credit, prepaid)

## Purpose

This policy describes how the bank decides whether to approve, review, or
decline a card-based payment in real time. The bank's stated tolerance is to
keep false-positive declines below 2% of approved volume while keeping
confirmed fraud loss under 7 basis points of authorised spend.

## Layered model

Every authorisation request is evaluated by four layers in sequence. Any layer
can short-circuit the decision:

1. **Hard blocks** — sanctions lists, frozen accounts, cards reported lost.
2. **Statistical features** — amount, velocity, merchant category code,
   geography vs. cardholder home country, device trust score.
3. **Customer context** — recent travel, scheduled large purchases, prior
   merchant relationships, agent memory notes from chat/voice channels.
4. **Agent review** — for ambiguous decisions an LLM-driven agent consults
   feature store, context retriever and memory before issuing a verdict.

## Outcomes

A decision is always one of: **approve**, **step-up authentication**, or
**decline**. "Step-up" means the cardholder must complete a 3-D Secure
challenge, a push notification confirmation, or a callback before the
transaction settles.

## Latency budget

The bank targets a hard p95 of **1,000 ms** end-to-end for the authorisation
decision. Layers 1–2 must complete in under 50 ms; layers 3–4 share the
remaining 950 ms.

## Review cadence

This policy is reviewed quarterly by the Fraud Operations Committee.
Threshold values referenced by sibling policy documents (velocity, foreign
travel, new device) live in those documents, not here.
