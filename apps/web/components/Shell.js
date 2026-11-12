"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { signOut, useSession } from "../lib/auth-client";

import AppBar from "@mui/material/AppBar";
import Avatar from "@mui/material/Avatar";
import Box from "@mui/material/Box";
import Chip from "@mui/material/Chip";
import CircularProgress from "@mui/material/CircularProgress";
import Divider from "@mui/material/Divider";
import Drawer from "@mui/material/Drawer";
import IconButton from "@mui/material/IconButton";
import List from "@mui/material/List";
import ListItemButton from "@mui/material/ListItemButton";
import ListItemIcon from "@mui/material/ListItemIcon";
import ListItemText from "@mui/material/ListItemText";
import ListSubheader from "@mui/material/ListSubheader";
import Toolbar from "@mui/material/Toolbar";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";
import { useTheme } from "@mui/material/styles";
import useMediaQuery from "@mui/material/useMediaQuery";

import MenuIcon from "@mui/icons-material/Menu";
import LogoutIcon from "@mui/icons-material/Logout";
import ShoppingCartCheckoutIcon from "@mui/icons-material/ShoppingCartCheckout";
import Inventory2OutlinedIcon from "@mui/icons-material/Inventory2Outlined";
import PolicyOutlinedIcon from "@mui/icons-material/PolicyOutlined";
import FactCheckOutlinedIcon from "@mui/icons-material/FactCheckOutlined";
import PaymentsOutlinedIcon from "@mui/icons-material/PaymentsOutlined";
import SmartToyOutlinedIcon from "@mui/icons-material/SmartToyOutlined";
import HistoryOutlinedIcon from "@mui/icons-material/HistoryOutlined";
import ExtensionOutlinedIcon from "@mui/icons-material/ExtensionOutlined";
import HubOutlinedIcon from "@mui/icons-material/HubOutlined";
import BarChartOutlinedIcon from "@mui/icons-material/BarChartOutlined";
import VpnKeyOutlinedIcon from "@mui/icons-material/VpnKeyOutlined";

const DRAWER_WIDTH = 264;

const GROUPS = [
  {
    label: "Commerce",
    items: [
      { href: "/", label: "Checkout", icon: <ShoppingCartCheckoutIcon fontSize="small" /> },
      { href: "/catalog", label: "Catalog", icon: <Inventory2OutlinedIcon fontSize="small" /> },
      { href: "/policies", label: "Policies", icon: <PolicyOutlinedIcon fontSize="small" /> },
      { href: "/approvals", label: "Approvals", icon: <FactCheckOutlinedIcon fontSize="small" /> },
      { href: "/payments", label: "Payments", icon: <PaymentsOutlinedIcon fontSize="small" /> },
    ],
  },
  {
    label: "Developer",
    items: [
      { href: "/agents", label: "Agents", icon: <SmartToyOutlinedIcon fontSize="small" /> },
      { href: "/runs", label: "Runs", icon: <HistoryOutlinedIcon fontSize="small" /> },
      { href: "/skills", label: "Skills", icon: <ExtensionOutlinedIcon fontSize="small" /> },
      { href: "/models", label: "Models", icon: <HubOutlinedIcon fontSize="small" /> },
      { href: "/usage", label: "Usage", icon: <BarChartOutlinedIcon fontSize="small" /> },
      { href: "/keys", label: "API keys", icon: <VpnKeyOutlinedIcon fontSize="small" /> },
    ],
  },
];

const ALL_ITEMS = GROUPS.flatMap((g) => g.items);

function Brand() {
  return (
    <Box component={Link} href="/" sx={{ display: "flex", alignItems: "center", gap: 1.25, px: 1, py: 2, color: "inherit" }}>
      <Avatar variant="rounded" sx={{ width: 38, height: 38, bgcolor: "primary.main", fontWeight: 700, boxShadow: "0 6px 16px rgba(20,83,116,0.35)" }}>M</Avatar>
      <Box>
        <Typography sx={{ fontWeight: 700, lineHeight: 1.1 }}>Mandate</Typography>
        <Typography variant="caption" color="text.secondary" sx={{ letterSpacing: "0.08em" }}>AGENT COMMERCE</Typography>
      </Box>
    </Box>
  );
}

