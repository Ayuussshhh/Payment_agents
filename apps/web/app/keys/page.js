"use client";

import { useCallback, useEffect, useState } from "react";
import { apiGet, apiPost } from "../../lib/api";

export default function Keys() {
  const [rows, setRows] = useState([]);
  const [name, setName] = useState("");
  const [created, setCreated] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    apiGet("/v1/api-keys")
      .then((data) => setRows(data.api_keys || []))
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
      const body = await apiPost("/v1/api-keys", { name });
      setCreated(body.api_key);
      setName("");
      load();
    } catch (caught) {
      setError(caught.message);
    } finally {
      setBusy(false);
    }
  }

  async function revoke(id) {
    setError("");
    try {
      await apiPost(`/v1/api-keys/${id}/revoke`, {});
      load();
    } catch (caught) {
      setError(caught.message);
    }
  }

  return (
    <>
      <header className="top">
        <div>
          <p className="eyebrow">API keys</p>
          <h1>A key cannot approve a payment.</h1>
        </div>
      </header>

      {error ? <p className="banner">{error}</p> : null}

      <section className="panel">
        <div className="panel-head">
          <h2>Create a key</h2>
        </div>
        <form onSubmit={create} className="inline-form">
          <label className="field">
            <span>Name</span>
            <input value={name} onChange={(event) => setName(event.target.value)} placeholder="CI pipeline" required />
          </label>
          <button className="btn btn-primary" type="submit" disabled={busy}>
            Create key
          </button>
        </form>
        {created ? (
          <div className="secret">
            <p className="meta">Copy this now. It is shown once.</p>
            <code>{created.secret}</code>
          </div>
        ) : null}
      </section>

      <section className="panel">
        <div className="panel-head">
          <h2>Keys</h2>
          <button className="link-button" onClick={load}>
            Refresh
          </button>
        </div>
        {rows.length === 0 ? (
          <p className="meta">No keys yet.</p>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Prefix</th>
                <th>Status</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id}>
                  <td>{row.name}</td>
                  <td className="mono">mk_{row.prefix}…</td>
                  <td>
                    <span className={`badge badge-${row.revoked_at ? "revoked" : "active"}`}>{row.revoked_at ? "revoked" : "active"}</span>
                  </td>
                  <td className="actions">
                    {row.revoked_at ? null : (
                      <button className="btn" onClick={() => revoke(row.id)}>
                        Revoke
                      </button>
                    )}
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
