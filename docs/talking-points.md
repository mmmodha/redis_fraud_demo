# Talking Points — Fraud Command Center

Printable single page. The 10 lines worth memorizing for the webinar,
in roughly the order they belong in the demo.

---

## Opener / headline

1. **"Sub-second fraud decisions, powered by real-time context."**
   The whole demo in seven words.

2. **"A bank's job isn't just to block fraud — it's to not block Jane
   when she's actually shopping in Singapore."**
   Frames why context matters more than a smarter model.

## During the IRIS hero beats

3. **"The Feature Store keeps the velocity counters under 10 ms — that's
   why this decision finishes before the swipe completes."**
   Use after Mike or Alex when the latency badge shows on the verdict.

4. **"Agent Memory is the bank's institutional memory of you —
   travel plans, prior disputes, devices we know. It's the layer that
   lets the agent say 'I know you'."**
   Drop after Jane's verdict flips.

5. **"Context Retriever is more than a vector index — it's an entity
   graph plus typed tools the LLM can call. The same tools you see in
   the Redis Cloud Console are what Claude is calling right now."**
   Pair this with the tab switch to Redis Cloud Console.

6. **"RDI is the pipe. It streams every change in the bank's source
   database into Redis in milliseconds, so the agent is never looking
   at stale data."**
   Use when pointing at the RDI panel or `stream:transactions` in
   Redis Insight.

## The chatbot comparison (the money moment)

7. **"Same Claude model. Same policy docs. Different context."**
   The mantra. Say it at least twice. Once after turn 1 of the chatbot
   comparison, once at the close.

8. **"RAG gives you the bank's policy. IRIS gives you the bank's
   policy *plus the customer sitting in front of you*. That's the
   difference."**

9. **"This kills the 'why don't I just use an LLM with RAG' question
   in a single click — because we're using an LLM with RAG. Plus
   IRIS."**

## Closer

10. **"This is what an AI-native bank looks like: deterministic where
    it has to be, contextual where it needs to be, sub-second
    everywhere. All on Redis."**

---

## Bonus lines (use if asked)

- *Latency:* "Every decision you saw was end-to-end under a second —
  feature read, context retrieval, memory lookup, Claude call, response.
  P95 stays under a second across 100 sequential decisions."
- *Cost:* "We're using prompt caching on Claude, so the policy
  preamble is only paid for once per session."
- *Production framing:* "The RDI configs you see in this repo are
  real RDI-shape YAML. Lift them straight into the production RDI
  Helm chart and point them at your real source DB — same config."
