"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { apiGet, apiPost } from "../../lib/api";

import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import CardHeader from "@mui/material/CardHeader";
import Divider from "@mui/material/Divider";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";
import { Banner, PageHeader, StatusChip, statusColor } from "../../components/ui";

const MONO = { fontFamily: "ui-monospace, monospace" };

function Trace({ trace }) {
  return (
    <Box sx={{ mt: 2, pt: 2, borderTop: "1px solid", borderColor: "divider" }}>
      <Typography variant="h6" sx={{ mb: 1 }}>Execution trace</Typography>
      {!trace?.length ? (
        <Typography variant="body2" color="text.secondary">No trace steps were recorded.</Typography>
      ) : (
        <Stack component="ol" spacing={1} sx={{ listStyle: "none", m: 0, p: 0 }}>
          {trace.map((item, index) => (
            <Box component="li" key={`${item.agent}-${index}`} sx={{ display: "flex", gap: 1, fontSize: "0.85rem" }}>
              <Typography component="span" variant="caption" color="primary" sx={{ minWidth: 72, textTransform: "uppercase", fontWeight: 600 }}>{item.agent}</Typography>
              {item.url ? (
                <Box component="a" href={item.url} target="_blank" rel="noreferrer" sx={{ color: "primary.main", textDecoration: "underline" }}>{item.text} ↗</Box>
              ) : (
                <Typography component="span" variant="body2" color="text.secondary">{item.text}</Typography>
              )}
            </Box>
          ))}
        </Stack>
      )}
    </Box>
  );
}

export default function Runs() {
  const [runs, setRuns] = useState([]);
  const [run, setRun] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try { const body = await apiGet("/v1/runs?limit=50"); setRuns(body.runs || []); setError(""); }
    catch (caught) { setError(caught.message); }
  }, []);
  useEffect(() => { load(); }, [load]);

  async function act(label, action) {
    setBusy(true); setError("");
    try { const body = await action(); setRun(body.run); await load(); }
    catch (caught) { setError(`${label}: ${caught.message}`); }
    finally { setBusy(false); }
  }

  async function inspect(id) {
    setBusy(true); setError("");
    try { const body = await apiGet(`/v1/runs/${id}`); setRun(body.run); }
    catch (caught) { setError(caught.message); }
    finally { setBusy(false); }
  }

  return (
    <>
      <PageHeader
        overline="Execution history"
        title="Runs"
        subtitle="Review agent activity, tool evidence, policy decisions, and outcomes."
        action={<Button component={Link} href="/agents" variant="contained">Build an agent</Button>}
      />
      <Banner>{error}</Banner>

      <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", md: "minmax(0,0.85fr) minmax(0,1.5fr)" }, gap: 2, alignItems: "start" }}>
        <Card>
          <CardHeader title="Recent runs" subheader="Latest 50 in this workspace" action={<Button size="small" onClick={load} disabled={busy}>Refresh</Button>} />
          <CardContent sx={{ p: 0 }}>
            {runs.length ? (
              <Box>
                {runs.map((item, i) => {
                  const selected = run?.id === item.id;
                  return (
                    <Box
                      key={item.id}
                      component="button"
                      onClick={() => inspect(item.id)}
                      sx={{
                        display: "flex", alignItems: "center", gap: 1.25, width: "100%", textAlign: "left",
                        px: 2.5, py: 1.5, border: 0, borderTop: i === 0 ? 0 : "1px solid", borderColor: "divider",
                        bgcolor: selected ? "action.selected" : "transparent", cursor: "pointer",
                        "&:hover": { bgcolor: selected ? "action.selected" : "action.hover" },
                      }}
                    >
                      <Box sx={{ width: 10, height: 10, borderRadius: "50%", flexShrink: 0, bgcolor: `${statusColor(item.status)}.main` }} />
                      <Box sx={{ minWidth: 0, flex: 1 }}>
                        <Typography variant="body2" sx={{ fontWeight: 600 }} noWrap>
                          {item.agent_name || "Agent"} <Typography component="span" variant="caption" color="text.secondary">v{item.agent_version}</Typography>
                        </Typography>
                        <Typography variant="caption" color="text.secondary" noWrap sx={{ display: "block" }}>{item.input?.goal || item.input?.query || "Agent execution"}</Typography>
                        <Typography variant="caption" color="text.disabled" noWrap sx={{ display: "block" }}>{new Date(item.created_at).toLocaleString()}</Typography>
                      </Box>
                      <StatusChip status={item.status} />
                    </Box>
                  );
                })}
              </Box>
            ) : (
              <Box sx={{ p: 4, textAlign: "center" }}>
                <Typography variant="h6">No runs yet</Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5, mb: 1.5 }}>Published agent executions will appear here with their traces and policy outcomes.</Typography>
                <Box component={Link} href="/agents" sx={{ color: "primary.main", fontWeight: 600 }}>Open the agent studio →</Box>
              </Box>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader
            title={run ? `Run ${run.id.slice(0, 8)}…` : "Select a run"}
            subheader="Inspection"
            action={run ? <StatusChip status={run.status} sx={{ mt: 1 }} /> : null}
          />
          <CardContent>
            {run ? (
              <>
                <Typography variant="body2" color="text.secondary">{run.stop_reason || "No stop reason"} · Proposals: {(run.output?.proposal_ids || []).length}</Typography>
                <Stack direction="row" spacing={1} sx={{ my: 2 }}>
                  {run.status === "paused" ? <Button size="small" variant="outlined" disabled={busy} onClick={() => act("Resume", () => apiPost(`/v1/runs/${run.id}/resume`, {}))}>Resume</Button> : null}
                  {!["succeeded", "completed", "failed", "cancelled", "limited"].includes(run.status) ? (
                    <Button size="small" variant="outlined" color="error" disabled={busy} onClick={() => act("Cancel", () => apiPost(`/v1/runs/${run.id}/cancel`, {}))}>Cancel run</Button>
                  ) : null}
                </Stack>

                {run.output?.final_text ? (
                  <Box sx={{ mt: 1 }}>
                    <Typography variant="h6" sx={{ mb: 0.5 }}>Agent response</Typography>
                    <Typography variant="body2" sx={{ whiteSpace: "pre-wrap", lineHeight: 1.6 }}>{run.output.final_text}</Typography>
                  </Box>
                ) : null}

                {run.output?.proposal_results?.length ? (
                  <Box sx={{ mt: 2, pt: 2, borderTop: "1px solid", borderColor: "divider" }}>
                    <Typography variant="h6" sx={{ mb: 1 }}>Policy evaluations</Typography>
                    {run.output.proposal_results.map((item, idx) => (
                      <Box key={item.proposal_id} sx={{ py: 1, borderTop: idx === 0 ? 0 : "1px solid", borderColor: "divider" }}>
                        <Typography variant="body2" sx={{ fontWeight: 600 }}>{item.sku} · {item.decision}</Typography>
                        <Typography variant="caption" color="text.secondary">{(item.reason_codes || []).join(", ")}</Typography>
                      </Box>
                    ))}
                  </Box>
                ) : null}

                <Trace trace={run.output?.trace} />
              </>
            ) : (
              <Typography variant="body2" color="text.secondary">Choose an execution to inspect its response, trace, and approval state.</Typography>
            )}
          </CardContent>
        </Card>
      </Box>
    </>
  );
}
