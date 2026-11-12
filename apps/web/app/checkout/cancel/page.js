"use client";

import Link from "next/link";

export default function CheckoutCancel() {
  return (
    <div className="return-wrap">
      <section className="panel return-card">
        <div className="big-badge warn">×</div>
        <h2>Payment cancelled</h2>
        <p className="meta">You left the PayPal checkout. Nothing was charged. The approval is still valid if you want to try again.</p>
        <Link className="btn btn-primary" href="/">
          Back to checkout
        </Link>
      </section>
    </div>
  );
}
