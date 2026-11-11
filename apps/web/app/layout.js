import "./globals.css";

export const metadata = {
  title: "Mandate",
  description: "Mandate Core Engine",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
