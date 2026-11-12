"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { apiGet, apiPost, idemKey } from "../../lib/api";

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
    event.preventDefault(); setBusy("compile"); setError("");
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
    <main className="studio-page policy-studio">
      <header className="page-heading"><div><p className="eyebrow">Policy center <span className="eyebrow-dot" /> Immutable versions</p><h1>Clear rules for every agent action.</h1><p className="lede">Draft in plain language. Review the compiled limits. Activate one version, and keep the full version history for audit.</p></div><div className="heading-status"><span className="status-indicator" /> {groups.length} polic{groups.length === 1 ? "y" : "ies"}</div></header>
      {error ? <p className="banner" role="alert">{error}</p> : null}
      {selected ? <section className="panel policy-selected"><div><p className="eyebrow">Latest draft</p><h2>{selected.name} · v{selected.version}</h2><p>{selected.original_instruction}</p></div><span className={`badge badge-${selected.status}`}>{selected.status}</span></section> : null}
      <section className="policy-layout">
        <div className="panel policy-editor">
          <div className="section-kicker"><span>01</span><div><h2>Write or revise a policy</h2><p>Each compile creates a new immutable revision.</p></div></div>
          <label className="field"><span>Policy version</span><select value={policyId} onChange={(event) => setPolicyId(event.target.value)}><option value="">Create a new policy</option>{groups.map((group) => <option key={group.id} value={group.id}>{group.name} · {group.versions.length} version{group.versions.length === 1 ? "" : "s"}</option>)}</select></label>
          <form onSubmit={create}><label className="field"><span>Plain-language instruction</span><textarea rows={7} value={instruction} onChange={(event) => setInstruction(event.target.value)} placeholder="Example: Keep purchases below $250, allow items from these brands, require 16 GB RAM, and ask me to approve every cart." required /></label><button className="btn btn-primary" disabled={busy === "compile" || !instruction.trim()}>{busy === "compile" ? "Compiling…" : policyId ? "Compile next version" : "Create policy draft"}</button></form>
          <p className="field-hint">The compiler can suggest a draft. Only the deterministic policy engine evaluates carts.</p>
        </div>

        <div className="policy-list">
          <div className="policy-list-head"><div><p className="eyebrow">02 · Policy library</p><h2>Policies and versions</h2></div><button className="link-button" onClick={load}>Refresh</button></div>
          {!groups.length ? <div className="empty policy-empty"><h2>No policies yet</h2><p>Create a policy to define budgets, product constraints, and approval requirements for your agents.</p></div> : groups.map((group) => {
            const active = group.versions.find((version) => version.status === "active");
            return <section className="panel policy-group" key={group.id}><div className="policy-group-head"><div><h2>{group.name}</h2><p className="meta">Policy ID <code>{group.id}</code></p></div>{active ? <span className="badge badge-active">Active · v{active.version}</span> : <span className="badge badge-draft">No active version</span>}</div>
              {active ? <PolicySummary policy={active} onSelect={() => setSelected(active)} /> : <p className="meta">Activate a reviewed draft before running purchase proposals.</p>}
              <details className="policy-versions"><summary>Version history <span>{group.versions.length}</span></summary><div className="version-list">{group.versions.map((version) => <article className="policy-version" key={version.id}><div className="policy-version-top"><div><strong>Version {version.version}</strong><span className={`badge badge-${version.status}`}>{version.status}</span></div><button className="link-button" onClick={() => setSelected(version)}>Inspect</button></div><p>{version.original_instruction}</p><div className="policy-facts"><span>Maximum <b>{money(version.maximum_total_minor, version.currency)}</b></span><span>{version.constraints?.approval_required ? "Human approval required" : "Automatic approval rules"}</span><span>{(version.ambiguities || []).length} ambiguities</span></div>{(version.ambiguities || []).length ? <p className="policy-warning">Resolve: {version.ambiguities.join(" · ")}</p> : null}{version.status === "draft" ? <button className="btn btn-primary" disabled={(version.ambiguities || []).length > 0 || Boolean(busy)} onClick={() => activate(version.id)}>{busy === version.id ? "Activating…" : "Activate version"}</button> : null}</article>)}</div></details>
            </section>;
          })}
        </div>
      </section>
    </main>
  );
}

function PolicySummary({ policy, onSelect }) {
  const constraints = policy.constraints || {};
  const specs = constraints.required_specs || {};
  return <div className="policy-summary"><div className="policy-summary-main"><span className="eyebrow">Currently enforced · version {policy.version}</span><p>{policy.original_instruction}</p><button className="link-button" onClick={onSelect}>Inspect full version ↗</button></div><div className="policy-rules"><div><small>Max total</small><strong>{money(policy.maximum_total_minor, policy.currency)}</strong></div><div><small>Allowed brands</small><strong>{constraints.allowed_brands?.length ? constraints.allowed_brands.join(", ") : "Any"}</strong></div><div><small>Minimum specs</small><strong>{[specs.ram_gb_min && `${specs.ram_gb_min} GB RAM`, specs.storage_gb_min && `${specs.storage_gb_min} GB ${specs.storage_type || "storage"}`].filter(Boolean).join(" · ") || "None"}</strong></div><div><small>Approval</small><strong>{constraints.approval_required ? "Required" : "Policy-based"}</strong></div></div></div>;
}

function money(minor, currency) { if (minor == null) return "—"; return new Intl.NumberFormat(undefined, { style: "currency", currency: currency || "USD" }).format(minor / 100); }
