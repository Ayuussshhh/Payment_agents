"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { signIn, signUp } from "../../lib/auth-client";
import { apiPost } from "../../lib/api";

export default function SignIn() {
  const router = useRouter();
  const [mode, setMode] = useState("sign-in");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [workspace, setWorkspace] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      if (mode === "sign-up") {
        const result = await signUp.email({ email, password, name: name || email });
        if (result.error) throw new Error(result.error.message || "Sign-up failed");
      } else {
        const result = await signIn.email({ email, password });
        if (result.error) throw new Error(result.error.message || "Sign-in failed");
      }
      // Ensure the signed-in user has an organization and owner role.
      await apiPost("/v1/onboarding", { organization_name: workspace });
      router.push("/");
      router.refresh();
    } catch (caught) {
      setError(caught.message || "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-wrap">
      <form className="auth-card" onSubmit={submit}>
        <div className="auth-brand">
          <span className="mark">M</span>
          <strong>Mandate Studio</strong>
        </div>
        <h1 className="auth-title">{mode === "sign-up" ? "Create your workspace" : "Sign in"}</h1>
        <p className="auth-sub">The studio calls the engine. It never approves a payment on its own.</p>

        {mode === "sign-up" ? (
          <label className="field">
            <span>Name</span>
            <input value={name} onChange={(event) => setName(event.target.value)} placeholder="Ada Lovelace" />
          </label>
        ) : null}
        <label className="field">
          <span>Email</span>
          <input type="email" required value={email} onChange={(event) => setEmail(event.target.value)} placeholder="you@company.com" />
        </label>
        <label className="field">
          <span>Password</span>
          <input type="password" required minLength={8} value={password} onChange={(event) => setPassword(event.target.value)} placeholder="At least 8 characters" />
        </label>
        {mode === "sign-up" ? (
          <label className="field">
            <span>Workspace name</span>
            <input value={workspace} onChange={(event) => setWorkspace(event.target.value)} placeholder="Acme" />
          </label>
        ) : null}

        {error ? <p className="banner">{error}</p> : null}

        <button className="btn btn-primary" type="submit" disabled={busy}>
          {busy ? "Working…" : mode === "sign-up" ? "Create workspace" : "Sign in"}
        </button>

        <button
          type="button"
          className="auth-switch"
          onClick={() => {
            setMode(mode === "sign-up" ? "sign-in" : "sign-up");
            setError("");
          }}
        >
          {mode === "sign-up" ? "Already have an account? Sign in" : "New here? Create a workspace"}
        </button>
      </form>
    </div>
  );
}
