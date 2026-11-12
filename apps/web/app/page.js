"use client";

import { useCallback, useEffect, useState } from "react";
import { apiGet, apiPost, idemKey } from "../lib/api";

const DEMO_POLICY =
  "Order a Dell laptop for the team. The total must not exceed $800, including tax and delivery. " +
  "At least 16 GB of RAM and a 512 GB SSD. No warranty and no accessories. Do not pay until I approve.";

export default function Checkout() {
  const [policy, setPolicy] = useState(null);
  const [goal, setGoal] = useState("Buy a reliable work laptop for the team, within budget.");
  const [chosen, setChosen] = useState(null);
  const [decision, setDecision] = useState(null);
  const [proposalId, setProposalId] = useState(null);
  const [approval, setApproval] = useState(null);
  const [payment, setPayment] = useState(null);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");

  const loadPolicy = useCallback(() => {
    apiGet("/v1/policies")
      .then((data) => {
        const active = (data.policies || []).find((row) => row.status === "active");
        setPolicy(active || null);
      })
      .catch((caught) => setError(caught.message));
  }, []);

  useEffect(() => {
    loadPolicy();
  }, [loadPolicy]);

  async function wrap(key, fn) {
    setBusy(key);
    setError("");
    try {
      return await fn();
    } catch (caught) {
      setError(caught.message);
      throw caught;
    } finally {
      setBusy("");
    }
  }

  async function createPolicy() {
    await wrap("policy", async () => {
      const created = await apiPost("/v1/policies", { instruction: DEMO_POLICY });
      await apiPost(`/v1/policies/${created.policy.id}/activate`, {}, { idempotencyKey: idemKey() });
      loadPolicy();
    });
  }

  async function runAgent() {
    setChosen(null);
    setDecision(null);
    setApproval(null);
    setPayment(null);
    await wrap("agent", async () => {
      const body = await apiPost("/v1/agent/shop", { policy_id: policy.policy_id, goal });
      setChosen(body.chosen);
      setDecision(body.decision);
      setProposalId(body.proposal_id);
    });
  }

  async function approve() {
    await wrap("approve", async () => {
      const opened = await apiPost("/v1/approvals", { proposal_id: proposalId }, { idempotencyKey: idemKey() });
      const granted = await apiPost(`/v1/approvals/${opened.approval.id}/approve`, {}, { idempotencyKey: idemKey() });
      setApproval(granted.approval);
    });
  }

  async function pay() {
    await wrap("pay", async () => {
      const body = await apiPost("/v1/payments", { proposal_id: proposalId, approval_id: approval.id }, { idempotencyKey: idemKey() });
      setPayment(body.payment);
      if (body.payment?.provider_approval_url) {
        window.location.href = body.payment.provider_approval_url;
      } else {
        setError("No PayPal approval link was returned. Check PAYPAL_CLIENT_ID / PAYPAL_CLIENT_SECRET.");
      }
    });
  }

  return (
    <>
      <header className="hero">
        <p className="eyebrow">Agentic checkout</p>
        <h1>An agent shops. You approve. PayPal pays — only the approved cart.</h1>
        <p className="lede">
          The model proposes a product within your budget policy. A deterministic engine decides and a human approves. PayPal is
          called last, for the exact cart that was approved — never by the model.
        </p>
      </header>

      {error ? <p className="banner">{error}</p> : null}

      <Step n={1} title="Budget policy" done={Boolean(policy)}>
        {policy ? (
          <p className="meta">
            Active policy · max <strong>{money(policy.maximum_total_minor, policy.currency)}</strong> · {policy.original_instruction}
          </p>
        ) : (
          <>
            <p className="meta">No active budget policy yet. Create the demo one to continue.</p>
            <button className="btn btn-primary" onClick={createPolicy} disabled={busy === "policy"}>
              {busy === "policy" ? "Creating…" : "Create demo budget policy"}
            </button>
          </>
        )}
      </Step>

      <Step n={2} title="Let the agent shop" done={Boolean(chosen)} locked={!policy}>
        <label className="field">
          <span>Goal for the agent</span>
          <textarea rows={2} value={goal} onChange={(event) => setGoal(event.target.value)} />
        </label>
        <button className="btn btn-primary" onClick={runAgent} disabled={!policy || busy === "agent"}>
          {busy === "agent" ? "The agent is deciding…" : "Run agent"}
        </button>
        {chosen ? (
          <div className="choice">
            <div className="choice-head">
              <span className="badge badge-active">chose {chosen.sku}</span>
              <span className="meta">{chosen.model}</span>
            </div>
            <p className="reasoning">“{chosen.reasoning}”</p>
            {decision ? (
              <div className="decision">
                <span className={`badge badge-${decision.decision}`}>{decision.decision.replace("_", " ")}</span>
                <span className="meta">{money(decision.evaluated_amount_minor, decision.currency)}</span>
                {(decision.reason_codes || []).map((code) => (
                  <span key={code} className="chip">
                    {code}
                  </span>
                ))}
              </div>
            ) : null}
          </div>
        ) : null}
      </Step>

      <Step n={3} title="Approve the cart" done={approval?.status === "valid"} locked={decision?.decision !== "needs_approval"}>
        {decision?.decision === "needs_approval" ? (
          approval?.status === "valid" ? (
            <p className="meta">
              Approved · bound to cart <span className="mono">{short(approval.cart_hash)}</span>. A changed line would void this.
            </p>
          ) : (
            <button className="btn btn-primary" onClick={approve} disabled={busy === "approve"}>
              {busy === "approve" ? "Signing…" : "Approve this cart"}
            </button>
          )
        ) : (
          <p className="meta">The agent’s proposal needs a human approval before any payment.</p>
        )}
      </Step>

      <Step n={4} title="Pay with PayPal" done={false} locked={approval?.status !== "valid"}>
        <p className="meta">Creates a PayPal order for the approved amount and sends you to PayPal to approve it (sandbox).</p>
        <button className="btn btn-primary" onClick={pay} disabled={approval?.status !== "valid" || busy === "pay"}>
          {busy === "pay" ? "Creating order…" : "Pay with PayPal"}
        </button>
      </Step>
    </>
  );
}

function Step({ n, title, children, done, locked }) {
  return (
    <section className={`step${locked ? " step-locked" : ""}`}>
      <div className={`step-num${done ? " step-done" : ""}`}>{done ? "✓" : n}</div>
      <div className="step-body">
        <h2>{title}</h2>
        {children}
      </div>
    </section>
  );
}

function money(minor, currency) {
  if (minor == null) return "—";
  return `$${(minor / 100).toFixed(2)} ${currency || "USD"}`;
}

function short(value) {
  return value ? `${value.slice(0, 12)}…` : "—";
}
