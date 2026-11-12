"use client";

import { useEffect, useState } from "react";
import { apiGet } from "../../lib/api";

import Box from "@mui/material/Box";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import CardHeader from "@mui/material/CardHeader";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableContainer from "@mui/material/TableContainer";
import TableHead from "@mui/material/TableHead";
import TableRow from "@mui/material/TableRow";
import Typography from "@mui/material/Typography";
import { Banner, PageHeader } from "../../components/ui";

const MONO = { fontFamily: "ui-monospace, monospace" };

function Stat({ label, value }) {
  return (
    <Card>
      <CardContent>
        <Typography variant="caption" color="text.secondary">{label}</Typography>
        <Typography variant="h2" sx={{ mt: 0.5, fontSize: "1.75rem" }}>{value}</Typography>
      </CardContent>
    </Card>
  );
}

export default function Usage() {
  const [usage, setUsage] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    apiGet("/v1/usage")
      .then((data) => setUsage(data.usage))
      .catch((caught) => setError(caught.message));
  }, []);

  const dash = (v) => (usage ? v : "…");

  return (
    <>
      <PageHeader overline="Usage" title="Token counts for this workspace." />
      <Banner>{error}</Banner>

      <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr 1fr", md: "repeat(4, 1fr)" }, gap: 2, mb: 3 }}>
        <Stat label="Calls" value={dash(usage?.calls)} />
        <Stat label="Input tokens" value={dash(usage?.input_tokens)} />
        <Stat label="Output tokens" value={dash(usage?.output_tokens)} />
        <Stat label="Models" value={dash((usage?.by_model || []).length)} />
      </Box>

      <Card>
        <CardHeader title="By model" />
        <CardContent>
          {usage && usage.by_model.length ? (
            <TableContainer>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Provider</TableCell>
                    <TableCell>Model</TableCell>
                    <TableCell align="right">Calls</TableCell>
                    <TableCell align="right">Input</TableCell>
                    <TableCell align="right">Output</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {usage.by_model.map((row) => (
                    <TableRow key={`${row.provider}/${row.model}`} hover>
                      <TableCell>{row.provider}</TableCell>
                      <TableCell sx={MONO}>{row.model}</TableCell>
                      <TableCell align="right">{row.calls}</TableCell>
                      <TableCell align="right">{row.input_tokens}</TableCell>
                      <TableCell align="right">{row.output_tokens}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          ) : (
            <Typography variant="body2" color="text.secondary">No model calls recorded yet. Run an agent to see usage.</Typography>
          )}
        </CardContent>
      </Card>
    </>
  );
}
