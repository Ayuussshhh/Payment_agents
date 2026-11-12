"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { apiGet, apiPost, idemKey } from "../lib/api";

import Avatar from "@mui/material/Avatar";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import Chip from "@mui/material/Chip";
import Stack from "@mui/material/Stack";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import CheckIcon from "@mui/icons-material/Check";
import { Banner, StatusChip, money as fmtMoney } from "../components/ui";

const DEMO_POLICY =
  "Order a Dell laptop for the team. The total must not exceed $800, including tax and delivery. " +
  "At least 16 GB of RAM and a 512 GB SSD. No warranty and no accessories. Do not pay until I approve.";

function money(minor, currency) {
  if (minor == null) return "—";
  return `$${(minor / 100).toFixed(2)} ${currency || "USD"}`;
}
function short(value) { return value ? `${value.slice(0, 12)}…` : "—"; }

function Step({ n, title, done, locked, children }) {
  return (
    <Card sx={{ opacity: locked ? 0.5 : 1, pointerEvents: locked ? "none" : "auto", transition: "opacity .2s" }}>
      <CardContent>
        <Stack direction="row" spacing={2}>
          <Avatar sx={{ width: 36, height: 36, fontWeight: 700, bgcolor: done ? "success.main" : "grey.200", color: done ? "#fff" : "text.secondary" }}>
            {done ? <CheckIcon fontSize="small" /> : n}
          </Avatar>
          <Box sx={{ flex: 1, minWidth: 0 }}>
            <Typography variant="h5" sx={{ mb: 1 }}>{title}</Typography>
            {children}
          </Box>
        </Stack>
      </CardContent>
    </Card>
  );
}

