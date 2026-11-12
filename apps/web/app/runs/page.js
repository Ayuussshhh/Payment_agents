"use client";

import { useState } from "react";
import { apiGet, apiPost } from "../../lib/api";

export default function Runs() {
  const [runId, setRunId] = useState("");
  const [run, setRun] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function act(label, action) {
    setBusy(true);
    setError("");
    try {
      const body = await action();
      setRun(body.run);
    } catch (caught) {
      setError(`${label}: ${caught.message}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <header className="top">
        <div>
          <p className="eyebrow">Runs</p>
          <h1>A run can pause, resume, and stop.</h1>
        </div>
      </header>

      {error ? <p className="banner">{error}</p> : null}

      <section className="panel">
        <div className="panel-head">
          <h2>Inspect a run</h2>
        </div>
        <div className="inline-form">
          <label className="field">
            <span>Run id</span>
            <input value={runId} onChange={(event) => setRunId(event.target.value)} placeholder="uuid from the Agents page" />
          </label>
          <button className="btn btn-primary" disabled={busy || !runId} onClick={() => act("Load", () => apiGet(`/v1/runs/${runId}`))}>
            Load
          </button>
        </div>
      </section>

      {run ? (
        <section className="panel">
          <div className="panel-head">
            <h2>Run {run.id.slice(0, 8)}…</h2>
            <span className={`badge badge-${run.status}`}>{run.status}</span>
          </div>
          <p className="meta">Stop reason: {run.stop_reason || "—"} · Proposals: {(run.output?.proposal_ids || []).length}</p>
          <div className="actions">
            <button className="btn" disabled={busy} onClick={() => act("Resume", () => apiPost(`/v1/runs/${run.id}/resume`, {}))}>
              Resume
            </button>
            <button className="btn" disabled={busy} onClick={() => act("Cancel", () => apiPost(`/v1/runs/${run.id}/cancel`, {}))}>
              Cancel
            </button>
          </div>
          <Trace trace={run.output?.trace} />
        </section>
      ) : null}
    </>
  );
}

function Trace({ trace }) {
  if (!trace || trace.length === 0) return <p className="meta">No trace steps.</p>;
  return (
    <ol className="trace">
      {trace.map((item, index) => (
        <li key={index}>
          <span className="trace-agent">{item.agent}</span>
          <span>{item.text}</span>
        </li>
      ))}
    </ol>
  );
}
