# Quant architecture

Quant work is how a claim earns the right to be shown. Phase 1 puts the gates in place and implements no models.

## Where numbers come from

A number on a screen eventually has one of three origins:

1. A verified observation, with a source id.
2. A deterministic calculation over those observations, with parameters and a code version.
3. A validated model run, with a dataset snapshot and a run id.

If none of the three exist, the UI says the value is unavailable. It does not estimate one.

## The gate in code

`backend/app/domains/pipeline.py` is the contract.

- `TradeProposal` cannot carry a probability, a quantity, or a leverage. Extra fields are rejected.
- A long or short proposal requires at least one `EvidenceRef`.
- An evidence source of `llm`, `model`, `ai`, `guess`, or `opinion` is rejected. The model is not allowed to cite itself.
- `QuantValidation` cannot be `passed` without evidence references.
- `RiskDecision.decided_by` must be `deterministic_risk_engine`.
- `authorize_execution` refuses to build an intent when quant has not passed, when evidence is missing, when risk has not approved, or when policy withholds permission.
- The risk engine in `backend/app/domains/risk/engine.py` raises. It does not contain a temporary rule that approves everything.

WAIT and NO TRADE are valid proposal directions. They do not require evidence because they do not claim a directional trade. They also cannot be authorized for execution.

## What Phase 5 has to add

A run record should be able to answer:

- Which dataset snapshot
- Which parameters
- Which code version
- In-sample and out-of-sample separation
- Costs, funding, and slippage assumptions
- Whether the run completed, failed, or lacked evidence

The performance and strategy screens may cite a run id. They may not accept a typed-in win rate.

## Regime and opportunity

Regime labels (Phase 6) are outputs of features, not prompts. Opportunity cards (Phase 7) hang off evidence ids and a quant status. A missing invalidation is a failed card, not a card with a blank that the operator is expected to ignore.

## Determinism

Given the same inputs, the risk engine and the calculators return the same decision. They do not call a language model. AI may explain a decision after it exists. AI does not author the decision.

## Phase 1 limit

No statistic is computed. The quant domain is a boundary and a contract test, not a research platform.
