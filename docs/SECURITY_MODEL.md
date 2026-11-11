# Security model

Status: specification v0.1, 11 November 2026.
Parent: [ENGINE.md](ENGINE.md). Enforcement points: [ENGINE_DESIGN.md](ENGINE_DESIGN.md).

Authentication answers who is calling. Authorization answers what that caller may do. Financial control answers whether this cart may move money. Three different checks. A pass on one does not imply a pass on the next.

The HTML handbook page `security.html` remains the threat essay. This file is the model the new code has to implement. The attack cases at the bottom are inherited from that page and from the prototype tests.

## Authentication

Better Auth 1.7.20 establishes browser identity for the Next.js application. It stores its users and sessions in the `auth` schema. Mandate memberships point at `auth.user.id`.

This is a deliberate choice against the draft plan's Auth.js default. As of 11 November 2026, `next-auth` stable is 4.24.15, and Auth.js v5 is `5.0.0-beta.32` with no stable release since the beta line began. The identity port is `Identity.authenticate`. A future stable Auth.js, or another issuer, replaces the adapter. It does not replace the role names, the CASL catalog, or the Python checks.

Better Auth is used for identity only. Its organization and permission plugins are not the authorization system for Mandate. One role model exists, and it is the catalog in this file.

| Caller | How the API authenticates |
| --- | --- |
| Studio user | Better Auth session. The web server calls the API with the session token. The API resolves the user from the `auth` session tables using the same secret |
| External application | `Authorization: Bearer mdt_...`. The API hashes the secret and looks up `identity.api_keys`. A revoked key fails |
| Worker | A process credential, not a user. It may expire approvals and publish the outbox. It may not approve a cart or capture a payment on its own initiative |
| Agent graph | No credential of its own. It runs inside a user- or key-initiated `ExecutionContext` |

`authenticate` failure is `unauthenticated` and HTTP 401. A missing membership is HTTP 404 on the organization resource.

Browser CASL checks hide buttons. They are not a control. Every mutating API route calls `authorize_action` before the subsystem method.

## The catalog

`contracts/permissions.json` is the source both sides load. CASL rules in the web app are generated from it. The Python authorizer reads the same file from the package data. A string that exists on only one side is a failed test.

```json
{
  "actions": ["read", "create", "update", "publish", "activate", "approve", "reject", "execute", "configure", "revoke"],
  "subjects": [
    "Organization",
    "Membership",
    "Agent",
    "AgentVersion",
    "AgentRun",
    "ModelConfig",
    "Skill",
    "Policy",
    "PolicyVersion",
    "Approval",
    "Transaction",
    "ProviderAccount",
    "ApiKey",
    "AuditEvent"
  ],
  "roles": {
    "owner": ["manage:all"],
    "admin": [
      "read:Organization",
      "update:Organization",
      "create:Membership",
      "update:Membership",
      "read:Membership",
      "create:Agent",
      "update:Agent",
      "publish:AgentVersion",
      "read:Agent",
      "read:AgentRun",
      "execute:AgentRun",
      "configure:ModelConfig",
      "read:ModelConfig",
      "create:Skill",
      "read:Skill",
      "read:Policy",
      "read:PolicyVersion",
      "read:Approval",
      "read:Transaction",
      "configure:ProviderAccount",
      "read:ProviderAccount",
      "create:ApiKey",
      "revoke:ApiKey",
      "read:ApiKey",
      "read:AuditEvent"
    ],
    "developer": [
      "read:Organization",
      "create:Agent",
      "update:Agent",
      "publish:AgentVersion",
      "read:Agent",
      "read:AgentRun",
      "execute:AgentRun",
      "configure:ModelConfig",
      "read:ModelConfig",
      "create:Skill",
      "read:Skill",
      "read:Policy",
      "read:PolicyVersion",
      "read:Transaction"
    ],
    "finance_manager": [
      "read:Organization",
      "read:Policy",
      "create:Policy",
      "activate:PolicyVersion",
      "read:PolicyVersion",
      "read:Approval",
      "read:Transaction",
      "read:AuditEvent"
    ],
    "approver": [
      "read:Organization",
      "read:PolicyVersion",
      "read:Approval",
      "approve:Approval",
      "reject:Approval",
      "read:Transaction"
    ],
    "viewer": [
      "read:Organization",
      "read:Agent",
      "read:AgentRun",
      "read:Skill",
      "read:Policy",
      "read:PolicyVersion",
      "read:Approval",
      "read:Transaction",
      "read:AuditEvent"
    ]
  }
}
```

`manage:all` expands to every action on every subject. It is owner-only. Admin does not receive `activate:PolicyVersion` or `approve:Approval`. The person who turns a policy on and the person who approves a cart are different roles. Owner can hold both jobs in a one-person organization, and the audit event still records which action ran.

Illustrative CASL, built from the catalog rather than handwritten per screen:

```javascript
can("read", "Agent");
can("create", "Agent");
can("publish", "AgentVersion");
can("activate", "PolicyVersion");
can("approve", "Approval");
can("read", "Transaction");
```

An action in a React component that is not in the catalog fails the catalog test. The same is true for a Python `authorize_action` call.

## Agent permissions

An agent may execute a skill only when all of these are true:

1. The skill version is attached to the published agent version that the run resolved.
2. The skill name is in the execution context allowlist, which starts as the attached set and may be narrowed by the caller.
3. The skill's `required_permissions` are included in the context. Narrowing never adds a skill that the version omitted.
4. `validate_call` accepts the arguments against `input_schema`.

