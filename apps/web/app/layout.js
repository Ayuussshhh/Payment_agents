import { Montserrat } from "next/font/google";
import ThemeRegistry from "../components/ThemeRegistry";
import Shell from "../components/Shell";
import "./globals.css";

const montserrat = Montserrat({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-montserrat",
  display: "swap",
});

export const metadata = {
  title: "Mandate Studio",
  description: "Studio for the Mandate Core Engine",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en" className={montserrat.variable}>
      <body>
        <ThemeRegistry>
          <Shell>{children}</Shell>
        </ThemeRegistry>
      </body>
    </html>
  );
}
