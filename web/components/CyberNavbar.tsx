"use client";
import React, { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";

export default function CyberNavbar() {
  const pathname = usePathname();
  const [clusterOnline, setClusterOnline] = useState<boolean | null>(null);
  const [activeNodes, setActiveNodes] = useState<number>(0);

  useEffect(() => {
    fetch("/api/stats")
      .then((res) => res.json())
      .then((data) => {
        setClusterOnline(data.online ?? true);
        setActiveNodes(data.workers?.length || 0);
      })
      .catch(() => setClusterOnline(false));
  }, []);

  const navLinks = [
    { href: "/", label: "OVERVIEW" },
    { href: "/register", label: "NODE REGISTRATION" },
    { href: "/login", label: "SIGN IN" },
    { href: "/dashboard", label: "COMMAND CENTER" },
  ];

  return (
    <header className="sticky top-0 z-50 border-b border-cyber-border bg-cyber-void/85 backdrop-blur-md">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3 sm:px-6 lg:px-8">
        {/* Brand / Logo */}
        <Link href="/" className="group flex items-center space-x-3">
          <div className="relative flex h-9 w-9 items-center justify-center rounded border border-cyber-amber bg-cyber-surface shadow-amber-glow-sm transition-all group-hover:shadow-amber-glow">
            <span className="font-mono text-sm font-bold text-cyber-amber-bright">HPC</span>
            <div className="absolute -top-1 -right-1 h-2 w-2 rounded-full bg-cyber-amber-bright animate-ping opacity-75" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <span className="font-mono text-sm font-bold tracking-widest text-gray-100 group-hover:text-cyber-amber-bright transition-colors">
                HPC // CLOUD
              </span>
              <span className="rounded bg-cyber-amber-darkest/80 px-1.5 py-0.5 font-mono text-[10px] text-cyber-amber-bright border border-cyber-amber-deep">
                v2.4
              </span>
            </div>
            <p className="font-mono text-[10px] text-zinc-500">DISTRIBUTED VOLUNTEER COMPUTING</p>
          </div>
        </Link>

        {/* Navigation Links */}
        <nav className="hidden md:flex items-center space-x-1 lg:space-x-2">
          {navLinks.map((link) => {
            const isActive = pathname === link.href;
            return (
              <Link
                key={link.href}
                href={link.href}
                className={`relative px-3.5 py-1.5 font-mono text-xs tracking-wider transition-all rounded ${
                  isActive
                    ? "text-cyber-amber-bright bg-cyber-surface border border-cyber-amber/60 shadow-amber-glow-sm"
                    : "text-zinc-400 hover:text-cyber-amber-light hover:bg-cyber-surface/60"
                }`}
              >
                {isActive && (
                  <span className="absolute left-1 top-1/2 -translate-y-1/2 text-cyber-amber-light font-bold">
                    &gt;
                  </span>
                )}
                <span className={isActive ? "ml-2" : ""}>{link.label}</span>
              </Link>
            );
          })}
        </nav>

        {/* Telemetry Status Badge */}
        <div className="flex items-center space-x-3">
          <div className="hidden sm:flex items-center space-x-2 rounded border border-cyber-border bg-cyber-surface/80 px-2.5 py-1 font-mono text-xs">
            <span className="relative flex h-2 w-2">
              <span
                className={`absolute inline-flex h-full w-full rounded-full opacity-75 animate-ping ${
                  clusterOnline ? "bg-emerald-400" : "bg-amber-400"
                }`}
              />
              <span
                className={`relative inline-flex h-2 w-2 rounded-full ${
                  clusterOnline ? "bg-emerald-500" : "bg-amber-500"
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

          <Link
            href="/register"
            className="flex items-center space-x-1.5 rounded border border-cyber-amber bg-cyber-amber px-3.5 py-1.5 font-mono text-xs font-semibold text-cyber-void transition-all hover:bg-cyber-amber-bright hover:shadow-amber-glow"
          >
            <span>JOIN CLUSTER</span>
            <span>&rarr;</span>
          </Link>
        </div>
      </div>
    </header>
  );
}
