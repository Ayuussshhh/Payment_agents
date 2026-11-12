"use client";

import { useCallback, useEffect, useState } from "react";
import { apiGet, apiPost, idemKey } from "../../lib/api";

export default function Payments() {
  const [valid, setValid] = useState([]);
  const [selected, setSelected] = useState("");
  const [payment, setPayment] = useState(null);
  const [attempts, setAttempts] = useState([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const loadApprovals = useCallback(() => {
    apiGet("/v1/approvals")
      .then((data) => setValid((data.approvals || []).filter((row) => row.status === "valid")))
      .catch((caught) => setError(caught.message));
  }, []);

  useEffect(() => {
    loadApprovals();
  }, [loadApprovals]);

  function show(body) {
    setPayment(body.payment);
    setAttempts(body.attempts || []);
  }

  async function refresh(id) {
    try {
      const body = await apiGet(`/v1/payments/${id}`);
      show(body);
    } catch (caught) {
      setError(caught.message);
    }
  }

  async function run(label, action) {
    setBusy(true);
    setError("");
    try {
      const body = await action();
      show({ payment: body.payment, attempts: attempts });
      if (body.payment) {
        await refresh(body.payment.id);
      }
    } catch (caught) {
      setError(`${label}: ${caught.message}`);
    } finally {
      setBusy(false);
    }
  }

  function create() {
    const approval = valid.find((row) => row.id === selected);
    if (!approval) {
      setError("Choose a valid approval first.");
      return;
    }
    run("Create", () =>
      apiPost("/v1/payments", { proposal_id: approval.proposal_id, approval_id: approval.id }, { idempotencyKey: idemKey() }),
    );
  }

  const id = payment?.id;
  const status = payment?.status;

  return (
    <>
      <header className="top">
        <div>
          <p className="eyebrow">Payments</p>
          <h1>The provider is called last, for the approved cart.</h1>
        </div>
      </header>

      {error ? <p className="banner">{error}</p> : null}

      <section className="panel">
        <div className="panel-head">
          <h2>Create from a valid approval</h2>
          <button className="link-button" onClick={loadApprovals}>
            Refresh
          </button>
        </div>
        <div className="inline-form">
          <label className="field">
            <span>Valid approval</span>
            <select value={selected} onChange={(event) => setSelected(event.target.value)}>
              <option value="">Choose an approval…</option>
              {valid.map((row) => (
                <option key={row.id} value={row.id}>
                  {shorten(row.id)} · {money(row.amount_minor, row.currency)}
                </option>
              ))}
            </select>
          </label>
          <button className="btn btn-primary" onClick={create} disabled={busy || !selected}>
            Create payment
          </button>
        </div>
        <p className="meta">Needs a payment provider. Set PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET in .env.</p>
      </section>

      {payment ? (
        <section className="panel">
          <div className="panel-head">
            <h2>Payment {shorten(id)}</h2>
            <span className={`badge badge-${status}`}>{status}</span>
          </div>
          <dl className="detail">
            <div>
              <dt>Amount</dt>
              <dd>{money(payment.amount_minor, payment.currency)}</dd>
            </div>
            <div>
              <dt>Reason</dt>
              <dd>{payment.reason_code || "—"}</dd>
            </div>
            <div>
              <dt>Order</dt>
              <dd className="mono">{payment.provider_order_id || "—"}</dd>
            </div>
            <div>
              <dt>Authorization</dt>
              <dd className="mono">{payment.provider_authorization_id || "—"}</dd>
            </div>
          </dl>

          <div className="actions">
            <button
              className="btn"
              disabled={busy || status !== "reserved"}
              onClick={() => run("Authorize", () => apiPost(`/v1/payments/${id}/authorize`, { order_id: payment.provider_order_id }))}
            >
              Authorize
            </button>
            <button className="btn btn-primary" disabled={busy || status !== "authorized"} onClick={() => run("Capture", () => apiPost(`/v1/payments/${id}/capture`, {}))}>
              Capture
            </button>
            <button
              className="btn"
              disabled={busy || !["reserved", "authorized"].includes(status)}
              onClick={() => run("Void", () => apiPost(`/v1/payments/${id}/void`, {}))}
            >
              Void
            </button>
            <button className="btn" disabled={busy || status !== "captured"} onClick={() => run("Refund", () => apiPost(`/v1/payments/${id}/refund`, {}))}>
              Refund
            </button>
          </div>

          {attempts.length ? (
            <table className="table">
              <thead>
                <tr>
                  <th>Operation</th>
                  <th>Provider status</th>
                </tr>
              </thead>
              <tbody>
                {attempts.map((attempt, index) => (
                  <tr key={index}>
                    <td>{attempt.operation}</td>
                    <td>{attempt.provider_status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : null}
        </section>
      ) : null}
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
