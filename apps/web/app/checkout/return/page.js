"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { apiGet, apiPost, idemKey } from "../../../lib/api";

import Avatar from "@mui/material/Avatar";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import CircularProgress from "@mui/material/CircularProgress";
import Typography from "@mui/material/Typography";
import { Banner, money } from "../../../components/ui";

const MONO = { fontFamily: "ui-monospace, monospace" };

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
      await apiPost(`/v1/payments/${tx}/authorize`, { order_id: orderId }, { idempotencyKey: idemKey() });
      const captured = await apiPost(`/v1/payments/${tx}/capture`, {}, { idempotencyKey: idemKey() });
      setPayment(captured.payment);
      setStatus(captured.payment.status);
    })().catch((caught) => { setError(caught.message); setStatus("error"); });
  }, []);

  return (
    <Box sx={{ minHeight: "60vh", display: "grid", placeItems: "center" }}>
      <Card sx={{ maxWidth: 470, textAlign: "center" }}>
        <CardContent sx={{ p: 4 }}>
          {status === "working" ? (
            <>
              <CircularProgress size={32} sx={{ mb: 2 }} />
              <Typography variant="h3">Completing the payment…</Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>Authorizing and capturing the approved cart with PayPal.</Typography>
            </>
          ) : null}

          {status === "captured" ? (
            <>
              <Avatar sx={{ width: 56, height: 56, mx: "auto", mb: 2, bgcolor: "success.light", color: "success.dark", fontSize: "1.6rem", fontWeight: 700 }}>✓</Avatar>
              <Typography variant="h3">Payment captured</Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                {money(payment.amount_minor, payment.currency)} captured · PayPal capture <Box component="span" sx={MONO}>{payment.provider_capture_id}</Box>.
              </Typography>
            </>
          ) : null}

          {status === "voided" ? (
            <>
              <Avatar sx={{ width: 56, height: 56, mx: "auto", mb: 2, bgcolor: "warning.light", color: "warning.dark", fontSize: "1.6rem", fontWeight: 700 }}>!</Avatar>
              <Typography variant="h3">Voided — the cart changed</Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>The cart no longer matches what was approved ({payment.reason_code}). No money was captured.</Typography>
            </>
          ) : null}

          {status === "error" ? (
            <>
              <Avatar sx={{ width: 56, height: 56, mx: "auto", mb: 2, bgcolor: "warning.light", color: "warning.dark", fontSize: "1.6rem", fontWeight: 700 }}>!</Avatar>
              <Typography variant="h3" sx={{ mb: 2 }}>Could not complete</Typography>
              <Banner>{error}</Banner>
            </>
          ) : null}

          <Button component={Link} href="/" variant="contained" sx={{ mt: 2.5 }}>Back to checkout</Button>
        </CardContent>
      </Card>
    </Box>
  );
}
