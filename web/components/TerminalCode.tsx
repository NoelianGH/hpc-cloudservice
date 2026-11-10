"use client";
import React, { useState } from "react";

interface TerminalCodeProps {
  title?: string;
  code: string;
  language?: string;
}

export default function TerminalCode({
  title = "BASH // CLI EXECUTION",
  code,
  language = "bash",
}: TerminalCodeProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="relative my-3 overflow-hidden rounded border border-cyber-border bg-cyber-black font-mono text-xs shadow-2xl">
      {/* Terminal Titlebar */}
      <div className="flex items-center justify-between border-b border-cyber-border bg-cyber-surface/90 px-3 py-1.5">
        <div className="flex items-center space-x-2">
          <div className="flex space-x-1.5">
            <span className="h-2 w-2 rounded-full bg-red-500/80"></span>
            <span className="h-2 w-2 rounded-full bg-amber-500/80"></span>
            <span className="h-2 w-2 rounded-full bg-emerald-500/80"></span>
          </div>
          <span className="text-[10px] text-zinc-400 font-semibold tracking-wider">
            {title}
          </span>
        </div>
        <button
          onClick={handleCopy}
          className="flex items-center space-x-1 rounded border border-cyber-border px-2 py-0.5 text-[10px] text-zinc-300 transition-colors hover:border-cyber-amber hover:text-cyber-amber-bright active:scale-95"
        >
          {copied ? (
            <span className="text-emerald-400 font-bold">COPIED [✓]</span>
          ) : (
            <span>COPY COMMAND</span>
          )}
        </button>
      </div>

      {/* Code Area */}
      <div className="overflow-x-auto p-3 text-zinc-200">
        <pre className="text-[11px] leading-relaxed">
          <code>
            {code.split("\n").map((line, i) => (
              <div key={i} className="flex">
                <span className="mr-3 select-none text-zinc-600">$</span>
                <span className={line.startsWith("#") ? "text-zinc-500 italic" : "text-amber-200"}>
                  {line}
                </span>
              </div>
            ))}
          </code>
        </pre>
      </div>
    </div>
  );
}