export default function Checkout() {
  const [policy, setPolicy] = useState(null);
  const [catalogCount, setCatalogCount] = useState(null);
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
      .then((data) => setPolicy((data.policies || []).find((row) => row.status === "active") || null))
      .catch((caught) => setError(caught.message));
  }, []);

  useEffect(() => {
    loadPolicy();
    apiGet("/v1/catalog").then((data) => setCatalogCount((data.catalog || []).length)).catch(() => setCatalogCount(null));
  }, [loadPolicy]);

  async function wrap(key, fn) {
    setBusy(key); setError("");
    try { return await fn(); }
    catch (caught) { setError(caught.message); throw caught; }
    finally { setBusy(""); }
  }

  async function createPolicy() {
    await wrap("policy", async () => {
      const created = await apiPost("/v1/policies", { instruction: DEMO_POLICY });
      await apiPost(`/v1/policies/${created.policy.id}/activate`, {}, { idempotencyKey: idemKey() });
      loadPolicy();
    });
  }

  async function runAgent() {
    setChosen(null); setDecision(null); setApproval(null); setPayment(null);
    await wrap("agent", async () => {
      const body = await apiPost("/v1/agent/shop", { policy_id: policy.policy_id, goal });
      setChosen(body.chosen); setDecision(body.decision); setProposalId(body.proposal_id);
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
      if (body.payment?.provider_approval_url) window.location.href = body.payment.provider_approval_url;
      else setError("No PayPal approval link was returned. Check PAYPAL_CLIENT_ID / PAYPAL_CLIENT_SECRET.");
    });
  }

  return (
    <Box sx={{ maxWidth: 860 }}>
      <Box sx={{ mb: 4 }}>
        <Typography variant="overline" color="primary">Agentic checkout</Typography>
        <Typography variant="h1" sx={{ mt: 0.5, fontSize: { xs: "1.9rem", md: "2.4rem" }, maxWidth: "20ch" }}>
          An agent shops. You approve. PayPal pays — only the approved cart.
        </Typography>
        <Typography variant="body1" color="text.secondary" sx={{ mt: 2, maxWidth: "64ch" }}>
          The model proposes a product within your budget policy. A deterministic engine decides and a human approves. PayPal is
          called last, for the exact cart that was approved — never by the model.
        </Typography>
      </Box>

      <Banner>{error}</Banner>

      <Stack spacing={2}>
        <Step n={1} title="Budget policy" done={Boolean(policy)}>
          {policy ? (
            <Typography variant="body2" color="text.secondary">
              Active policy · max <b>{money(policy.maximum_total_minor, policy.currency)}</b> · {policy.original_instruction}
            </Typography>
          ) : (
            <>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>No active budget policy yet. Create the demo one to continue.</Typography>
              <Button variant="contained" onClick={createPolicy} disabled={busy === "policy"}>{busy === "policy" ? "Creating…" : "Create demo budget policy"}</Button>
            </>
          )}
        </Step>

        <Step n={2} title="Let the agent shop" done={Boolean(chosen)} locked={!policy}>
          <TextField label="Goal for the agent" value={goal} onChange={(e) => setGoal(e.target.value)} multiline rows={2} fullWidth size="small" sx={{ mb: 1.5 }} />
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
            The agent reads {catalogCount != null ? <b>{catalogCount} products</b> : "the"} merchant catalog and the budget policy, then proposes one SKU. It never sets a price.{" "}
            <Box component={Link} href="/catalog" sx={{ color: "primary.main", fontWeight: 600 }}>See the catalog →</Box>
          </Typography>
          <Button variant="contained" onClick={runAgent} disabled={!policy || busy === "agent"}>{busy === "agent" ? "The agent is deciding…" : "Run agent"}</Button>
          {chosen ? (
            <Box sx={{ mt: 2, p: 2, borderRadius: 2, border: "1px solid", borderColor: "primary.light", bgcolor: "rgba(20,83,116,0.04)" }}>
              <Stack direction="row" justifyContent="space-between" alignItems="center" spacing={1}>
                <Chip size="small" color="success" label={`chose ${chosen.sku}`} />
                <Typography variant="body2" color="text.secondary">{chosen.model}</Typography>
              </Stack>
              <Typography sx={{ mt: 1.5, fontStyle: "italic", lineHeight: 1.6 }}>“{chosen.reasoning}”</Typography>
              {decision ? (
                <Stack direction="row" flexWrap="wrap" alignItems="center" gap={1} sx={{ mt: 1.5, pt: 1.5, borderTop: "1px solid", borderColor: "divider" }}>
                  <StatusChip status={decision.decision} />
                  <Typography variant="body2" color="text.secondary">{money(decision.evaluated_amount_minor, decision.currency)}</Typography>
                  {(decision.reason_codes || []).map((code) => <Chip key={code} size="small" variant="outlined" label={code} />)}
                </Stack>
              ) : null}
            </Box>
          ) : null}
        </Step>

        <Step n={3} title="Approve the cart" done={approval?.status === "valid"} locked={decision?.decision !== "needs_approval"}>
          {decision?.decision === "needs_approval" ? (
            approval?.status === "valid" ? (
              <Typography variant="body2" color="text.secondary">
                Approved · bound to cart <Box component="span" sx={{ fontFamily: "ui-monospace, monospace" }}>{short(approval.cart_hash)}</Box>. A changed line would void this.
              </Typography>
            ) : (
              <Button variant="contained" onClick={approve} disabled={busy === "approve"}>{busy === "approve" ? "Signing…" : "Approve this cart"}</Button>
            )
          ) : (
            <Typography variant="body2" color="text.secondary">The agent’s proposal needs a human approval before any payment.</Typography>
          )}
        </Step>

        <Step n={4} title="Pay with PayPal" done={false} locked={approval?.status !== "valid"}>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>Creates a PayPal order for the approved amount and sends you to PayPal to approve it (sandbox).</Typography>
          <Button
            variant="contained"
            onClick={pay}
            disabled={approval?.status !== "valid" || busy === "pay"}
            sx={{ background: "linear-gradient(135deg, #003087, #0070e0)" }}
          >
            {busy === "pay" ? "Creating order…" : "Pay with PayPal"}
          </Button>
        </Step>
      </Stack>
    </Box>
  );
}
