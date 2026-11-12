"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { apiGet, apiPost } from "../../lib/api";

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
    <main className="studio-page runs-studio">
      <header className="runs-header"><div><p className="eyebrow">Execution history</p><h1>Runs</h1><p>Review agent activity, tool evidence, policy decisions, and outcomes.</p></div><Link className="btn btn-primary" href="/agents">Build an agent</Link></header>
      {error ? <p className="banner" role="alert">{error}</p> : null}
      <section className="runs-grid">
        <div className="runs-list panel"><div className="panel-head"><div><h2>Recent runs</h2><p className="meta">Latest 50 in this workspace</p></div><button className="btn" onClick={load} disabled={busy}>Refresh</button></div>
          {runs.length ? <div className="run-table">{runs.map((item) => <button className={`run-list-item${run?.id === item.id ? " selected" : ""}`} key={item.id} onClick={() => inspect(item.id)}><span className={`run-status-mark status-${item.status}`} /><span className="run-list-copy"><strong>{item.agent_name || "Agent"} <small>v{item.agent_version}</small></strong><span>{item.input?.goal || item.input?.query || "Agent execution"}</span><small>{new Date(item.created_at).toLocaleString()}</small></span><span className={`badge badge-${item.status}`}>{item.status}</span></button>)}</div> : <div className="runs-empty"><h3>No runs yet</h3><p>Published agent executions will appear here with their traces and policy outcomes.</p><Link className="inline-link" href="/agents">Open the agent studio →</Link></div>}
        </div>
        <section className="run-detail panel"><div className="panel-head"><div><p className="eyebrow">Inspection</p><h2>{run ? `Run ${run.id.slice(0, 8)}…` : "Select a run"}</h2></div>{run ? <span className={`badge badge-${run.status}`}>{run.status}</span> : null}</div>
          {run ? <><p className="meta">{run.stop_reason || "No stop reason"} · Proposals: {(run.output?.proposal_ids || []).length}</p><div className="actions">{run.status === "paused" ? <button className="btn" disabled={busy} onClick={() => act("Resume", () => apiPost(`/v1/runs/${run.id}/resume`, {}))}>Resume</button> : null}{!["succeeded", "completed", "failed", "cancelled", "limited"].includes(run.status) ? <button className="btn" disabled={busy} onClick={() => act("Cancel", () => apiPost(`/v1/runs/${run.id}/cancel`, {}))}>Cancel run</button> : null}</div>{run.output?.final_text ? <article className="run-final"><h3>Agent response</h3><p>{run.output.final_text}</p></article> : null}{run.output?.proposal_results?.length ? <div className="run-proposals"><h3>Policy evaluations</h3>{run.output.proposal_results.map((item) => <div key={item.proposal_id}><strong>{item.sku} · {item.decision}</strong><small>{(item.reason_codes || []).join(", ")}</small></div>)}</div> : null}<Trace trace={run.output?.trace} /></> : <div className="runs-empty"><p>Choose an execution to inspect its response, trace, and approval state.</p></div>}
        </section>
      </section>
    </main>
  );
}

function Trace({ trace }) {
  if (!trace?.length) return <div className="run-trace"><h3>Execution trace</h3><p className="meta">No trace steps were recorded.</p></div>;
  return <div className="run-trace"><h3>Execution trace</h3><ol className="trace">{trace.map((item, index) => <li key={`${item.agent}-${index}`}><span className="trace-agent">{item.agent}</span>{item.url ? <a href={item.url} target="_blank" rel="noreferrer">{item.text} ↗</a> : <span>{item.text}</span>}</li>)}</ol></div>;
}
