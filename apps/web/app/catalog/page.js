"use client";

import { useCallback, useEffect, useState } from "react";
import { apiDelete, apiGet, apiPost, apiPut } from "../../lib/api";

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
import { Banner, PageHeader, money } from "../../components/ui";

const EMPTY = { sku: "", name: "", brand: "", category: "", description: "", currency: "USD", unit_amount_minor: "", ram_gb: "", storage_gb: "", storage_type: "", source_url: "" };

function Kicker({ n, title, subtitle, action }) {
  return (
    <Stack direction="row" alignItems="flex-start" spacing={1.25} sx={{ mb: 2 }}>
      <Box sx={{ width: 28, height: 28, flexShrink: 0, display: "grid", placeItems: "center", borderRadius: "50%", bgcolor: "primary.main", color: "#fff", fontSize: "0.72rem", fontWeight: 700 }}>{n}</Box>
      <Box sx={{ flex: 1 }}>
        <Typography variant="h5">{title}</Typography>
        {subtitle ? <Typography variant="caption" color="text.secondary">{subtitle}</Typography> : null}
      </Box>
      {action}
    </Stack>
  );
}

export default function Catalog() {
  const [items, setItems] = useState([]);
  const [form, setForm] = useState(EMPTY);
  const [researchQuery, setResearchQuery] = useState("");
  const [research, setResearch] = useState([]);
  const [history, setHistory] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");

  const load = useCallback(async () => {
    try { const body = await apiGet("/v1/catalog"); setItems(body.catalog || []); setError(""); }
    catch (caught) { setError(caught.message); }
  }, []);
  useEffect(() => { load(); }, [load]);

  function setField(key, value) { setForm((current) => ({ ...current, [key]: value })); }

  async function save(event) {
    event.preventDefault(); setBusy("save"); setError("");
    const payload = {
      name: form.name.trim(), brand: form.brand.trim(), category: form.category.trim(), description: form.description.trim(),
      currency: form.currency.toUpperCase(), unit_amount_minor: Math.round(Number(form.unit_amount_minor) * 100),
      ram_gb: form.ram_gb ? Number(form.ram_gb) : null, storage_gb: form.storage_gb ? Number(form.storage_gb) : null,
      storage_type: form.storage_type || null, source_url: form.source_url || null,
    };
    try {
      if (form.sku) await apiPut(`/v1/catalog/${encodeURIComponent(form.sku)}`, payload);
      else await apiPost("/v1/catalog", { ...payload, sku: form.skuDraft.trim() });
      setForm(EMPTY); await load();
    } catch (caught) { setError(caught.message); }
    finally { setBusy(""); }
  }

  async function searchWeb(event) {
    event.preventDefault(); setBusy("research"); setError(""); setResearch([]);
    try { const body = await apiPost("/v1/catalog/research", { query: researchQuery }); setResearch(body.results || []); }
    catch (caught) { setError(caught.message); }
    finally { setBusy(""); }
  }

  async function showHistory(sku) {
    setError("");
    try { const body = await apiGet(`/v1/catalog/${encodeURIComponent(sku)}/versions`); setHistory({ sku, versions: body.versions || [] }); }
    catch (caught) { setError(caught.message); }
  }

  async function archive(sku) {
    setError("");
    try { await apiDelete(`/v1/catalog/${encodeURIComponent(sku)}`); await load(); }
    catch (caught) { setError(caught.message); }
  }

  function useResearchResult(item) {
    setForm((current) => ({ ...current, sku: "", name: item.title || "", description: item.content || "", source_url: item.url || "" }));
    document.getElementById("catalog-editor")?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  return (
    <>
      <PageHeader
        overline="Merchant data · Workspace catalog"
        title="Your catalog. Your prices. Every change has a version."
        subtitle="Start with an empty workspace. Research a real item on the web, verify its details, then add it to the catalog. Only saved catalog values can enter a proposal."
        action={<Chip color="success" variant="outlined" label={`${items.length} active item${items.length === 1 ? "" : "s"}`} />}
      />
      <Banner>{error}</Banner>

      <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", lg: "minmax(0,1.5fr) minmax(0,0.95fr)" }, gap: 2, alignItems: "start" }}>
        <Stack spacing={2}>
          <Card>
            <CardContent>
              <Kicker n="01" title="Research from the web" subtitle="Live search results with source links. Nothing is imported until you review it." />
              <Stack component="form" onSubmit={searchWeb} direction={{ xs: "column", sm: "row" }} spacing={1.5} alignItems={{ sm: "flex-end" }}>
                <TextField label="Search query" value={researchQuery} onChange={(e) => setResearchQuery(e.target.value)} placeholder="Brand, product name, or model number" required inputProps={{ maxLength: 300 }} size="small" sx={{ flex: 1 }} />
                <Button type="submit" variant="contained" disabled={busy === "research" || !researchQuery.trim()}>{busy === "research" ? "Searching…" : "Search web"}</Button>
              </Stack>
              {research.length ? (
                <Stack spacing={1.5} sx={{ mt: 2 }}>
                  {research.map((source, index) => (
                    <Stack key={`${source.url}-${index}`} direction="row" alignItems="center" justifyContent="space-between" spacing={2} sx={{ p: 1.5, border: "1px solid", borderColor: "divider", borderRadius: 2 }}>
                      <Box sx={{ minWidth: 0 }}>
                        <Typography variant="body2" sx={{ fontWeight: 600 }}>{source.title || "Web result"}</Typography>
                        <Typography variant="caption" color="text.secondary" sx={{ display: "block", my: 0.5 }}>{source.content}</Typography>
                        <Box component="a" href={source.url} target="_blank" rel="noreferrer" sx={{ color: "primary.main", fontSize: "0.78rem" }}>Open original source ↗</Box>
                      </Box>
                      <Button size="small" variant="outlined" onClick={() => useResearchResult(source)}>Review item</Button>
                    </Stack>
                  ))}
                </Stack>
              ) : null}
            </CardContent>
          </Card>

          <Card id="catalog-editor">
            <CardContent>
              <Kicker
                n="02"
                title={form.sku ? `Edit ${form.sku}` : "Add a verified catalog item"}
                subtitle="Set the price and specifications you are willing to sell at. Web snippets never set them for you."
                action={form.sku ? <Button size="small" onClick={() => setForm(EMPTY)}>Cancel edit</Button> : null}
              />
              <Box component="form" onSubmit={save} sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr" }, gap: 2 }}>
                <TextField label="SKU" value={form.sku || form.skuDraft || ""} onChange={(e) => (form.sku ? null : setField("skuDraft", e.target.value.toUpperCase()))} disabled={Boolean(form.sku)} required inputProps={{ maxLength: 80 }} placeholder="A unique merchant SKU" size="small" />
                <TextField label="Product name" value={form.name} onChange={(e) => setField("name", e.target.value)} required inputProps={{ maxLength: 160 }} size="small" />
                <TextField label="Brand" value={form.brand} onChange={(e) => setField("brand", e.target.value)} required inputProps={{ maxLength: 100 }} size="small" />
                <TextField label="Category" value={form.category} onChange={(e) => setField("category", e.target.value)} inputProps={{ maxLength: 100 }} placeholder="e.g. laptop" size="small" />
                <Stack direction="row" spacing={1}>
                  <TextField label="Price" type="number" inputProps={{ step: "0.01", min: "0.01" }} value={form.unit_amount_minor} onChange={(e) => setField("unit_amount_minor", e.target.value)} required size="small" sx={{ flex: 1 }} />
                  <TextField select label="Currency" value={form.currency} onChange={(e) => setField("currency", e.target.value)} size="small" sx={{ width: 110 }}>
                    {["USD", "INR", "EUR", "GBP"].map((c) => <MenuItem key={c} value={c}>{c}</MenuItem>)}
                  </TextField>
                </Stack>
                <TextField label="RAM (GB)" type="number" inputProps={{ min: "1" }} value={form.ram_gb} onChange={(e) => setField("ram_gb", e.target.value)} size="small" />
                <TextField label="Storage (GB)" type="number" inputProps={{ min: "1" }} value={form.storage_gb} onChange={(e) => setField("storage_gb", e.target.value)} size="small" />
                <TextField label="Storage type" value={form.storage_type} onChange={(e) => setField("storage_type", e.target.value)} placeholder="SSD" size="small" />
                <TextField label="Description" value={form.description} onChange={(e) => setField("description", e.target.value)} inputProps={{ maxLength: 2000 }} multiline rows={3} size="small" sx={{ gridColumn: "1 / -1" }} />
                <TextField label="Source URL (optional, kept for audit)" type="url" value={form.source_url} onChange={(e) => setField("source_url", e.target.value)} placeholder="https://…" inputProps={{ maxLength: 2000 }} size="small" sx={{ gridColumn: "1 / -1" }} />
                <Box sx={{ gridColumn: "1 / -1" }}>
                  <Button type="submit" variant="contained" disabled={busy === "save"}>{busy === "save" ? "Saving revision…" : form.sku ? "Save new revision" : "Add to catalog"}</Button>
                </Box>
              </Box>
            </CardContent>
          </Card>
        </Stack>

        <Stack spacing={2}>
          <Card>
            <CardContent>
              <Kicker n="03" title="Live catalog" subtitle="Items available to your agent." action={<Button size="small" onClick={load}>Refresh</Button>} />
              {items.length ? (
                <Stack spacing={1.5}>
                  {items.map((item) => (
                    <Box key={item.sku} sx={{ p: 1.5, border: "1px solid", borderColor: "divider", borderRadius: 2 }}>
                      <Stack direction="row" justifyContent="space-between" alignItems="flex-start" spacing={1}>
                        <Box sx={{ minWidth: 0 }}>
                          <Typography variant="body2" sx={{ fontWeight: 600 }}>{item.name}</Typography>
                          <Typography variant="caption" color="text.secondary">{item.brand} · {item.sku} · v{item.version}</Typography>
                        </Box>
                        <Typography sx={{ fontWeight: 700, whiteSpace: "nowrap" }}>{money(item.unit_amount_minor, item.currency)}</Typography>
                      </Stack>
                      <Stack direction="row" flexWrap="wrap" gap={0.75} sx={{ my: 1 }}>
                        {item.category ? <Chip size="small" label={item.category} /> : null}
                        {item.ram_gb ? <Chip size="small" label={`${item.ram_gb} GB RAM`} /> : null}
                        {item.storage_gb ? <Chip size="small" label={`${item.storage_gb} GB ${item.storage_type || "storage"}`} /> : null}
                      </Stack>
                      <Stack direction="row" flexWrap="wrap" gap={1.5} sx={{ pt: 1, borderTop: "1px solid", borderColor: "divider" }}>
                        <Button size="small" onClick={() => showHistory(item.sku)}>Version history</Button>
                        <Button size="small" onClick={() => setForm({ ...item, unit_amount_minor: (item.unit_amount_minor / 100).toFixed(2), skuDraft: "" })}>Edit</Button>
                        <Button size="small" color="error" onClick={() => archive(item.sku)}>Archive</Button>
                      </Stack>
                    </Box>
                  ))}
                </Stack>
              ) : (
                <Box sx={{ textAlign: "center", py: 3 }}>
                  <Typography variant="h6">No catalog items yet</Typography>
                  <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>Your workspace starts empty. Search the web or add a verified item to make it available to agents.</Typography>
                </Box>
              )}
            </CardContent>
          </Card>

          {history ? (
            <Card>
              <CardContent>
                <Kicker title={`${history.sku} revisions`} subtitle="Immutable item snapshots." action={<Button size="small" onClick={() => setHistory(null)}>Close</Button>} />
                {history.versions.map((version) => (
                  <Accordion key={version.version} elevation={0} disableGutters sx={{ border: "1px solid", borderColor: "divider", borderRadius: 2, mb: 1, "&:before": { display: "none" } }}>
                    <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                      <Typography variant="body2" sx={{ flex: 1 }}>Version {version.version}</Typography>
                      <Typography variant="caption" color="text.secondary">{version.created_at ? new Date(version.created_at).toLocaleString() : ""}</Typography>
                    </AccordionSummary>
                    <AccordionDetails>
                      <Box component="pre" sx={{ m: 0, p: 1.5, maxHeight: 320, overflow: "auto", borderRadius: 1.5, bgcolor: "grey.50", fontSize: "0.72rem", fontFamily: "ui-monospace, monospace" }}>
                        {JSON.stringify(version.snapshot, null, 2)}
                      </Box>
                    </AccordionDetails>
                  </Accordion>
                ))}
              </CardContent>
            </Card>
          ) : null}
        </Stack>
      </Box>
    </>
  );
}
