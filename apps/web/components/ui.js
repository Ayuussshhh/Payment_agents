"use client";

import Alert from "@mui/material/Alert";
import Box from "@mui/material/Box";
import Chip from "@mui/material/Chip";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

// Maps a domain status string to an MUI color for Chips/badges.
const SUCCESS = ["valid", "active", "captured", "succeeded", "completed", "allow", "approved"];
const WARNING = ["pending", "draft", "reserved", "authorized", "running", "paused", "needs_approval", "unknown"];
const ERROR = ["rejected", "revoked", "voided", "failed", "deny", "expired", "cancelled", "limited", "error"];

export function statusColor(status) {
  const s = String(status || "").toLowerCase();
  if (SUCCESS.includes(s)) return "success";
  if (WARNING.includes(s)) return "warning";
  if (ERROR.includes(s)) return "error";
  return "default";
}

export function StatusChip({ status, size = "small", sx }) {
  const label = String(status || "—").replace(/_/g, " ");
  return <Chip size={size} label={label} color={statusColor(status)} variant="filled" sx={{ textTransform: "capitalize", ...sx }} />;
}

export function PageHeader({ overline, title, subtitle, action }) {
  return (
    <Stack direction={{ xs: "column", sm: "row" }} justifyContent="space-between" alignItems={{ xs: "flex-start", sm: "flex-end" }} spacing={2} sx={{ mb: 3 }}>
      <Box sx={{ minWidth: 0 }}>
        {overline ? <Typography variant="overline" color="primary" sx={{ display: "block", mb: 0.5 }}>{overline}</Typography> : null}
        <Typography variant="h1" sx={{ fontSize: { xs: "1.6rem", md: "2rem" } }}>{title}</Typography>
        {subtitle ? <Typography variant="body1" color="text.secondary" sx={{ mt: 1, maxWidth: "64ch" }}>{subtitle}</Typography> : null}
      </Box>
      {action ? <Box sx={{ flexShrink: 0 }}>{action}</Box> : null}
    </Stack>
  );
}

export function Banner({ children, severity = "error", onClose, sx }) {
  if (!children) return null;
  return <Alert severity={severity} onClose={onClose} variant="outlined" sx={{ mb: 2, borderRadius: 2, ...sx }}>{children}</Alert>;
}

export function money(minor, currency = "USD") {
  if (minor == null) return "—";
  try {
    return new Intl.NumberFormat(undefined, { style: "currency", currency: currency || "USD" }).format(minor / 100);
  } catch {
    return `${(minor / 100).toFixed(2)} ${currency || "USD"}`;
  }
}

export function shortId(id, n = 8) {
  return id ? `${String(id).slice(0, n)}…` : "—";
}
