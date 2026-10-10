"use client";

import { MessageSquare, Network, UploadCloud, Activity, Terminal, UserCircle } from "lucide-react";
import { motion } from "framer-motion";

export type ViewId = "chat" | "knowledge" | "ingestion" | "overview" | "profile";

interface NavItem {
  id: ViewId;
  label: string;
  icon: typeof MessageSquare;
}

const NAV_ITEMS: NavItem[] = [
  { id: "chat", label: "Chat", icon: MessageSquare },
  { id: "knowledge", label: "Knowledge", icon: Network },
  { id: "ingestion", label: "Ingestion", icon: UploadCloud },
  { id: "overview", label: "Overview", icon: Activity },
  { id: "profile", label: "Profile", icon: UserCircle },
];

interface NavRailProps {
  activeView: ViewId;
  onViewChange: (view: ViewId) => void;
}

export function NavRail({ activeView, onViewChange }: NavRailProps) {
  return (
    <nav className="w-[72px] h-full flex flex-col items-center bg-[var(--color-surface)] border-r border-[var(--color-border)] shrink-0 py-4 gap-1 z-30">
      {/* Wordmark */}
      <div className="flex flex-col items-center gap-1.5 mb-6 px-2">
        <div className="w-9 h-9 rounded-lg bg-indigo-500/20 border border-indigo-500/50 flex items-center justify-center">
          <Terminal className="w-4.5 h-4.5 text-indigo-400" />
        </div>
        <span
          className="text-[8px] font-bold tracking-[0.15em] text-[var(--color-text-muted)] uppercase"
          style={{ fontFamily: "var(--font-mono)" }}
        >
          VIGIL
        </span>
      </div>

      {/* Nav Items */}
      <div className="flex flex-col items-center gap-1 flex-1 w-full px-2">
        {NAV_ITEMS.map((item) => {
          const isActive = activeView === item.id;
          const Icon = item.icon;

          return (
            <button
              key={item.id}
              onClick={() => onViewChange(item.id)}
              className={`relative w-full flex flex-col items-center gap-1 py-2.5 rounded-lg transition-all duration-200 group ${
                isActive
                  ? "text-indigo-400"
                  : "text-[var(--color-text-muted)] hover:text-[var(--color-text-secondary)]"
              }`}
              title={item.label}
            >
              {isActive && (
                <motion.div
                  layoutId="nav-active-bg"
                  className="absolute inset-0 rounded-lg bg-indigo-500/10 border border-indigo-500/25"
                  transition={{ type: "spring", stiffness: 350, damping: 30 }}
                />
              )}
              <Icon className="w-5 h-5 relative z-10" />
              <span
                className="text-[9px] font-semibold tracking-wide relative z-10 uppercase"
                style={{ fontFamily: "var(--font-mono)" }}
              >
                {item.label}
              </span>
            </button>
          );
        })}
      </div>
    </nav>
  );
}
