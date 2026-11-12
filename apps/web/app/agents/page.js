"use client";

import { useState } from "react";
import { apiPost } from "../../lib/api";

export default function Agents() {
  const [name, setName] = useState("Laptop buyer");
  const [graphKind, setGraphKind] = useState("buyer");
  const [prompt, setPrompt] = useState("You help buy one laptop that fits the policy. Propose a single SKU.");
  const [model, setModel] = useState("openai/gpt-4o-mini");
  const [goal, setGoal] = useState("Buy a Dell laptop under the policy.");
  const [agent, setAgent] = useState(null);
  const [version, setVersion] = useState(null);
  const [run, setRun] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function step(label, action, setter) {
    setBusy(true);
    setError("");
    try {
      const result = await action();
      if (setter) setter(result);
      return result;
    } catch (caught) {
      setError(`${label}: ${caught.message}`);
      throw caught;
    } finally {
      setBusy(false);
    }
  }

  async function createAgent() {
    const body = await step("Create agent", () => apiPost("/v1/agents", { name, graph_kind: graphKind }));
    setAgent(body.agent);
    setVersion(null);
    setRun(null);
  }

  async function publish() {
    if (!agent) return;
    const body = await step("Publish version", () =>
      apiPost(`/v1/agents/${agent.id}/versions`, { prompt, provider: "openai", model, temperature: 0 }),
    );
    setVersion(body.version);
  }

  async function startRun() {
    if (!agent) return;
    const body = await step("Run", () => apiPost(`/v1/agents/${agent.id}/runs`, { input: { goal } }));
    setRun(body.run);
  }

  return (
    <>
      <header className="top">
        <div>
          <p className="eyebrow">Agents</p>
          <h1>Published versions, not a draft text box.</h1>
        </div>
      </header>

      {error ? <p className="banner">{error}</p> : null}

      <section className="panel">
        <div className="panel-head">
          <h2>1 · Define the agent</h2>
          {agent ? <span className="badge badge-active">created</span> : null}
        </div>
        <div className="inline-form">
          <label className="field">
            <span>Name</span>
            <input value={name} onChange={(event) => setName(event.target.value)} />
          </label>
          <label className="field">
            <span>Graph</span>
            <select value={graphKind} onChange={(event) => setGraphKind(event.target.value)}>
              <option value="buyer">buyer</option>
              <option value="compiler">compiler</option>
            </select>
          </label>
          <button className="btn btn-primary" onClick={createAgent} disabled={busy}>
            Create agent
          </button>
        </div>
      </section>

      <section className="panel">
        <div className="panel-head">
          <h2>2 · Publish a version</h2>
          {version ? <span className="badge badge-active">v{version.version}</span> : null}
        </div>
        <label className="field">
          <span>System prompt (frozen once published)</span>
          <textarea rows={3} value={prompt} onChange={(event) => setPrompt(event.target.value)} />
        </label>
        <div className="inline-form">
          <label className="field">
            <span>Model</span>
            <input value={model} onChange={(event) => setModel(event.target.value)} />
          </label>
          <button className="btn" onClick={publish} disabled={busy || !agent}>
            Publish version
          </button>
        </div>
      </section>

      <section className="panel">
        <div className="panel-head">
          <h2>3 · Run it</h2>
          {run ? <span className={`badge badge-${run.status}`}>{run.status}</span> : null}
        </div>
        <div className="inline-form">
          <label className="field">
            <span>Goal</span>
            <input value={goal} onChange={(event) => setGoal(event.target.value)} />
          </label>
          <button className="btn btn-primary" onClick={startRun} disabled={busy || !version}>
            Start run
          </button>
        </div>
        {run ? (
          <>
            <p className="meta">Run {run.id} · {run.stop_reason || run.status}</p>
            <Trace trace={run.output?.trace} />
          </>
        ) : (
          <p className="meta">Publish a version first, then run. Runs need a model key configured.</p>
        )}
      </section>
    </>
  );
}

function Trace({ trace }) {
  if (!trace || trace.length === 0) return <p className="meta">No trace yet.</p>;
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
