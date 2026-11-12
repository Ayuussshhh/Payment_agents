"use client";

import { useEffect, useState } from "react";
import { getJson } from "../../lib/api";

export default function Skills() {
  const [skills, setSkills] = useState([]);
  const [error, setError] = useState("");

  useEffect(() => {
    getJson("/v1/skills")
      .then((body) => setSkills(body.skills || []))
      .catch(() => setError("The engine is not running on port 8001."));
  }, []);

  return (
    <>
      <header className="top">
        <div>
          <p className="eyebrow">Skills</p>
          <h1>Capabilities an agent is allowed to call.</h1>
        </div>
      </header>
      {error ? <p className="banner">{error}</p> : null}
      <div className="cards">
        {skills.map((skill) => (
          <article className="card" key={skill.id}>
            <div className="card-top">
              <h2>{skill.name}</h2>
              <span className="pill">v{skill.version}</span>
            </div>
            <p>{skill.description}</p>
            <span className="meta">{skill.execution_mode}</span>
          </article>
        ))}
      </div>
    </>
  );
}