PayPal operations are absent from the skill catalog. A published version that names a skill outside the registry fails at publish time.

The context allowlist is built by the runtime from the version row. Tool arguments cannot add to it.

## Financial permissions

`approve:Approval` lets a person call the approve endpoint. The approval service still requires:

- The evaluation is `needs_approval`.
- The recomputed cart hash equals the hash on the proposal.
- The policy version is the version named on the proposal, and it is active.
- The approver's membership is in this organization.
- The approval is `pending` and unexpired.

`execute` on a transaction is not an action in the catalog on purpose. Capture, void, and refund are commerce methods. They require `approve`-level ownership of the flow only through the stored approval, plus a user or API key that has `read:Transaction` and a dedicated commerce grant:

| Method | Catalog action |
| --- | --- |
| `prepare` | `execute:AgentRun` is not sufficient. The action is `create:Transaction` |
| `authorize` | `update:Transaction` |
| `capture`, `void`, `refund` | `update:Transaction` |

Add these actions to the catalog when the commerce routes are added, in the same revision as the routes. Owner has them through `manage:all`. Admin has `create:Transaction` and `update:Transaction` only if the organization explicitly wants operators to drive sandbox payments. The default admin list above does not include them. The finance manager receives `create:Transaction` and `update:Transaction` in the v0.8 revision of the catalog, together with the routes. That revision is a catalog change with a test, not a silent extra `can`.

The policy evaluator does not read CASL. A finance manager who can activate a policy still gets `over_budget` when the cart is over the maximum.

## Secrets

| Secret | Where it lives | Who can read it |
| --- | --- | --- |
| PayPal client secret and webhook id | API and worker environment | Those processes. Never a graph node, a skill argument, a log line, or a studio response |
| Model API key | API environment in v0.3 | The model adapter. The studio can store a key by sending it to the API, which writes the environment-equivalent secret store for the process. The GET config route returns whether a key is set, not the key |
| Better Auth secret | Web and API environment | Session verification |
| API key secret | Hash in `identity.api_keys` | Shown once at creation |
| Approval signing key | API environment, from v0.7 | Approval service. The database row remains the authority |

The studio's config response may include the PayPal client id when the mode is sandbox, because the browser button needs it. The secret stays on the server. This matches the prototype.

Logs redact `Authorization`, `api_key`, `client_secret`, and request bodies of provider calls. Token usage is safe to log as counts.

## Organization boundary

Every repository method takes `organization_id` from `ExecutionContext`. Path parameters that include an organization id must equal the membership. A mismatch is 404. Row level security is the second line, behind the repository filter, and it is tested.

Agent runs, proposals, and transactions created in organization A are unreadable with organization B's session, including by primary key guessing.

## Engineering rules

| Rule | Enforcement |
| --- | --- |
| The model never authorizes a payment | Commerce methods are not skills. The compiler schema rejects `status`. Capture checks the approval row |
| The agent never receives a provider secret | Secrets are read inside the adapter from the environment. They are not fields on `GraphContext` |
| Published versions are immutable | Database trigger plus repository tests that attempt an update |
| The policy engine is deterministic | Pure evaluator. Tests call it twice |
| An approval is bound to a cart hash | Snapshot columns and `intent_mismatch` |
| The gateway revalidates every financial operation | `prepare` and `capture` recompute the hash from catalog prices |
| Payment operations are idempotent | Unique `(organization_id, idempotency_key)` and the provider request id |
| Events commit with the state change | Outbox insert in the same transaction |
| Organization boundaries hold on the server | Repository filter, RLS, 404 on mismatch |
| Each provider has its own adapter | `PaymentProvider` protocol. PayPal is one implementation |
| Agent run state and transaction state are separate | `cancel_run` does not void. Transaction methods do not read graph checkpoints |
| Redis is not on the correctness path | Locks and the outbox are PostgreSQL |

## Attack cases the suite keeps

| Case | Required result |
| --- | --- |
| Amount changes after approval | `intent_mismatch`. The provider is voided on capture, or never called if the change is seen at prepare |
| Hidden warranty or accessory | `addon` or `over_budget` |
| Wrong brand or too little RAM | `brand` or `spec_ram` |
| Two reservations that each fit and together do not | One `budget_exhausted`. One reservation held |
| Compiler JSON includes `status: active` | `compiler_overreach`. The version stays a draft |
| Vague copy such as "around $800" or "a good laptop" | Ambiguities stored. Activation fails |
| Suggested price from the model | Ignored. The catalog price is hashed |
| Same idempotency key, twice | One provider object |
| Lost provider response | Status `unknown`. No second create |
| Tool call to a skill not on the version | `skill_not_attached` |
| Caller from another organization with a known id | 404 and zero rows |
| Frontend-only permission change | The API still returns `forbidden` |

## Residual risks, stated as such

- A person with the PayPal dashboard can move money outside Mandate. Mitigation is operational: sandbox keys in this product, restricted live keys only after an explicit decision, no second key in an agent.
- The engine believes the catalog adapter. A poisoned description is untrusted text. A poisoned price in a catalog you do not control is a catalog trust decision. The first catalog is one the organization owns.
- Voice is an input channel. It is not an authenticator.
- Provider fraud systems may still decline a cart Mandate allowed.
- An append-only table with restricted grants detects ordinary tampering by the application role. It does not detect a database superuser. v0.10's hash chain raises that bar and still will not be described as an absolute proof against an operator who holds the signing key.
