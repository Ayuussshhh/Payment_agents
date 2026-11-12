"use client";

import { useEffect, useState } from "react";
import { getJson } from "../../lib/api";

export default function Models() {
  const [providers, setProviders] = useState([]);
  const [error, setError] = useState("");

  useEffect(() => {
    getJson("/v1/models")
      .then((body) => setProviders(body.providers || []))
      .catch(() => setError("The engine is not running on port 8001."));
  }, []);

  return (
    <>
      <header className="top">
        <div>
          <p className="eyebrow">Models</p>
          <h1>One interface. The provider stays behind it.</h1>
        </div>
      </header>
      {error ? <p className="banner">{error}</p> : null}
      <div className="cards">
        {providers.map((provider) => (
          <article className="card" key={provider.name}>
            <div className="card-top">
              <h2>{provider.name}</h2>
              <span className="pill">{provider.model}</span>
            </div>
            <div className="chips">
              {Object.entries(provider.capabilities || {})
                .filter(([, value]) => value === true)
                .map(([name]) => (
                  <span key={name}>{name.replaceAll("_", " ")}</span>
                ))}
            </div>
          </article>
        ))}
      </div>
    </>
  );
}
