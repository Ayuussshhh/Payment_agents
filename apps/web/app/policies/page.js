"use client";

import { useCallback, useEffect, useState } from "react";
import { apiGet, apiPost, idemKey } from "../../lib/api";

const SAMPLE =
  "Order a Dell laptop for the team. The total must not exceed $800, including tax and delivery. " +
  "At least 16 GB of RAM and a 512 GB SSD. No warranty and no accessories. Do not pay until I approve.";

export default function Policies() {
  const [rows, setRows] = useState([]);
  const [instruction, setInstruction] = useState(SAMPLE);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    apiGet("/v1/policies")
      .then((data) => setRows(data.policies || []))
      .catch((caught) => setError(caught.message));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function create(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await apiPost("/v1/policies", { instruction });
      load();
    } catch (caught) {
      setError(caught.message);
    } finally {
      setBusy(false);
    }
  }

  async function activate(versionId) {
    setError("");
    try {
      await apiPost(`/v1/policies/${versionId}/activate`, {}, { idempotencyKey: idemKey() });
      load();
    } catch (caught) {
      setError(caught.message);
    }
  }

  return (
    <>
      <header className="top">
        <div>
          <p className="eyebrow">Policies</p>
          <h1>A draft is not an active rule.</h1>
        </div>
      </header>

      {error ? <p className="banner">{error}</p> : null}

      <section className="panel">
        <div className="panel-head">
          <h2>Compile an instruction</h2>
        </div>
        <form onSubmit={create}>
          <label className="field">
            <span>Plain-language rule</span>
            <textarea rows={4} value={instruction} onChange={(event) => setInstruction(event.target.value)} />
          </label>
          <button className="btn btn-primary" type="submit" disabled={busy}>
            {busy ? "Compiling…" : "Compile draft"}
          </button>
        </form>
      </section>

      <section className="panel">
        <div className="panel-head">
          <h2>Versions</h2>
          <button className="link-button" onClick={load}>
            Refresh
          </button>
        </div>
        {rows.length === 0 ? (
          <p className="meta">No policies yet. Compile one above.</p>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Status</th>
                <th>Max</th>
                <th>Instruction</th>
                <th>Ambiguities</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id}>
                  <td>
                    <span className={`badge badge-${row.status}`}>{row.status}</span>
                  </td>
                  <td>{money(row.maximum_total_minor, row.currency)}</td>
                  <td className="truncate">{row.original_instruction}</td>
                  <td>{(row.ambiguities || []).length}</td>
                  <td>
                    {row.status === "draft" ? (
                      <button
                        className="btn"
                        disabled={(row.ambiguities || []).length > 0}
                        title={(row.ambiguities || []).length > 0 ? "Resolve ambiguities first" : "Activate"}
                        onClick={() => activate(row.id)}
                      >
                        Activate
                      </button>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </>
  );
}

function money(minor, currency) {
  if (minor == null) return "—";
  return `${(minor / 100).toFixed(2)} ${currency || "USD"}`;
}
