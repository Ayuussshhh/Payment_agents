"use client";

import { useEffect, useState } from "react";

export default function Home() {
  const [contract, setContract] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    fetch("/v1")
      .then((response) => {
        if (!response.ok) {
          throw new Error("bad status");
        }
        return response.json();
      })
      .then(setContract)
      .catch(() => setError("The engine is not running on port 8001."));
  }, []);

  return (
    <main>
      <p className="kicker">Core Engine</p>
      <h1>{contract ? contract.name : "Mandate"}</h1>
      <p className="lede">This shell reads the engine. It does not decide a purchase.</p>
      {error ? <p className="error">{error}</p> : null}
      <section>
        <div>
          <span>Contract</span>
          <strong>{contract ? contract.version : "…"}</strong>
        </div>
        <div>
          <span>Engine</span>
          <strong>{contract ? contract.engine_version : "…"}</strong>
        </div>
      </section>
    </main>
  );
}
