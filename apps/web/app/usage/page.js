"use client";

import { useEffect, useState } from "react";
import { apiGet } from "../../lib/api";

export default function Usage() {
  const [usage, setUsage] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    apiGet("/v1/usage")
      .then((data) => setUsage(data.usage))
      .catch((caught) => setError(caught.message));
  }, []);

  return (
    <>
      <header className="top">
        <div>
          <p className="eyebrow">Usage</p>
          <h1>Token counts for this workspace.</h1>
        </div>
      </header>

      {error ? <p className="banner">{error}</p> : null}

      <div className="stats">
        <article>
          <span>Calls</span>
          <strong>{usage ? usage.calls : "…"}</strong>
        </article>
        <article>
          <span>Input tokens</span>
          <strong>{usage ? usage.input_tokens : "…"}</strong>
        </article>
        <article>
          <span>Output tokens</span>
          <strong>{usage ? usage.output_tokens : "…"}</strong>
        </article>
        <article>
          <span>Models</span>
          <strong>{usage ? (usage.by_model || []).length : "…"}</strong>
        </article>
      </div>

      <section className="panel">
        <div className="panel-head">
          <h2>By model</h2>
        </div>
        {usage && usage.by_model.length ? (
          <table className="table">
            <thead>
              <tr>
                <th>Provider</th>
                <th>Model</th>
                <th>Calls</th>
                <th>Input</th>
                <th>Output</th>
              </tr>
            </thead>
            <tbody>
              {usage.by_model.map((row) => (
                <tr key={`${row.provider}/${row.model}`}>
                  <td>{row.provider}</td>
                  <td className="mono">{row.model}</td>
                  <td>{row.calls}</td>
                  <td>{row.input_tokens}</td>
                  <td>{row.output_tokens}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="meta">No model calls recorded yet. Run an agent to see usage.</p>
        )}
      </section>
    </>
  );
}
