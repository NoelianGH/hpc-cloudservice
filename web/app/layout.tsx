import type { Metadata } from "next";
import "./globals.css";
import CyberNavbar from "@/components/CyberNavbar";
import CyberFooter from "@/components/CyberFooter";

export const metadata: Metadata = {
  title: "IdleScale • Turn Idle Devices into Supercomputing Power",
  description: "Platform komputasi terdistribusi generasi baru. Ubah kapasitas idle perangkat PC relawan menjadi kekuatan superkomputer terisolasi aman dengan validasi anti-fake GitHub.",
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