function NavContent({ pathname, session, onNavigate, onSignOut }) {
  return (
    <Box sx={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <Box sx={{ px: 1.5 }}><Brand /></Box>
      <Divider sx={{ mx: 2 }} />
      <Box sx={{ flex: 1, overflowY: "auto", px: 1.5, py: 1 }}>
        {GROUPS.map((group) => (
          <List
            key={group.label}
            subheader={
              <ListSubheader disableSticky sx={{ bgcolor: "transparent", color: "text.disabled", fontSize: "0.66rem", fontWeight: 700, letterSpacing: "0.12em", lineHeight: 2.4 }}>
                {group.label.toUpperCase()}
              </ListSubheader>
            }
            sx={{ py: 0 }}
          >
            {group.items.map((item) => {
              const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
              return (
                <ListItemButton key={item.href} component={Link} href={item.href} selected={active} onClick={onNavigate} sx={{ mb: 0.25 }}>
                  <ListItemIcon sx={{ minWidth: 34, color: active ? "inherit" : "text.secondary" }}>{item.icon}</ListItemIcon>
                  <ListItemText primaryTypographyProps={{ fontSize: "0.875rem", fontWeight: active ? 600 : 500 }} primary={item.label} />
                </ListItemButton>
              );
            })}
          </List>
        ))}
      </Box>
      <Divider sx={{ mx: 2 }} />
      <Box sx={{ p: 1.5 }}>
        <Box sx={{ display: "flex", alignItems: "center", gap: 1, p: 1, mb: 1, borderRadius: 2, bgcolor: "grey.50", border: "1px solid", borderColor: "divider" }}>
          <Avatar variant="rounded" sx={{ width: 32, height: 32, bgcolor: "primary.light", fontSize: "0.85rem" }}>
            {session?.user?.email?.slice(0, 1).toUpperCase() || "W"}
          </Avatar>
          <Box sx={{ minWidth: 0 }}>
            <Typography variant="body2" sx={{ fontWeight: 600, lineHeight: 1.2 }}>Workspace</Typography>
            <Typography variant="caption" color="text.secondary">PayPal sandbox</Typography>
          </Box>
          <Box sx={{ ml: "auto", width: 8, height: 8, borderRadius: "50%", bgcolor: "success.main" }} />
        </Box>
        <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", px: 0.5 }}>
          <Tooltip title={session?.user?.email || ""}>
            <Typography variant="caption" color="text.secondary" noWrap sx={{ maxWidth: 150 }}>{session?.user?.email}</Typography>
          </Tooltip>
          <Tooltip title="Sign out">
            <IconButton size="small" onClick={onSignOut}><LogoutIcon fontSize="small" /></IconButton>
          </Tooltip>
        </Box>
      </Box>
    </Box>
  );
}

export default function Shell({ children }) {
  const pathname = usePathname();
  const router = useRouter();
  const { data: session, isPending } = useSession();
  const theme = useTheme();
  const isDesktop = useMediaQuery(theme.breakpoints.up("md"));
  const [mobileOpen, setMobileOpen] = useState(false);

  const signedIn = Boolean(session?.user);

  useEffect(() => {
    if (!isPending && !signedIn && pathname !== "/sign-in") {
      router.replace("/sign-in");
    }
  }, [isPending, signedIn, pathname, router]);

  async function handleSignOut() {
    await signOut();
    router.push("/sign-in");
    router.refresh();
  }

  if (pathname === "/sign-in") return <>{children}</>;

  if (isPending || !signedIn) {
    return (
      <Box sx={{ minHeight: "100vh", display: "grid", placeItems: "center", color: "text.secondary", gap: 2 }}>
        <CircularProgress size={28} />
        <Typography variant="body2" color="text.secondary">{isPending ? "Loading…" : "Redirecting to sign-in…"}</Typography>
      </Box>
    );
  }

  const title = ALL_ITEMS.find((i) => (i.href === "/" ? pathname === "/" : pathname.startsWith(i.href)))?.label || "Studio";
  const nav = <NavContent pathname={pathname} session={session} onNavigate={() => setMobileOpen(false)} onSignOut={handleSignOut} />;

  return (
    <Box sx={{ display: "flex", minHeight: "100vh", bgcolor: "background.default" }}>
      <AppBar
        position="fixed"
        color="inherit"
        elevation={0}
        sx={{
          width: { md: `calc(100% - ${DRAWER_WIDTH}px)` },
          ml: { md: `${DRAWER_WIDTH}px` },
          borderBottom: "1px solid", borderColor: "divider",
          bgcolor: "rgba(255,255,255,0.8)",
        }}
      >
        <Toolbar>
          <IconButton edge="start" onClick={() => setMobileOpen(true)} sx={{ mr: 1, display: { md: "none" } }}><MenuIcon /></IconButton>
          <Typography variant="h5" sx={{ flex: 1, fontWeight: 700 }}>{title}</Typography>
          <Chip size="small" label="Sandbox" color="warning" variant="outlined" />
        </Toolbar>
      </AppBar>

      <Box component="nav" sx={{ width: { md: DRAWER_WIDTH }, flexShrink: { md: 0 } }}>
        <Drawer
          variant="temporary"
          open={mobileOpen}
          onClose={() => setMobileOpen(false)}
          ModalProps={{ keepMounted: true }}
          sx={{ display: { xs: "block", md: "none" }, "& .MuiDrawer-paper": { width: DRAWER_WIDTH, boxSizing: "border-box" } }}
        >
          {nav}
        </Drawer>
        <Drawer
          variant="permanent"
          open
          sx={{ display: { xs: "none", md: "block" }, "& .MuiDrawer-paper": { width: DRAWER_WIDTH, boxSizing: "border-box", borderRight: "1px solid", borderColor: "divider" } }}
        >
          {nav}
        </Drawer>
      </Box>

      <Box component="main" sx={{ flexGrow: 1, width: { md: `calc(100% - ${DRAWER_WIDTH}px)` }, minWidth: 0 }}>
        <Toolbar />
        <Box sx={{ p: { xs: 2, md: 4 }, maxWidth: 1280, mx: "auto" }}>{children}</Box>
      </Box>
    </Box>
  );
}
