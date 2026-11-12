"use client";

import { createTheme } from "@mui/material/styles";

// Design tokens ported from the BizTask360 (Vuexy) admin template.
const PRIMARY = { light: "#5588A3", main: "#145374", dark: "#115E59", contrastText: "#ffffff" };
const SECONDARY = { light: "#64748B", main: "#475569", dark: "#334155", contrastText: "#ffffff" };
const TEXT_PRIMARY = "rgba(31, 41, 51, 0.87)";
const TEXT_SECONDARY = "rgba(31, 41, 51, 0.60)";
const TEXT_DISABLED = "rgba(31, 41, 51, 0.38)";
const DIVIDER = "rgba(31, 41, 51, 0.12)";

const theme = createTheme({
  palette: {
    mode: "light",
    primary: PRIMARY,
    secondary: SECONDARY,
    error: { light: "#FCA5A5", main: "#EF4444", dark: "#B91C1C", contrastText: "#ffffff" },
    warning: { light: "#FED7AA", main: "#FB923C", dark: "#C2410C", contrastText: "#111827" },
    info: { light: "#7DD3FC", main: "#38BDF8", dark: "#0284C7", contrastText: "#0F172A" },
    success: { light: "#4ADE80", main: "#22C55E", dark: "#15803D", contrastText: "#ffffff" },
    grey: {
      50: "#F8FAFC", 100: "#F1F5F9", 200: "#E2E8F0", 300: "#CBD5E1", 400: "#94A3B8",
      500: "#64748B", 600: "#475569", 700: "#334155", 800: "#1E293B", 900: "#0F172A",
    },
    text: { primary: TEXT_PRIMARY, secondary: TEXT_SECONDARY, disabled: TEXT_DISABLED },
    divider: DIVIDER,
    background: { paper: "#ffffff", default: "#F8FAFC" },
    action: {
      hover: "rgba(20, 83, 116, 0.06)",
      selected: "rgba(20, 83, 116, 0.10)",
      focus: "rgba(20, 83, 116, 0.12)",
    },
  },
  shape: { borderRadius: 10 },
  typography: {
    fontFamily: 'var(--font-montserrat), "Montserrat", -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif',
    fontSize: 14,
    h1: { fontWeight: 700, fontSize: "2rem", letterSpacing: "-0.02em", lineHeight: 1.2 },
    h2: { fontWeight: 700, fontSize: "1.5rem", letterSpacing: "-0.015em", lineHeight: 1.25 },
    h3: { fontWeight: 700, fontSize: "1.25rem", letterSpacing: "-0.01em" },
    h4: { fontWeight: 600, fontSize: "1.125rem" },
    h5: { fontWeight: 600, fontSize: "1rem" },
    h6: { fontWeight: 600, fontSize: "0.9375rem" },
    subtitle1: { fontWeight: 600 },
    subtitle2: { fontWeight: 600, fontSize: "0.8125rem" },
    body1: { fontSize: "0.9375rem", lineHeight: 1.55 },
    body2: { fontSize: "0.8125rem", lineHeight: 1.5 },
    button: { textTransform: "none", fontWeight: 600 },
    overline: { fontWeight: 700, fontSize: "0.68rem", letterSpacing: "0.13em", lineHeight: 1.4 },
    caption: { fontSize: "0.75rem" },
  },
  shadows: [
    "none",
    "0px 2px 4px rgba(47, 43, 61, 0.08)",
    "0px 2px 6px rgba(47, 43, 61, 0.10)",
    "0px 3px 8px rgba(47, 43, 61, 0.10)",
    "0px 3px 9px rgba(47, 43, 61, 0.11)",
    "0px 4px 10px rgba(47, 43, 61, 0.11)",
    "0px 4px 11px rgba(47, 43, 61, 0.12)",
    "0px 4px 18px rgba(47, 43, 61, 0.08)",
    "0px 4px 13px rgba(47, 43, 61, 0.13)",
    "0px 5px 14px rgba(47, 43, 61, 0.14)",
    "0px 5px 15px rgba(47, 43, 61, 0.15)",
    "0px 5px 16px rgba(47, 43, 61, 0.15)",
    "0px 6px 17px rgba(47, 43, 61, 0.16)",
    "0px 6px 18px rgba(47, 43, 61, 0.16)",
    "0px 6px 19px rgba(47, 43, 61, 0.17)",
    "0px 7px 20px rgba(47, 43, 61, 0.17)",
    "0px 7px 21px rgba(47, 43, 61, 0.18)",
    "0px 7px 22px rgba(47, 43, 61, 0.18)",
    "0px 8px 23px rgba(47, 43, 61, 0.19)",
    "0px 8px 24px rgba(47, 43, 61, 0.19)",
    "0px 9px 25px rgba(47, 43, 61, 0.20)",
    "0px 9px 26px rgba(47, 43, 61, 0.21)",
    "0px 9px 27px rgba(47, 43, 61, 0.21)",
    "0px 10px 28px rgba(47, 43, 61, 0.22)",
    "0px 10px 30px rgba(47, 43, 61, 0.22)",
  ],
  components: {
    MuiCssBaseline: {
      styleOverrides: {
        body: { backgroundColor: "#F8FAFC" },
        "::selection": { background: "rgba(20, 83, 116, 0.16)" },
      },
    },
    MuiPaper: { styleOverrides: { root: { backgroundImage: "none" } } },
    MuiCard: {
      defaultProps: { elevation: 0 },
      styleOverrides: {
        root: {
          border: "1px solid rgba(31, 41, 51, 0.08)",
          borderRadius: 12,
          boxShadow: "0px 3px 12px rgba(47, 43, 61, 0.06)",
        },
      },
    },
    MuiCardHeader: {
      styleOverrides: {
        root: { padding: "20px 20px 0" },
        title: { fontSize: "1.0625rem", fontWeight: 700 },
        subheader: { fontSize: "0.8125rem", marginTop: 2 },
      },
    },
    MuiCardContent: {
      styleOverrides: { root: { padding: 20, "&:last-child": { paddingBottom: 20 } } },
    },
    MuiButton: {
      defaultProps: { disableElevation: true },
      styleOverrides: {
        root: { borderRadius: 8, padding: "7px 18px" },
        sizeSmall: { padding: "4px 12px" },
        containedPrimary: { boxShadow: "0px 3px 8px rgba(20, 83, 116, 0.28)" },
      },
    },
    MuiOutlinedInput: { styleOverrides: { root: { borderRadius: 8 } } },
    MuiChip: { styleOverrides: { root: { fontWeight: 600 }, sizeSmall: { fontSize: "0.72rem" } } },
    MuiTableCell: {
      styleOverrides: {
        root: { borderColor: DIVIDER },
        head: {
          fontWeight: 600, fontSize: "0.72rem", textTransform: "uppercase",
          letterSpacing: "0.06em", color: TEXT_SECONDARY,
        },
      },
    },
    MuiTableRow: { styleOverrides: { root: { "&:last-child td": { borderBottom: 0 } } } },
    MuiAppBar: { styleOverrides: { root: { backdropFilter: "saturate(180%) blur(6px)" } } },
    MuiTooltip: { styleOverrides: { tooltip: { fontSize: "0.72rem" } } },
    MuiListItemButton: {
      styleOverrides: {
        root: {
          borderRadius: 8,
          "&.Mui-selected": {
            backgroundColor: PRIMARY.main,
            color: "#fff",
            boxShadow: "0px 3px 8px rgba(20, 83, 116, 0.30)",
            "&:hover": { backgroundColor: PRIMARY.dark },
            "& .MuiListItemIcon-root": { color: "#fff" },
          },
        },
      },
    },
  },
});

export default theme;
