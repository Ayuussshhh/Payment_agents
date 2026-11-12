"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { getJson } from "../lib/api";

export default function Overview() {
  const [contract, setContract] = useState(null);
  const [health, setHealth] = useState(null);
  const [skills, setSkills] = useState([]);
  const [providers, setProviders] = useState([]);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([getJson("/v1"), getJson("/health"), getJson("/v1/skills"), getJson("/v1/models")])
      .then(([contractBody, healthBody, skillBody, modelBody]) => {
        setContract(contractBody);
        setHealth(healthBody);
        setSkills(skillBody.skills || []);
        setProviders(modelBody.providers || []);
      })
      .catch(() => setError("The engine is not running on port 8001."));
  }, []);

  return (
    <>
      <header className="top">
        <div>
          <p className="eyebrow">Workspace</p>
          <h1>Build an agent. Keep the payment outside it.</h1>
        </div>
        <span className={health && health.database ? "pill live" : "pill"}>{health && health.database ? "Database connected" : "Waiting for database"}</span>
      </header>
      {error ? <p className="banner">{error}</p> : null}
      <div className="stats">
        <article>
          <span>Engine</span>
          <strong>{contract ? contract.engine_version : "…"}</strong>
        </article>
        <article>
          <span>Contract</span>
          <strong>{contract ? contract.version : "…"}</strong>
        </article>
        <article>
          <span>Skills</span>
          <strong>{skills.length}</strong>
        </article>
        <article>
          <span>Providers</span>
          <strong>{providers.length}</strong>
        </article>
      </div>
      <section className="panel">
        <div className="panel-head">
          <h2>Ready in the engine</h2>
          <Link href="/skills">View skills</Link>
        </div>
        <ul className="resource-list">
          {(contract ? contract.resources : []).map((item) => (
            <li key={item.method + item.path}>
              <code>{item.method}</code>
              <span>{item.path}</span>
            </li>
          ))}
        </ul>
      </section>
    </>
  );
}
