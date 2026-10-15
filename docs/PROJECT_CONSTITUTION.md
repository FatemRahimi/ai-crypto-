# Project constitution

These rules are non-negotiable. A later phase may add mechanism. It may not weaken a rule.

The API exposes only the flags the running process enforces or explicitly marks as not implemented. Policy that is not yet a control is labeled as such in `docs/SECURITY.md` and `docs/ARCHITECTURE.md`.

## 1. No evidence, no claim

The system does not state a market fact, a probability, a balance, a backtest, an expected return, a liquidation price, or an order-flow observation unless that statement comes from verified data, a deterministic calculation, or a validated quant model.

A language-model sentence is not evidence. An evidence reference must name a verifiable record. Citing `llm`, `model`, `ai`, `guess`, or `opinion` is rejected by the proposal contract.

Phase 1 enforcement: directional `TradeProposal` values require an evidence reference, and the UI sample panels are marked Demo. The absence of a market feed is reported as absence, not filled with a sample price.

## 2. AI cannot directly execute trades

AI output stops at a trade proposal. A proposal is not an order. It has no size, price, leverage, or credential.

The only path toward an exchange is:

AI or strategy → trade proposal → quant validation → deterministic risk engine → execution policy → restricted execution gateway → exchange adapter.

The AI package is not allowed to import the execution gateway. The Phase 1 gateway refuses every intent, including an intent that has passed the choke point.

## 3. The risk engine is deterministic

Risk approval is a deterministic decision. It is not a paragraph from a model. A risk decision whose author is anything other than `deterministic_risk_engine` is invalid.

Phase 1 does not implement risk rules. The installed engine refuses every evaluation. Missing inputs fail closed. They do not fail open.

## 4. This platform does not custody funds

User funds remain at the exchange. AI-Crypto is not a wallet, does not take deposits, and does not hold a balance of record. A future balance display must come from a verified exchange read.

## 5. Withdrawal permission is never required

Exchange integration, when it exists, must not request withdrawal or transfer-out permission. Read and, much later, tightly scoped trade permissions are separate decisions. Trade permission is not granted by connecting an account.

## 6. An LLM does not invent probabilities

A probability, expectancy, or confidence number requires a quant model run with a stored record. The proposal and validation contracts reject extra fields, including a probability attached to a proposal. The opportunities screen does not show one.

## 7. No fake backtests

A backtest result exists only as the output of a completed, reproducible run. Phase 1 has no backtest engine and the performance screen has no fabricated curve.

## 8. AI cannot bypass security boundaries

Model output cannot approve risk, disable the kill-switch invariant, widen CORS, read a secret into the browser, or call the execution gateway. Security configuration lives in process settings and middleware, not in prompts.

## 9. Simple interface, complex intelligence behind it

The interface stays calm and progressive. Research detail is closed until opened. The backend may grow many domains. The primary navigation stays the seven sections defined for this product.

## 10. Strategy and model changes require validation

A strategy is not active because a person, or a model, described it. Activation requires a compiled rule set and a quant validation record. Phase 1 stores neither, and the approve control is disabled.

## How a change is allowed to proceed

A change that touches orders, risk, capital, credentials, or a number shown to the operator must name which rule above it satisfies and which test shows the boundary still holds.
