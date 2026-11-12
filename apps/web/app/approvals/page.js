"use client";

import { useCallback, useEffect, useState } from "react";
import { apiGet, apiPost, idemKey } from "../../lib/api";

import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import CardHeader from "@mui/material/CardHeader";
import Chip from "@mui/material/Chip";
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
  useEffect(() => { load(); }, [load]);

  async function evaluate(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setDecision(null);
    try {
      const body = await apiPost("/v1/proposals", { policy_id: policyId, sku });
      setDecision(body);
    } catch (caught) { setError(caught.message); }
    finally { setBusy(false); }
  }

  async function openApproval(proposalId) {
    setError("");
    try {
      await apiPost("/v1/approvals", { proposal_id: proposalId }, { idempotencyKey: idemKey() });
      setDecision(null);
      load();
    } catch (caught) { setError(caught.message); }
  }

  async function act(approvalId, action) {
    setError("");
    try {
      await apiPost(`/v1/approvals/${approvalId}/${action}`, action === "reject" ? { reason: "Rejected in studio" } : {}, { idempotencyKey: idemKey() });
      load();
    } catch (caught) { setError(caught.message); }
  }

  return (
    <>
      <PageHeader overline="Approvals" title="One cart. One signature." />
      <Banner>{error}</Banner>

      <Card sx={{ mb: 3 }}>
        <CardHeader title="Evaluate a purchase" />
        <CardContent>
          <Stack component="form" onSubmit={evaluate} direction={{ xs: "column", md: "row" }} spacing={1.5} alignItems={{ md: "flex-end" }}>
            <TextField select label="Active policy" value={policyId} onChange={(e) => setPolicyId(e.target.value)} required size="small" sx={{ flex: 1, minWidth: 180 }}>
              <MenuItem value="">Choose a policy…</MenuItem>
              {policies.map((row) => (
                <MenuItem key={row.policy_id || row.id} value={row.policy_id || row.id}>
                  {shortId(row.policy_id || row.id)} · {money(row.maximum_total_minor, row.currency)}
                </MenuItem>
              ))}
            </TextField>
            <TextField select label="Catalog SKU" value={sku} onChange={(e) => setSku(e.target.value)} required size="small" sx={{ flex: 1, minWidth: 180 }}>
              <MenuItem value="">Choose a SKU…</MenuItem>
              {catalog.map((item) => (
                <MenuItem key={item.sku} value={item.sku}>{item.sku} · {money(item.unit_amount_minor, "USD")}</MenuItem>
              ))}
            </TextField>
            <Button type="submit" variant="contained" disabled={busy || !policyId || !sku}>{busy ? "Evaluating…" : "Evaluate"}</Button>
          </Stack>

          {decision ? (
            <Stack direction="row" flexWrap="wrap" alignItems="center" gap={1} sx={{ mt: 2, pt: 2, borderTop: "1px solid", borderColor: "divider" }}>
              <StatusChip status={decision.decision.decision} />
              <Typography variant="body2" color="text.secondary">{money(decision.decision.evaluated_amount_minor, decision.decision.currency)}</Typography>
              {(decision.decision.reason_codes || []).map((code) => <Chip key={code} size="small" label={code} variant="outlined" />)}
              {decision.decision.decision === "needs_approval" ? (
                <Button size="small" variant="outlined" onClick={() => openApproval(decision.proposal_id)}>Open approval</Button>
              ) : null}
            </Stack>
          ) : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader title="Approvals" action={<Button size="small" onClick={load}>Refresh</Button>} />
        <CardContent>
          {rows.length === 0 ? (
            <Typography variant="body2" color="text.secondary">No approvals yet.</Typography>
          ) : (
            <TableContainer>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Approval</TableCell>
                    <TableCell>Status</TableCell>
                    <TableCell>Amount</TableCell>
                    <TableCell>Cart hash</TableCell>
                    <TableCell align="right" />
                  </TableRow>
                </TableHead>
                <TableBody>
                  {rows.map((row) => (
                    <TableRow key={row.id} hover>
                      <TableCell sx={MONO}>{shortId(row.id)}</TableCell>
                      <TableCell><StatusChip status={row.status} /></TableCell>
                      <TableCell>{money(row.amount_minor, row.currency)}</TableCell>
                      <TableCell sx={{ ...MONO, maxWidth: 220, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{row.cart_hash}</TableCell>
                      <TableCell align="right">
                        <Stack direction="row" spacing={1} justifyContent="flex-end">
                          {row.status === "pending" ? (
                            <>
                              <Button size="small" variant="contained" onClick={() => act(row.id, "approve")}>Approve</Button>
                              <Button size="small" variant="outlined" color="inherit" onClick={() => act(row.id, "reject")}>Reject</Button>
                            </>
                          ) : null}
                          {row.status === "valid" ? (
                            <Button size="small" variant="outlined" color="error" onClick={() => act(row.id, "reject")}>Revoke</Button>
                          ) : null}
                        </Stack>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </CardContent>
      </Card>
    </>
  );
}
