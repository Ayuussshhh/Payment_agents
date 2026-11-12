"use client";

import { useCallback, useEffect, useState } from "react";
import { apiGet, apiPost, idemKey } from "../../lib/api";

export default function Approvals() {
  const [rows, setRows] = useState([]);
  const [policies, setPolicies] = useState([]);
  const [catalog, setCatalog] = useState([]);
  const [policyId, setPolicyId] = useState("");
  const [sku, setSku] = useState("");
  const [decision, setDecision] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    Promise.all([apiGet("/v1/approvals"), apiGet("/v1/policies"), apiGet("/v1/catalog")])
      .then(([approvals, policyList, catalogBody]) => {
        setRows(approvals.approvals || []);
        setPolicies((policyList.policies || []).filter((row) => row.status === "active"));
        setCatalog(catalogBody.catalog || []);
      })
      .catch((caught) => setError(caught.message));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function evaluate(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setDecision(null);
    try {
      const body = await apiPost("/v1/proposals", { policy_id: policyId, sku });
      setDecision(body);
    } catch (caught) {
      setError(caught.message);
    } finally {
      setBusy(false);
    }
  }

  async function openApproval(proposalId) {
    setError("");
    try {
      await apiPost("/v1/approvals", { proposal_id: proposalId }, { idempotencyKey: idemKey() });
      setDecision(null);
      load();
    } catch (caught) {
      setError(caught.message);
    }
  }

  async function act(approvalId, action) {
    setError("");
    try {
      await apiPost(`/v1/approvals/${approvalId}/${action}`, action === "reject" ? { reason: "Rejected in studio" } : {}, { idempotencyKey: idemKey() });
      load();
    } catch (caught) {
      setError(caught.message);
    }
  }

  return (
    <>
      <header className="top">
        <div>
          <p className="eyebrow">Approvals</p>
          <h1>One cart. One signature.</h1>
        </div>
      </header>

      {error ? <p className="banner">{error}</p> : null}

      <section className="panel">
        <div className="panel-head">
          <h2>Evaluate a purchase</h2>
        </div>
        <form onSubmit={evaluate} className="inline-form">
          <label className="field">
            <span>Active policy</span>
            <select value={policyId} onChange={(event) => setPolicyId(event.target.value)} required>
              <option value="">Choose a policy…</option>
              {policies.map((row) => (
                <option key={row.policy_id || row.id} value={row.policy_id || row.id}>
                  {shorten(row.policy_id || row.id)} · {money(row.maximum_total_minor, row.currency)}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Catalog SKU</span>
            <select value={sku} onChange={(event) => setSku(event.target.value)} required>
              <option value="">Choose a SKU…</option>
              {catalog.map((item) => (
                <option key={item.sku} value={item.sku}>
                  {item.sku} · {money(item.unit_amount_minor, "USD")}
                </option>
              ))}
            </select>
          </label>
          <button className="btn btn-primary" type="submit" disabled={busy || !policyId || !sku}>
            {busy ? "Evaluating…" : "Evaluate"}
          </button>
        </form>

        {decision ? (
          <div className="decision">
            <span className={`badge badge-${decision.decision.decision}`}>{decision.decision.decision}</span>
            <span className="meta">{money(decision.decision.evaluated_amount_minor, decision.decision.currency)}</span>
            {(decision.decision.reason_codes || []).map((code) => (
              <span key={code} className="chip">
                {code}
              </span>
            ))}
            {decision.decision.decision === "needs_approval" ? (
              <button className="btn" onClick={() => openApproval(decision.proposal_id)}>
                Open approval
              </button>
            ) : null}
          </div>
        ) : null}
      </section>

      <section className="panel">
        <div className="panel-head">
          <h2>Approvals</h2>
          <button className="link-button" onClick={load}>
            Refresh
          </button>
        </div>
        {rows.length === 0 ? (
          <p className="meta">No approvals yet.</p>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Approval</th>
                <th>Status</th>
                <th>Amount</th>
                <th>Cart hash</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id}>
                  <td className="mono">{shorten(row.id)}</td>
                  <td>
                    <span className={`badge badge-${row.status}`}>{row.status}</span>
                  </td>
                  <td>{money(row.amount_minor, row.currency)}</td>
                  <td className="mono truncate">{row.cart_hash}</td>
                  <td className="actions">
                    {row.status === "pending" ? (
                      <>
                        <button className="btn btn-primary" onClick={() => act(row.id, "approve")}>
                          Approve
                        </button>
                        <button className="btn" onClick={() => act(row.id, "reject")}>
                          Reject
                        </button>
                      </>
                    ) : null}
                    {row.status === "valid" ? (
                      <button className="btn" onClick={() => act(row.id, "reject")}>
                        Revoke
                      </button>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </>
  );
}

function money(minor, currency) {
  if (minor == null) return "—";
  return `${(minor / 100).toFixed(2)} ${currency || "USD"}`;
}

function shorten(id) {
  return id ? `${id.slice(0, 8)}…` : "—";
}
