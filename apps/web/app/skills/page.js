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
      <PageHeader overline="Skills" title="Capabilities an agent is allowed to call." />
      <Banner>{error}</Banner>
      <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr", lg: "repeat(3, 1fr)" }, gap: 2 }}>
        {skills.map((skill) => (
          <Card key={skill.id}>
            <CardContent>
              <Stack direction="row" justifyContent="space-between" alignItems="center" spacing={1}>
                <Typography variant="h5">{skill.name}</Typography>
                <Chip size="small" label={`v${skill.version}`} variant="outlined" />
              </Stack>
              <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>{skill.description}</Typography>
              <Chip size="small" label={skill.execution_mode} sx={{ mt: 1.5 }} />
            </CardContent>
          </Card>
        ))}
      </Box>
    </>
  );
}
