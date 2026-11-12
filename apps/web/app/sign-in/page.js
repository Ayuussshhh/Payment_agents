"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { signIn, signUp } from "../../lib/auth-client";
import { apiPost } from "../../lib/api";

import Avatar from "@mui/material/Avatar";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import Stack from "@mui/material/Stack";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import { Banner } from "../../components/ui";

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
      await apiPost("/v1/onboarding", { organization_name: workspace });
      router.push("/");
      router.refresh();
    } catch (caught) {
      setError(caught.message || "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }

  const isSignUp = mode === "sign-up";

  return (
    <Box
      sx={{
        minHeight: "100vh", display: "grid", placeItems: "center", p: 2,
        background: "radial-gradient(800px 500px at 50% -10%, rgba(20,83,116,0.12), transparent 60%), #F8FAFC",
      }}
    >
      <Card sx={{ width: "100%", maxWidth: 420 }}>
        <CardContent sx={{ p: { xs: 3, sm: 4 } }}>
          <Stack direction="row" alignItems="center" spacing={1.25} sx={{ mb: 3 }}>
            <Avatar variant="rounded" sx={{ bgcolor: "primary.main", fontWeight: 700 }}>M</Avatar>
            <Typography sx={{ fontWeight: 700 }}>Mandate Studio</Typography>
          </Stack>

          <Typography variant="h2" sx={{ fontSize: "1.6rem" }}>{isSignUp ? "Create your workspace" : "Sign in"}</Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 1, mb: 3 }}>
            The studio calls the engine. It never approves a payment on its own.
          </Typography>

          <Banner onClose={() => setError("")}>{error}</Banner>

          <Box component="form" onSubmit={submit}>
            <Stack spacing={2}>
              {isSignUp ? (
                <TextField label="Name" value={name} onChange={(e) => setName(e.target.value)} placeholder="Ada Lovelace" fullWidth size="small" />
              ) : null}
              <TextField label="Email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@company.com" fullWidth size="small" />
              <TextField label="Password" type="password" required inputProps={{ minLength: 8 }} value={password} onChange={(e) => setPassword(e.target.value)} placeholder="At least 8 characters" fullWidth size="small" />
              {isSignUp ? (
                <TextField label="Workspace name" value={workspace} onChange={(e) => setWorkspace(e.target.value)} placeholder="Acme" fullWidth size="small" />
              ) : null}
              <Button type="submit" variant="contained" size="large" disabled={busy} fullWidth>
                {busy ? "Working…" : isSignUp ? "Create workspace" : "Sign in"}
              </Button>
              <Button type="button" variant="text" onClick={() => { setMode(isSignUp ? "sign-in" : "sign-up"); setError(""); }} sx={{ color: "text.secondary" }}>
                {isSignUp ? "Already have an account? Sign in" : "New here? Create a workspace"}
              </Button>
            </Stack>
          </Box>
        </CardContent>
      </Card>
    </Box>
  );
}
