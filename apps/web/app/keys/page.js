"use client";

import { useCallback, useEffect, useState } from "react";
import { apiGet, apiPost } from "../../lib/api";

import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import CardHeader from "@mui/material/CardHeader";
import Stack from "@mui/material/Stack";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableContainer from "@mui/material/TableContainer";
import TableHead from "@mui/material/TableHead";
import TableRow from "@mui/material/TableRow";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import { Banner, PageHeader, StatusChip } from "../../components/ui";

const MONO = { fontFamily: "ui-monospace, monospace" };

export default function Keys() {
  const [rows, setRows] = useState([]);
  const [name, setName] = useState("");
  const [created, setCreated] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    apiGet("/v1/api-keys").then((data) => setRows(data.api_keys || [])).catch((caught) => setError(caught.message));
  }, []);
  useEffect(() => { load(); }, [load]);

  async function create(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const body = await apiPost("/v1/api-keys", { name });
      setCreated(body.api_key);
      setName("");
      load();
    } catch (caught) { setError(caught.message); }
    finally { setBusy(false); }
  }

  async function revoke(id) {
    setError("");
    try { await apiPost(`/v1/api-keys/${id}/revoke`, {}); load(); }
    catch (caught) { setError(caught.message); }
  }

  return (
    <>
      <PageHeader overline="API keys" title="A key cannot approve a payment." />
      <Banner>{error}</Banner>

      <Card sx={{ mb: 3 }}>
        <CardHeader title="Create a key" />
        <CardContent>
          <Stack component="form" onSubmit={create} direction={{ xs: "column", sm: "row" }} spacing={1.5} alignItems={{ sm: "flex-end" }}>
            <TextField label="Name" value={name} onChange={(e) => setName(e.target.value)} placeholder="CI pipeline" required size="small" sx={{ flex: 1 }} />
            <Button type="submit" variant="contained" disabled={busy}>Create key</Button>
          </Stack>
          {created ? (
            <Box sx={{ mt: 2, p: 1.5, borderRadius: 2, border: "1px dashed", borderColor: "success.main", bgcolor: "rgba(34,197,94,0.06)" }}>
              <Typography variant="body2" color="text.secondary">Copy this now. It is shown once.</Typography>
              <Typography sx={{ ...MONO, mt: 0.5, wordBreak: "break-all", color: "success.dark" }}>{created.secret}</Typography>
            </Box>
          ) : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader title="Keys" action={<Button size="small" onClick={load}>Refresh</Button>} />
        <CardContent>
          {rows.length === 0 ? (
            <Typography variant="body2" color="text.secondary">No keys yet.</Typography>
          ) : (
            <TableContainer>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Name</TableCell>
                    <TableCell>Prefix</TableCell>
                    <TableCell>Status</TableCell>
                    <TableCell align="right" />
                  </TableRow>
                </TableHead>
                <TableBody>
                  {rows.map((row) => (
                    <TableRow key={row.id} hover>
                      <TableCell>{row.name}</TableCell>
                      <TableCell sx={MONO}>mk_{row.prefix}…</TableCell>
                      <TableCell><StatusChip status={row.revoked_at ? "revoked" : "active"} /></TableCell>
                      <TableCell align="right">
                        {row.revoked_at ? null : <Button size="small" color="inherit" variant="outlined" onClick={() => revoke(row.id)}>Revoke</Button>}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </CardContent>
      </Card>
    </>
  );
}
