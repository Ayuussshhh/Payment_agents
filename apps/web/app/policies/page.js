"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { apiGet, apiPost, idemKey } from "../../lib/api";

import Accordion from "@mui/material/Accordion";
import AccordionDetails from "@mui/material/AccordionDetails";
import AccordionSummary from "@mui/material/AccordionSummary";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import Chip from "@mui/material/Chip";
import MenuItem from "@mui/material/MenuItem";
import Stack from "@mui/material/Stack";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import { Banner, PageHeader, StatusChip, money } from "../../components/ui";

const MONO = { fontFamily: "ui-monospace, monospace" };

function Kicker({ n, title, subtitle, action }) {
  return (
    <Stack direction="row" alignItems="flex-start" spacing={1.25} sx={{ mb: 2 }}>
      {n ? <Box sx={{ width: 28, height: 28, flexShrink: 0, display: "grid", placeItems: "center", borderRadius: "50%", bgcolor: "primary.main", color: "#fff", fontSize: "0.72rem", fontWeight: 700 }}>{n}</Box> : null}
      <Box sx={{ flex: 1 }}>
        <Typography variant="h5">{title}</Typography>
        {subtitle ? <Typography variant="caption" color="text.secondary">{subtitle}</Typography> : null}
      </Box>
      {action}
    </Stack>
  );
}

function PolicySummary({ policy, onSelect }) {
  const constraints = policy.constraints || {};
  const specs = constraints.required_specs || {};
  const rules = [
    ["Max total", money(policy.maximum_total_minor, policy.currency)],
    ["Allowed brands", constraints.allowed_brands?.length ? constraints.allowed_brands.join(", ") : "Any"],
    ["Minimum specs", [specs.ram_gb_min && `${specs.ram_gb_min} GB RAM`, specs.storage_gb_min && `${specs.storage_gb_min} GB ${specs.storage_type || "storage"}`].filter(Boolean).join(" · ") || "None"],
    ["Approval", constraints.approval_required ? "Required" : "Policy-based"],
  ];
  return (
    <Box sx={{ display: "flex", flexWrap: "wrap", gap: 2, p: 2, borderRadius: 2, border: "1px solid", borderColor: "primary.light", bgcolor: "rgba(20,83,116,0.04)", mb: 2 }}>
      <Box sx={{ flex: "1 1 260px", minWidth: 0 }}>
        <Typography variant="overline" color="primary">Currently enforced · version {policy.version}</Typography>
        <Typography variant="body2" color="text.secondary" sx={{ my: 0.5 }}>{policy.original_instruction}</Typography>
        <Button size="small" onClick={onSelect}>Inspect full version ↗</Button>
      </Box>
      <Box sx={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 1.5, flex: "1 1 220px" }}>
        {rules.map(([label, value]) => (
          <Box key={label}>
            <Typography variant="caption" color="text.secondary">{label}</Typography>
            <Typography variant="body2" sx={{ fontWeight: 600 }}>{value}</Typography>
          </Box>
        ))}
      </Box>
    </Box>
  );
}

