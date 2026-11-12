"use client";

import { useEffect, useState } from "react";
import { getJson } from "../../lib/api";

import Box from "@mui/material/Box";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import Chip from "@mui/material/Chip";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";
import { Banner, PageHeader } from "../../components/ui";

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
      <PageHeader overline="Models" title="One interface. The provider stays behind it." />
      <Banner>{error}</Banner>
      <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", md: "1fr 1fr" }, gap: 2 }}>
        {providers.map((provider) => (
          <Card key={provider.name}>
            <CardContent>
              <Stack direction="row" justifyContent="space-between" alignItems="center" spacing={1}>
                <Typography variant="h5">{provider.name}</Typography>
                <Chip size="small" color="primary" variant="outlined" label={provider.model} />
              </Stack>
              <Stack direction="row" flexWrap="wrap" gap={0.75} sx={{ mt: 1.5 }}>
                {Object.entries(provider.capabilities || {})
                  .filter(([, value]) => value === true)
                  .map(([name]) => (
                    <Chip key={name} size="small" label={name.replaceAll("_", " ")} />
                  ))}
              </Stack>
            </CardContent>
          </Card>
        ))}
      </Box>
    </>
  );
}
