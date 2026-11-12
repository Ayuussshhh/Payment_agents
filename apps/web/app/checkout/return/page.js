"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { apiGet, apiPost, idemKey } from "../../../lib/api";

export default function CheckoutReturn() {
  const [status, setStatus] = useState("working");
  const [payment, setPayment] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const tx = params.get("tx");
    if (!tx) {
      setError("No payment reference in the return URL.");
      setStatus("error");
      return;
    }
    (async () => {
      const current = await apiGet(`/v1/payments/${tx}`);
      const orderId = current.payment.provider_order_id;
      // The buyer approved on PayPal; authorize the hold, then capture the approved cart.
      await apiPost(`/v1/payments/${tx}/authorize`, { order_id: orderId }, { idempotencyKey: idemKey() });
      const captured = await apiPost(`/v1/payments/${tx}/capture`, {}, { idempotencyKey: idemKey() });
      setPayment(captured.payment);
      setStatus(captured.payment.status);
    })().catch((caught) => {
      setError(caught.message);
      setStatus("error");
    });
  }, []);

  return (
    <div className="return-wrap">
      <section className="panel return-card">
        {status === "working" ? (
          <>
            <h2>Completing the payment…</h2>
            <p className="meta">Authorizing and capturing the approved cart with PayPal.</p>
          </>
        ) : null}

        {status === "captured" ? (
          <>
            <div className="big-badge ok">✓</div>
            <h2>Payment captured</h2>
            <p className="meta">
              {money(payment.amount_minor, payment.currency)} captured · PayPal capture{" "}
              <span className="mono">{payment.provider_capture_id}</span>.
            </p>
          </>
        ) : null}

        {status === "voided" ? (
          <>
            <div className="big-badge warn">!</div>
            <h2>Voided — the cart changed</h2>
            <p className="meta">The cart no longer matches what was approved ({payment.reason_code}). No money was captured.</p>
          </>
        ) : null}

        {status === "error" ? (
          <>
            <div className="big-badge warn">!</div>
            <h2>Could not complete</h2>
            <p className="banner">{error}</p>
          </>
        ) : null}

        <Link className="btn btn-primary" href="/">
          Back to checkout
        </Link>
      </section>
    </div>
  );
}

function money(minor, currency) {
  if (minor == null) return "—";
  return `$${(minor / 100).toFixed(2)} ${currency || "USD"}`;
}