export default function Policies() {
  const [rows, setRows] = useState([]);
  const [instruction, setInstruction] = useState("");
  const [policyId, setPolicyId] = useState("");
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [selected, setSelected] = useState(null);

  const load = useCallback(() => apiGet("/v1/policies").then((data) => setRows(data.policies || [])).catch((caught) => setError(caught.message)), []);
  useEffect(() => { load(); }, [load]);

  const groups = useMemo(() => {
    const result = new Map();
    for (const row of rows) {
      if (!result.has(row.policy_id)) result.set(row.policy_id, []);
      result.get(row.policy_id).push(row);
    }
    return [...result.entries()].map(([id, versions]) => ({ id, name: versions[0]?.name || "Policy", versions: versions.sort((a, b) => b.version - a.version) }));
  }, [rows]);

  async function create(event) {
    event.preventDefault();
    setBusy("compile"); setError("");
    try {
      const body = await apiPost("/v1/policies", { instruction, ...(policyId ? { policy_id: policyId } : {}) });
      setInstruction(""); setSelected(body.policy); await load();
    } catch (caught) { setError(caught.message); }
    finally { setBusy(""); }
  }

  async function activate(versionId) {
    setBusy(versionId); setError("");
    try { const body = await apiPost(`/v1/policies/${versionId}/activate`, {}, { idempotencyKey: idemKey() }); setSelected(body.policy); await load(); }
    catch (caught) { setError(caught.message); }
    finally { setBusy(""); }
  }

  return (
    <>
      <PageHeader
        overline="Policy center · Immutable versions"
        title="Clear rules for every agent action."
        subtitle="Draft in plain language. Review the compiled limits. Activate one version, and keep the full version history for audit."
        action={<Chip color="success" variant="outlined" label={`${groups.length} ${groups.length === 1 ? "policy" : "policies"}`} />}
      />
      <Banner>{error}</Banner>

      {selected ? (
        <Card sx={{ mb: 3 }}>
          <CardContent>
            <Stack direction="row" justifyContent="space-between" alignItems="flex-start" spacing={2}>
              <Box>
                <Typography variant="overline" color="primary">Latest draft</Typography>
                <Typography variant="h5">{selected.name} · v{selected.version}</Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>{selected.original_instruction}</Typography>
              </Box>
              <StatusChip status={selected.status} />
            </Stack>
          </CardContent>
        </Card>
      ) : null}

      <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", md: "minmax(0,0.8fr) minmax(0,1.4fr)" }, gap: 2, alignItems: "start" }}>
        <Card>
          <CardContent>
            <Kicker n="01" title="Write or revise a policy" subtitle="Each compile creates a new immutable revision." />
            <TextField select label="Policy version" value={policyId} onChange={(e) => setPolicyId(e.target.value)} fullWidth size="small" sx={{ mb: 2 }}>
              <MenuItem value="">Create a new policy</MenuItem>
              {groups.map((group) => <MenuItem key={group.id} value={group.id}>{group.name} · {group.versions.length} version{group.versions.length === 1 ? "" : "s"}</MenuItem>)}
            </TextField>
            <Box component="form" onSubmit={create}>
              <TextField
                label="Plain-language instruction" value={instruction} onChange={(e) => setInstruction(e.target.value)} required multiline rows={7} fullWidth size="small" sx={{ mb: 2 }}
                placeholder="Example: Keep purchases below $250, allow items from these brands, require 16 GB RAM, and ask me to approve every cart."
              />
              <Button type="submit" variant="contained" disabled={busy === "compile" || !instruction.trim()}>{busy === "compile" ? "Compiling…" : policyId ? "Compile next version" : "Create policy draft"}</Button>
            </Box>
            <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 1.5 }}>The compiler can suggest a draft. Only the deterministic policy engine evaluates carts.</Typography>
          </CardContent>
        </Card>

        <Stack spacing={2}>
          <Stack direction="row" justifyContent="space-between" alignItems="center">
            <Box>
              <Typography variant="overline" color="primary">02 · Policy library</Typography>
              <Typography variant="h5">Policies and versions</Typography>
            </Box>
            <Button size="small" onClick={load}>Refresh</Button>
          </Stack>

          {!groups.length ? (
            <Card><CardContent sx={{ textAlign: "center", py: 4 }}>
              <Typography variant="h6">No policies yet</Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>Create a policy to define budgets, product constraints, and approval requirements for your agents.</Typography>
            </CardContent></Card>
          ) : groups.map((group) => {
            const active = group.versions.find((version) => version.status === "active");
            return (
              <Card key={group.id}>
                <CardContent>
                  <Stack direction="row" justifyContent="space-between" alignItems="center" spacing={1} sx={{ mb: 1.5 }}>
                    <Box>
                      <Typography variant="h5">{group.name}</Typography>
                      <Typography variant="caption" color="text.secondary">Policy ID <Box component="span" sx={MONO}>{group.id}</Box></Typography>
                    </Box>
                    {active ? <StatusChip status="active" sx={{ "& .MuiChip-label": { textTransform: "none" } }} /> : <Chip size="small" color="warning" label="No active version" />}
                  </Stack>

                  {active ? <PolicySummary policy={active} onSelect={() => setSelected(active)} /> : <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>Activate a reviewed draft before running purchase proposals.</Typography>}

                  <Accordion elevation={0} disableGutters sx={{ border: "1px solid", borderColor: "divider", borderRadius: 2, "&:before": { display: "none" } }}>
                    <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                      <Typography variant="body2" sx={{ fontWeight: 600 }}>Version history</Typography>
                      <Chip size="small" label={group.versions.length} sx={{ ml: 1 }} />
                    </AccordionSummary>
                    <AccordionDetails>
                      <Stack spacing={1.5}>
                        {group.versions.map((version) => (
                          <Box key={version.id} sx={{ p: 1.5, border: "1px solid", borderColor: "divider", borderRadius: 2 }}>
                            <Stack direction="row" justifyContent="space-between" alignItems="center" spacing={1}>
                              <Stack direction="row" alignItems="center" spacing={1}>
                                <Typography variant="body2" sx={{ fontWeight: 600 }}>Version {version.version}</Typography>
                                <StatusChip status={version.status} />
                              </Stack>
                              <Button size="small" onClick={() => setSelected(version)}>Inspect</Button>
                            </Stack>
                            <Typography variant="body2" color="text.secondary" sx={{ my: 1 }}>{version.original_instruction}</Typography>
                            <Stack direction="row" flexWrap="wrap" gap={1.5} sx={{ color: "text.secondary", fontSize: "0.78rem" }}>
                              <span>Maximum <b>{money(version.maximum_total_minor, version.currency)}</b></span>
                              <span>{version.constraints?.approval_required ? "Human approval required" : "Automatic approval rules"}</span>
                              <span>{(version.ambiguities || []).length} ambiguities</span>
                            </Stack>
                            {(version.ambiguities || []).length ? <Typography variant="caption" sx={{ display: "block", mt: 1, color: "warning.dark" }}>Resolve: {version.ambiguities.join(" · ")}</Typography> : null}
                            {version.status === "draft" ? (
                              <Button size="small" variant="contained" sx={{ mt: 1.5 }} disabled={(version.ambiguities || []).length > 0 || Boolean(busy)} onClick={() => activate(version.id)}>
                                {busy === version.id ? "Activating…" : "Activate version"}
                              </Button>
                            ) : null}
                          </Box>
                        ))}
                      </Stack>
                    </AccordionDetails>
                  </Accordion>
                </CardContent>
              </Card>
            );
          })}
        </Stack>
      </Box>
    </>
  );
}
