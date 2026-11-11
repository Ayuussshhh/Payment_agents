# Product vision

Status: specification v0.1, 11 November 2026.
Parent: [ENGINE.md](ENGINE.md).

## The product

Mandate is the infrastructure for controlled agentic commerce.

An organization states what an agent is allowed to buy. The agent can search, compare, and prepare a purchase. Mandate decides whether that proposal is still inside the policy, requires a person to approve the exact cart, and calls a payment provider only for the cart that was approved. If the cart changes, the approval is dead.

Customers will eventually reach that engine through:

- Mandate's own web application, the Agent Studio.
- External applications, through HTTP APIs and SDKs.
- Custom purchasing agents.
- Business procurement workflows.
- More than one payment provider.
- Third-party agent and skill integrations.

The studio is the interface a person uses. The engine is the product those other clients can use without opening the studio. The engine has its own version, its own tests, and documented contracts. It runs with the web application stopped.

## The first workflow

A budget owner says, in text:

> Order a Dell laptop for the team. The total must not exceed $800, including tax and delivery. At least 16 GB of RAM and a 512 GB SSD. No warranty and no accessories. Do not pay until I approve. Prefer something with good battery life.

The compiler returns a draft. "Good battery life" stays a preference. The owner activates the draft. The buyer lists the catalog and proposes SKUs. The catalog owns the price. The policy returns a reason code. The Dell that fits requires approval. The owner approves that cart hash. PayPal is asked for that amount. If the merchant price later moves, capture voids the authorization even when the new price is still under $800.

That sentence is the acceptance story for v0.8. The current prototype already demonstrates it against SQLite. The engine has to demonstrate it against PostgreSQL, with the same reason codes.

## What the platform is organized to do

1. Build. Agent definitions, model configuration, a skill registry, and published versions.
2. Control. Policies, permissions, budgets, approvals.
3. Execute. The agent runtime, the commerce engine, payment adapters.
4. Observe. Traces, audit events, financial history.
5. Extend. APIs, SDKs, webhooks, and later a marketplace of skills.

Control and execute come before a polished build surface. An external developer should be able to run an agent and a sandbox payment before the studio is feature-complete.

## What this is

- A policy and enforcement layer in front of payment providers.
- A versioned agent runtime whose tools are explicit and whose published versions are immutable.
- A commerce state machine that a provider adapter plugs into.
- An audit trail that can reconstruct one purchase from proposal to capture or void.

## What this is not

- A card network, a wallet, or a replacement for PayPal, Stripe, Razorpay, or Polar.
- A voice biometric. Speech can be a way to type a policy. It cannot approve a cart.
- An LLM that allows or denies a charge. The model may draft a policy and may propose a SKU. The decision function is ordinary code.
- A claim that the goods shipped match the listing. The engine sees what the catalog adapter returns.
- A guarantee about a provider's own fraud score. That score can still run after Mandate has allowed a cart.
- Legal clearance to move live money. Sandbox and test keys until there is a separate decision to touch a real account.

## The promise that is allowed after the tests pass

Until the tests in the porting gate pass, the following are intentions. After they pass, they are the product claims.

1. The agent process cannot read a payment-provider secret.
2. A provider create call happens only when a transaction row exists, the policy version is active, the cart hash equals the approved hash, and the amount still fits in the remaining budget, including other pending transactions.
3. A change to amount, currency, seller, SKU, or a line after approval makes that approval unusable.
4. Two concurrent attempts cannot both reserve the same last minor unit of a budget.
5. Retrying the same idempotency key does not create a second provider object.
6. A lost provider response leaves the transaction `unknown` until a retrieve or a verified webhook resolves it. The worker does not resolve the unknown by creating a new charge.
7. Model output cannot activate a policy, mark an approval valid, or move a transaction to `captured`.

## Vocabulary carried forward from the prototype

The engine uses the prototype's words so the existing tests still name real behavior.

| Idea | Value |
| --- | --- |
| Policy outcomes | `allow`, `deny`, `needs_approval` |
| A refused cart whose hash no longer matches | `intent_mismatch`, and the adapter voids rather than captures |
| Money | Integer minor units, plus an ISO currency code |
| A published policy or agent | A new row. The previous row is unchanged |

`REQUIRES_APPROVAL` in the draft plan is `needs_approval` in the engine and in the API.
