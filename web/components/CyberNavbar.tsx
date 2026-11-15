"use client";
import React, { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";

export default function CyberNavbar() {
  const pathname = usePathname();
  const [clusterOnline, setClusterOnline] = useState<boolean | null>(null);
  const [activeNodes, setActiveNodes] = useState<number>(0);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  useEffect(() => {
    fetch("/api/stats")
      .then((res) => res.json())
      .then((data) => {
        setClusterOnline(data.online ?? true);
        setActiveNodes((data.workers || []).filter((w: any) => w.online).length);
      })
      .catch(() => setClusterOnline(false));
  }, []);

  // Tutup menu mobile otomatis saat berpindah halaman
  useEffect(() => {
    setMobileMenuOpen(false);
  }, [pathname]);

  // Tutup menu jika tombol ESC ditekan
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") setMobileMenuOpen(false);
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  // Menu utama di tengah (Desktop)
  const centerLinks = [
    { href: "/", label: "OVERVIEW" },
    { href: "/join", label: "GABUNG" },
    { href: "/appreciation", label: "APPRECIATION" },
  ];

  // Semua menu untuk drawer (Mobile / saat window diminimize)
  const allNavLinks = [
    { href: "/", label: "OVERVIEW" },
    { href: "/join", label: "GABUNG" },
    { href: "/appreciation", label: "APPRECIATION" },
    { href: "/dashboard", label: "DASHBOARD" },
    { href: "/admin", label: "ADMIN" },
  ];

  return (
    <>
      <header className="sticky top-0 z-40 border-b border-cyber-border bg-cyber-void/90 backdrop-blur-md">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3 sm:px-6 lg:px-8 relative">

          {/* ================================================================= */}
          {/* KIRI: Brand / Logo IdleScale                                     */}
          {/* ================================================================= */}
          <Link href="/" className="group flex items-center space-x-3 z-10">
            <div className="relative flex h-10 w-10 items-center justify-center rounded-lg border border-cyber-amber/70 bg-cyber-surface shadow-amber-glow-sm transition-all group-hover:shadow-amber-glow group-hover:border-cyber-amber">
              {/* CPU Cluster Scaling SVG Icon */}
              <svg
                className="h-5 w-5 text-cyber-amber-bright transition-transform duration-300 group-hover:scale-110"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <rect x="4" y="4" width="16" height="16" rx="2" />
                <rect x="9" y="9" width="6" height="6" />
                <line x1="9" y1="1" x2="9" y2="4" />
                <line x1="15" y1="1" x2="15" y2="4" />
                <line x1="9" y1="20" x2="9" y2="23" />
                <line x1="15" y1="20" x2="15" y2="23" />
                <line x1="20" y1="9" x2="23" y2="9" />
                <line x1="20" y1="15" x2="23" y2="15" />
                <line x1="1" y1="9" x2="4" y2="9" />
                <line x1="1" y1="15" x2="4" y2="15" />
              </svg>
              <div className="absolute -top-1 -right-1 h-2 w-2 rounded-full bg-cyber-amber-bright animate-ping opacity-75" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <span className="font-sans text-base font-extrabold tracking-tight text-white group-hover:text-cyber-amber-bright transition-colors">
                  Idle<span className="text-cyber-amber-bright">Scale</span>
                </span>
                <span className="rounded-full bg-cyber-amber-darkest/90 px-2 py-0.5 font-mono text-[10px] font-semibold text-cyber-amber-bright border border-cyber-amber-deep">
                  Cloud v2.4
                </span>
              </div>
              <p className="font-mono text-[10px] text-zinc-400 tracking-wider">COMMUNITY SUPERCOMPUTING NETWORK</p>
            </div>
          </Link>

          {/* ================================================================= */}
          {/* TENGAH: Menu Navigasi Utama (OVERVIEW, GABUNG, APPRECIATION)     */}
          {/* ================================================================= */}
          <nav className="hidden md:flex items-center space-x-1 xl:space-x-2 absolute left-1/2 -translate-x-1/2">
            {centerLinks.map((link) => {
              const isActive = pathname === link.href;
              return (
                <Link
                  key={link.href}
                  href={link.href}
                  className={`relative px-3.5 py-1.5 font-mono text-xs tracking-wider transition-all rounded ${isActive
                    ? "text-cyber-amber-bright bg-cyber-surface border border-cyber-amber/60 shadow-amber-glow-sm"
                    : "text-zinc-400 hover:text-cyber-amber-light hover:bg-cyber-surface/60"
                    }`}
                >
                  {isActive && (
                    <span className="absolute left-1 top-1/2 -translate-y-1/2 text-cyber-amber-light font-bold">
                      &gt;
                    </span>
                  )}
                  <span className={isActive ? "ml-2 font-semibold" : ""}>{link.label}</span>
                </Link>
              );
            })}
          </nav>

          {/* ================================================================= */}
          {/* UJUNG KANAN: REGISTER, LOGIN & Tombol Hamburger (3 Garis)        */}
          {/* ================================================================= */}
          <div className="flex items-center space-x-2 sm:space-x-3 z-10">
            {/* Cluster Telemetry Pill (Hanya di layar sangat lebar 2xl agar tidak sesak) */}
            <div className="hidden 2xl:flex items-center space-x-2 rounded border border-cyber-border bg-cyber-surface/80 px-2.5 py-1 font-mono text-xs mr-1">
              <span className="relative flex h-2 w-2">
                <span
                  className={`absolute inline-flex h-full w-full rounded-full opacity-75 animate-ping ${clusterOnline ? "bg-emerald-400" : "bg-amber-400"
                    }`}
                />
                <span
                  className={`relative inline-flex h-2 w-2 rounded-full ${clusterOnline ? "bg-emerald-500" : "bg-amber-500"
                    }`}
                />
              </span>
              <span className="text-[11px] text-zinc-300">
                CLUSTER:{" "}
                <strong className={clusterOnline ? "text-emerald-400" : "text-amber-400"}>
                  {clusterOnline ? "ONLINE" : "STANDBY"}
                </strong>
              </span>
              <span className="text-zinc-600">|</span>
              <span className="text-[11px] text-zinc-400">
                NODES: <span className="text-cyber-amber-bright">{activeNodes}</span>
              </span>
            </div>

            {/* Desktop Auth Buttons: REGISTER & LOGIN di Ujung Kanan */}
            <div className="hidden md:flex items-center space-x-2">
              <Link
                href="/register"
                className={`flex items-center space-x-1.5 rounded border border-cyber-amber bg-cyber-amber px-3.5 py-1.5 font-mono text-xs font-semibold text-cyber-void transition-all hover:bg-cyber-amber-bright hover:shadow-amber-glow ${pathname === "/register" ? "ring-2 ring-cyber-amber-bright shadow-amber-glow" : ""
                  }`}
              >
                <span>REGISTER</span>
                <span className="text-xs">&rarr;</span>
              </Link>

              <Link
                href="/login"
                className={`px-3.5 py-1.5 font-mono text-xs tracking-wider transition-all rounded border ${pathname === "/login"
                  ? "text-cyber-amber-bright bg-cyber-surface border-cyber-amber shadow-amber-glow-sm font-semibold"
                  : "text-zinc-300 hover:text-cyber-amber-bright hover:bg-cyber-surface border-cyber-border hover:border-cyber-amber/60"
                  }`}
              >
                LOGIN
              </Link>
            </div>

            {/* Tombol Hamburger 3 Garis (Muncul saat layar mengecil / diminimize < md) */}
            <button
              type="button"
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="md:hidden relative flex h-9 w-9 items-center justify-center rounded border border-cyber-border bg-cyber-surface text-cyber-amber-bright hover:border-cyber-amber hover:shadow-amber-glow-sm transition-all focus:outline-none"
              aria-label="Toggle menu navigasi"
              aria-expanded={mobileMenuOpen}
            >
              <div className="w-4 h-3.5 flex flex-col justify-between items-center pointer-events-none">
                <span
                  className={`h-0.5 w-full bg-cyber-amber-bright rounded-sm transition-all duration-300 ${mobileMenuOpen ? "rotate-45 translate-y-1.5" : ""
                    }`}
                />
                <span
                  className={`h-0.5 w-full bg-cyber-amber-bright rounded-sm transition-all duration-300 ${mobileMenuOpen ? "opacity-0" : ""
                    }`}
                />
                <span
                  className={`h-0.5 w-full bg-cyber-amber-bright rounded-sm transition-all duration-300 ${mobileMenuOpen ? "-rotate-45 -translate-y-1.5" : ""
                    }`}
                />
              </div>
            </button>
          </div>
        </div>
      </header>

      {/* =================================================================== */}
      {/* MOBILE DRAWER / SLIDE-OVER MENU KANAN (TIDAK ADA TOMBOL YANG HILANG)*/}
      {/* =================================================================== */}
      {mobileMenuOpen && (
        <div className="fixed inset-0 z-50 md:hidden">
          {/* Backdrop gelap transparan */}
          <div
            className="fixed inset-0 bg-black/80 backdrop-blur-sm transition-opacity"
            onClick={() => setMobileMenuOpen(false)}
            aria-hidden="true"
          />

          {/* Panel Drawer dari Kanan */}
          <div className="fixed inset-y-0 right-0 z-50 w-full max-w-xs sm:max-w-sm bg-cyber-void border-l border-cyber-border p-6 shadow-2xl flex flex-col justify-between overflow-y-auto">
            <div>
              {/* Drawer Header */}
              <div className="flex items-center justify-between border-b border-cyber-border pb-4">
                <div className="flex items-center space-x-2">
                  <span className="h-2 w-2 rounded-full bg-cyber-amber-bright animate-ping"></span>
                  <span className="font-sans text-xs font-bold tracking-wider text-cyber-amber-bright">
                    Menu Navigasi
                  </span>
                </div>
                <button
                  type="button"
                  onClick={() => setMobileMenuOpen(false)}
                  className="rounded border border-cyber-border bg-cyber-surface px-2 py-1 font-mono text-xs text-zinc-400 hover:border-cyber-amber hover:text-cyber-amber-bright transition-colors"
                >
                  ✕ CLOSE
                </button>
              </div>

              {/* Status Cluster di dalam Drawer */}
              <div className="mt-4 flex items-center justify-between rounded border border-cyber-border bg-cyber-surface/60 p-3 font-mono text-xs">
                <div className="flex items-center space-x-2">
                  <span
                    className={`h-2 w-2 rounded-full ${clusterOnline ? "bg-emerald-500" : "bg-amber-500"
                      }`}
                  />
                  <span className="text-[11px] text-zinc-300">
                    CLUSTER:{" "}
                    <strong className={clusterOnline ? "text-emerald-400" : "text-amber-400"}>
                      {clusterOnline ? "ONLINE" : "STANDBY"}
                    </strong>
                  </span>
                </div>
                <span className="text-[11px] text-zinc-400">
                  NODES: <span className="text-cyber-amber-bright font-bold">{activeNodes}</span>
                </span>
              </div>

              {/* Daftar Menu Utama */}
              <nav className="mt-6 flex flex-col space-y-2">
                <span className="font-mono text-[10px] text-zinc-500 uppercase tracking-wider mb-1">
                  MAIN SECTIONS
                </span>
                {allNavLinks.map((link) => {
                  const isActive =
                    pathname === link.href ||
                    (link.href === "/admin" && pathname.startsWith("/admin"));
                  return (
                    <Link
                      key={link.href}
                      href={link.href}
                      onClick={() => setMobileMenuOpen(false)}
                      className={`flex items-center justify-between px-3.5 py-2.5 font-mono text-xs tracking-wider rounded border transition-all ${isActive
                        ? "text-cyber-amber-bright bg-cyber-surface border-cyber-amber shadow-amber-glow-sm font-semibold"
                        : "text-zinc-300 border-cyber-border/40 hover:border-cyber-amber/60 hover:text-cyber-amber-light hover:bg-cyber-surface/40"
                        }`}
                    >
                      <span>{link.label}</span>
                      <span className="text-cyber-amber-bright text-xs">&rarr;</span>
                    </Link>
                  );
                })}
              </nav>
            </div>

            {/* Bagian Bawah Drawer: AUTH BUTTONS (LOGIN & REGISTER) */}
            <div className="mt-8 border-t border-cyber-border pt-5 space-y-3">
              <span className="block font-mono text-[10px] text-zinc-500 uppercase tracking-wider">
                PORTAL ACCESS
              </span>
              <div className="grid grid-cols-2 gap-2">
                <Link
                  href="/register"
                  onClick={() => setMobileMenuOpen(false)}
                  className="flex items-center justify-center py-2.5 font-mono text-xs font-semibold tracking-wider rounded border border-cyber-amber bg-cyber-amber text-cyber-void hover:bg-cyber-amber-bright hover:shadow-amber-glow transition-all"
                >
                  REGISTER
                </Link>

                <Link
                  href="/login"
                  onClick={() => setMobileMenuOpen(false)}
                  className={`flex items-center justify-center py-2.5 font-mono text-xs tracking-wider rounded border transition-all ${pathname === "/login"
                    ? "text-cyber-amber-bright bg-cyber-surface border-cyber-amber font-semibold"
                    : "text-zinc-200 border-cyber-border bg-cyber-surface/60 hover:border-cyber-amber hover:text-cyber-amber-bright"
                    }`}
                >
                  LOGIN
                </Link>
              </div>

              <p className="text-center font-mono text-[9px] text-zinc-500 pt-2">
                IdleScale Network • Distributed Volunteer Supercomputing
              </p>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
