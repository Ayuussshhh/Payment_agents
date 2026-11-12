"use client";

import { useCallback, useEffect, useState } from "react";
import { apiGet, apiPost, idemKey } from "../../lib/api";

import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import CardHeader from "@mui/material/CardHeader";
import MenuItem from "@mui/material/MenuItem";
import Stack from "@mui/material/Stack";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableContainer from "@mui/material/TableContainer";
import TableHead from "@mui/material/TableHead";
import TableRow from "@mui/material/TableRow";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import { Banner, PageHeader, StatusChip, money, shortId } from "../../components/ui";

const MONO = { fontFamily: "ui-monospace, monospace" };

function Detail({ label, value, mono }) {
  return (
    <Box>
      <Typography variant="caption" color="text.secondary">{label}</Typography>
      <Typography sx={{ mt: 0.25, ...(mono ? MONO : {}) }}>{value}</Typography>
    </Box>
  );
}

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
  useEffect(() => { loadApprovals(); }, [loadApprovals]);

  function show(body) { setPayment(body.payment); setAttempts(body.attempts || []); }

  async function refresh(id) {
    try { const body = await apiGet(`/v1/payments/${id}`); show(body); }
    catch (caught) { setError(caught.message); }
  }

  async function run(label, action) {
    setBusy(true);
    setError("");
    try {
      const body = await action();
      show({ payment: body.payment, attempts });
      if (body.payment) await refresh(body.payment.id);
    } catch (caught) { setError(`${label}: ${caught.message}`); }
    finally { setBusy(false); }
  }

  function create() {
    const approval = valid.find((row) => row.id === selected);
    if (!approval) { setError("Choose a valid approval first."); return; }
    run("Create", () => apiPost("/v1/payments", { proposal_id: approval.proposal_id, approval_id: approval.id }, { idempotencyKey: idemKey() }));
  }

  const id = payment?.id;
  const status = payment?.status;

  return (
    <>
      <PageHeader overline="Payments" title="The provider is called last, for the approved cart." />
      <Banner>{error}</Banner>

      <Card sx={{ mb: 3 }}>
        <CardHeader title="Create from a valid approval" action={<Button size="small" onClick={loadApprovals}>Refresh</Button>} />
        <CardContent>
          <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5} alignItems={{ sm: "flex-end" }}>
            <TextField select label="Valid approval" value={selected} onChange={(e) => setSelected(e.target.value)} size="small" sx={{ flex: 1, minWidth: 200 }}>
              <MenuItem value="">Choose an approval…</MenuItem>
              {valid.map((row) => <MenuItem key={row.id} value={row.id}>{shortId(row.id)} · {money(row.amount_minor, row.currency)}</MenuItem>)}
            </TextField>
            <Button variant="contained" onClick={create} disabled={busy || !selected}>Create payment</Button>
          </Stack>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 1.5 }}>
            Needs a payment provider. Set PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET in .env.
          </Typography>
        </CardContent>
      </Card>

      {payment ? (
        <Card>
          <CardHeader title={`Payment ${shortId(id)}`} action={<StatusChip status={status} sx={{ mt: 1 }} />} />
          <CardContent>
            <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr 1fr", md: "repeat(4, 1fr)" }, gap: 2 }}>
              <Detail label="Amount" value={money(payment.amount_minor, payment.currency)} />
              <Detail label="Reason" value={payment.reason_code || "—"} />
              <Detail label="Order" value={payment.provider_order_id || "—"} mono />
              <Detail label="Authorization" value={payment.provider_authorization_id || "—"} mono />
            </Box>

            <Stack direction="row" flexWrap="wrap" gap={1} sx={{ mt: 2.5 }}>
              <Button variant="outlined" disabled={busy || status !== "reserved"} onClick={() => run("Authorize", () => apiPost(`/v1/payments/${id}/authorize`, { order_id: payment.provider_order_id }))}>Authorize</Button>
              <Button variant="contained" disabled={busy || status !== "authorized"} onClick={() => run("Capture", () => apiPost(`/v1/payments/${id}/capture`, {}))}>Capture</Button>
              <Button variant="outlined" color="inherit" disabled={busy || !["reserved", "authorized"].includes(status)} onClick={() => run("Void", () => apiPost(`/v1/payments/${id}/void`, {}))}>Void</Button>
              <Button variant="outlined" color="inherit" disabled={busy || status !== "captured"} onClick={() => run("Refund", () => apiPost(`/v1/payments/${id}/refund`, {}))}>Refund</Button>
            </Stack>

            {attempts.length ? (
              <TableContainer sx={{ mt: 2.5 }}>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Operation</TableCell>
                      <TableCell>Provider status</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {attempts.map((attempt, index) => (
                      <TableRow key={index} hover>
                        <TableCell>{attempt.operation}</TableCell>
                        <TableCell>{attempt.provider_status}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            ) : null}
          </CardContent>
        </Card>
      ) : null}
    </>
  );
}
