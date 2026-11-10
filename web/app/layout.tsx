import type { Metadata } from "next";
import "./globals.css";
import CyberNavbar from "@/components/CyberNavbar";
import CyberFooter from "@/components/CyberFooter";

export const metadata: Metadata = {
  title: "HPC Cloud Service // Volunteer Computing Grid",
  description: "Distributed volunteer high-performance computing with automated GitHub verification and sandboxed nodes.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className="bg-cyber-void text-zinc-100 antialiased flex flex-col min-h-screen bg-cyber-grid selection:bg-cyber-amber selection:text-cyber-void">
        <CyberNavbar />
        <main className="flex-1">{children}</main>
        <CyberFooter />
      </body>
    </html>
  );
}

