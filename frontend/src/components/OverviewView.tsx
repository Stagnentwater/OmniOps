"use client";

import { SystemStatusPanel } from "@/components/SystemStatusPanel";

interface OverviewViewProps {
  refreshToken: number;
}

export function OverviewView({ refreshToken }: OverviewViewProps) {
  return (
    <div className="flex-1 h-full flex flex-col bg-[var(--color-surface)] overflow-hidden">
      {/* View Header */}
      <div className="h-14 border-b border-[var(--color-border)] flex items-center px-6 gap-3 shrink-0 bg-[var(--color-surface-elevated)]/50">
        <span className="font-bold text-sm tracking-wide text-[var(--color-text-primary)]">
          OPERATIONAL OVERVIEW
        </span>
        <span
          className="px-2 py-0.5 rounded text-[10px] font-mono font-medium bg-[var(--color-surface-elevated)] border border-[var(--color-border)] text-[var(--color-text-muted)] ml-auto"
        >
          SYSTEM STATUS
        </span>
      </div>

      {/* Full-width SystemStatusPanel content */}
      <div className="flex-1 overflow-hidden">
        <SystemStatusPanel refreshToken={refreshToken} />
      </div>
    </div>
  );
}
