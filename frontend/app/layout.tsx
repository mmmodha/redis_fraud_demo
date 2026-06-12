import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Redis Bank Fraud Command Center",
  description: "Redis IRIS fraud-detection demo",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="font-redis-body bg-redis-bg text-redis-text antialiased">
        {children}
      </body>
    </html>
  );
}
