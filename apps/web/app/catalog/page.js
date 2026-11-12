"use client";

import { useCallback, useEffect, useState } from "react";
import { apiDelete, apiGet, apiPost, apiPut } from "../../lib/api";

const EMPTY = { sku: "", name: "", brand: "", category: "", description: "", currency: "USD", unit_amount_minor: "", ram_gb: "", storage_gb: "", storage_type: "", source_url: "" };

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
    <main className="studio-page catalog-studio">
      <header className="page-heading">
        <div><p className="eyebrow">Merchant data <span className="eyebrow-dot" /> Workspace catalog</p><h1>Your catalog. Your prices. Every change has a version.</h1><p className="lede">Start with an empty workspace. Research a real item on the web, verify its details, then add it to the catalog. Only saved catalog values can enter a proposal.</p></div>
        <div className="heading-status"><span className="status-indicator" /> {items.length} active item{items.length === 1 ? "" : "s"}</div>
      </header>
      {error ? <p className="banner" role="alert">{error}</p> : null}

      <section className="catalog-workspace">
        <div className="catalog-main">
          <section className="panel catalog-research">
            <div className="section-kicker"><span>01</span><div><h2>Research from the web</h2><p>Live search results with source links. Nothing is imported until you review it.</p></div></div>
            <form className="inline-form research-form" onSubmit={searchWeb}><label className="field"><span>Search query</span><input value={researchQuery} onChange={(event) => setResearchQuery(event.target.value)} placeholder="Brand, product name, or model number" required maxLength={300} /></label><button className="btn btn-primary" disabled={busy === "research" || !researchQuery.trim()}>{busy === "research" ? "Searching…" : "Search web"}</button></form>
            {research.length ? <div className="research-results">{research.map((source, index) => <article className="research-result" key={`${source.url}-${index}`}><div><strong>{source.title || "Web result"}</strong><p>{source.content}</p><a href={source.url} target="_blank" rel="noreferrer">Open original source ↗</a></div><button className="btn" onClick={() => useResearchResult(source)}>Review item</button></article>)}</div> : null}
          </section>

          <section className="panel" id="catalog-editor">
            <div className="section-kicker"><span>02</span><div><h2>{form.sku ? `Edit ${form.sku}` : "Add a verified catalog item"}</h2><p>Set the price and specifications you are willing to sell at. Web snippets never set them for you.</p></div>{form.sku ? <button className="link-button" type="button" onClick={() => setForm(EMPTY)}>Cancel edit</button> : null}</div>
            <form onSubmit={save} className="catalog-form">
              <label className="field"><span>SKU</span><input value={form.sku || form.skuDraft || ""} onChange={(event) => form.sku ? null : setField("skuDraft", event.target.value.toUpperCase())} disabled={Boolean(form.sku)} required maxLength={80} placeholder="A unique merchant SKU" /></label>
              <label className="field"><span>Product name</span><input value={form.name} onChange={(event) => setField("name", event.target.value)} required maxLength={160} /></label>
              <label className="field"><span>Brand</span><input value={form.brand} onChange={(event) => setField("brand", event.target.value)} required maxLength={100} /></label>
              <label className="field"><span>Category</span><input value={form.category} onChange={(event) => setField("category", event.target.value)} maxLength={100} placeholder="e.g. laptop" /></label>
              <label className="field"><span>Price</span><div className="money-input"><input type="number" step="0.01" min="0.01" value={form.unit_amount_minor} onChange={(event) => setField("unit_amount_minor", event.target.value)} required /><select value={form.currency} onChange={(event) => setField("currency", event.target.value)}><option>USD</option><option>INR</option><option>EUR</option><option>GBP</option></select></div></label>
              <label className="field"><span>RAM (GB)</span><input type="number" min="1" value={form.ram_gb} onChange={(event) => setField("ram_gb", event.target.value)} /></label>
              <label className="field"><span>Storage (GB)</span><input type="number" min="1" value={form.storage_gb} onChange={(event) => setField("storage_gb", event.target.value)} /></label>
              <label className="field"><span>Storage type</span><input value={form.storage_type} onChange={(event) => setField("storage_type", event.target.value)} placeholder="SSD" /></label>
              <label className="field field-wide"><span>Description</span><textarea rows={3} value={form.description} onChange={(event) => setField("description", event.target.value)} maxLength={2000} /></label>
              <label className="field field-wide"><span>Source URL <small>Optional, kept for audit</small></span><input type="url" value={form.source_url} onChange={(event) => setField("source_url", event.target.value)} placeholder="https://…" maxLength={2000} /></label>
              <div className="field-wide"><button className="btn btn-primary" disabled={busy === "save"}>{busy === "save" ? "Saving revision…" : form.sku ? "Save new revision" : "Add to catalog"}</button></div>
            </form>
          </section>
        </div>

        <aside className="catalog-aside">
          <section className="panel catalog-items-panel"><div className="section-kicker"><span>03</span><div><h2>Live catalog</h2><p>Items available to your agent.</p></div><button className="link-button" onClick={load}>Refresh</button></div>
            {items.length ? <div className="catalog-items">{items.map((item) => <article className="catalog-item" key={item.sku}><div className="catalog-item-title"><div><strong>{item.name}</strong><small>{item.brand} · {item.sku} · v{item.version}</small></div><span>{money(item.unit_amount_minor, item.currency)}</span></div><div className="chips">{item.category ? <span className="chip">{item.category}</span> : null}{item.ram_gb ? <span className="chip">{item.ram_gb} GB RAM</span> : null}{item.storage_gb ? <span className="chip">{item.storage_gb} GB {item.storage_type || "storage"}</span> : null}</div><div className="catalog-item-actions"><button className="link-button" onClick={() => showHistory(item.sku)}>Version history</button><button className="link-button" onClick={() => setForm({ ...item, unit_amount_minor: (item.unit_amount_minor / 100).toFixed(2), skuDraft: "" })}>Edit</button><button className="link-button danger-link" onClick={() => archive(item.sku)}>Archive</button></div></article>)}</div> : <div className="catalog-empty"><span>⌕</span><h3>No catalog items yet</h3><p>Your workspace starts empty. Search the web or add a verified item to make it available to agents.</p></div>}
          </section>
          {history ? <section className="panel catalog-history"><div className="section-kicker"><div><h2>{history.sku} revisions</h2><p>Immutable item snapshots.</p></div><button className="link-button" onClick={() => setHistory(null)}>Close</button></div>{history.versions.map((version) => <details className="history-revision" key={version.version}><summary><span>Version {version.version}</span><time>{version.created_at ? new Date(version.created_at).toLocaleString() : ""}</time></summary><pre>{JSON.stringify(version.snapshot, null, 2)}</pre></details>)}</section> : null}
        </aside>
      </section>
    </main>
  );
}

function money(minor, currency = "USD") { return new Intl.NumberFormat(undefined, { style: "currency", currency }).format((minor || 0) / 100); }
