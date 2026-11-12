"use client";

import Link from "next/link";
import Avatar from "@mui/material/Avatar";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import Typography from "@mui/material/Typography";

export default function CheckoutCancel() {
  return (
    <Box sx={{ minHeight: "60vh", display: "grid", placeItems: "center" }}>
      <Card sx={{ maxWidth: 440, textAlign: "center" }}>
        <CardContent sx={{ p: 4 }}>
          <Avatar sx={{ width: 56, height: 56, mx: "auto", mb: 2, bgcolor: "warning.light", color: "warning.dark", fontSize: "1.6rem", fontWeight: 700 }}>×</Avatar>
          <Typography variant="h3">Payment cancelled</Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 1.5 }}>
            You left the PayPal checkout. Nothing was charged. The approval is still valid if you want to try again.
          </Typography>
          <Button component={Link} href="/" variant="contained" sx={{ mt: 2.5 }}>Back to checkout</Button>
        </CardContent>
      </Card>
    </Box>
  );
}
