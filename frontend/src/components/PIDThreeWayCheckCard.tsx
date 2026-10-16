"use client";

import React, { useState } from "react";
import {
  AlertTriangle,
  CheckCircle,
  XCircle,
  Eye,
  Cpu,
  Database,
  Type,
  ShieldAlert,
  ChevronDown,
  ChevronUp,
  ExternalLink,
  Layers,
  Sparkles,
} from "lucide-react";
import { ApiClient } from "../services/api";

export interface ThreeWayCheckData {
  tag: string;
  symbol_type: string;
  is_isa_standard: boolean;
  isa_category?: string;
  isa_details?: string;
  symbol_probability: number;
  ocr_confidence: number;
  in_asset_register: boolean;
  symbol_prob_passed: boolean;
  ocr_conf_passed: boolean;
  asset_reg_passed: boolean;
  passed_count: number;
  decision: "3/3_CONFIRM" | "2/3_HUMAN_CHECK" | "1/3_REJECT" | string;
  decision_label: string;
  decision_color: "green" | "yellow" | "red" | string;
  requires_human_review: boolean;
  two_way_breakdown?: {
    passed_checks?: string[];
    failed_checks?: string[];
    passed_count?: number;
    summary?: string;
    diagram_ascii?: string;
    isa_compliance?: {
      is_standard: boolean;
      category: string;
      details: string;
    };
  };
  bbox?: [number, number, number, number] | null;
  cropped_image_base64?: string | null;
}

interface PIDThreeWayCheckCardProps {
  checks: ThreeWayCheckData[];
  onPreviewImage?: (url: string, filename: string) => void;
}

export function PIDThreeWayCheckCard({
  checks,
  onPreviewImage,
}: PIDThreeWayCheckCardProps) {
  const [resolvedStatus, setResolvedStatus] = useState<
    Record<string, { action: string; message: string }>
  >({});
  const [resolvingTag, setResolvingTag] = useState<string | null>(null);
  const [operatorNotes, setOperatorNotes] = useState<Record<string, string>>({});
  const [isExpanded, setIsExpanded] = useState<boolean>(true);

  if (!checks || checks.length === 0) return null;

  const humanChecksCount = checks.filter(
    (c) => c.decision === "2/3_HUMAN_CHECK" || c.requires_human_review
  ).length;

  const handleResolve = async (
    tag: string,
    action: "APPROVE_AND_REGISTER" | "RECLASSIFY" | "REJECT",
    reclassifiedType?: string
  ) => {
    setResolvingTag(tag);
    try {
      const resp = await ApiClient.verifyPIDSymbol({
        tag,
        action,
        reclassified_type: reclassifiedType,
        notes: operatorNotes[tag] || "Resolved by operator via 3-way check audit",
      });
      setResolvedStatus((prev) => ({
        ...prev,
        [tag]: {
          action,
          message: resp.message || `Action ${action} confirmed`,
        },
      }));
    } catch (err: any) {
      setResolvedStatus((prev) => ({
        ...prev,
        [tag]: {
          action: "ERROR",
          message: err?.message || "Failed to submit verification",
        },
      }));
    } finally {
      setResolvingTag(null);
    }
  };

  return (
    <div className="mt-4 rounded-xl border border-amber-500/30 bg-[var(--color-surface)] shadow-lg shadow-amber-500/5 overflow-hidden">
      {/* Top Header Bar */}
      <div className="p-3.5 bg-gradient-to-r from-amber-500/10 via-amber-500/5 to-transparent border-b border-amber-500/20 flex items-center justify-between gap-3">
        <div className="flex items-center gap-2.5 min-w-0">
          <div className="w-8 h-8 rounded-lg bg-amber-500/15 border border-amber-500/30 flex items-center justify-center text-amber-400 shrink-0">
            <Cpu className="w-4 h-4" />
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold text-[var(--color-text-primary)] tracking-wide">
                P&ID 3-Way Verification Audit
              </span>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-zinc-800 text-amber-400 border border-amber-500/30 shrink-0">
                Drawing Path: YOLO Symbol Detect
              </span>
            </div>
            <div className="text-[11px] text-[var(--color-text-muted)] mt-0.5 truncate">
              ANSI/ISA-5.1 Compliance Gate • 3 Dimensions: Symbol Probability | OCR Confidence | Asset Register
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          {humanChecksCount > 0 ? (
            <span className="text-[10px] font-mono font-semibold px-2 py-0.5 rounded-full bg-amber-500/15 text-amber-300 border border-amber-500/30 flex items-center gap-1.5 animate-pulse">
              <AlertTriangle className="w-3 h-3 text-amber-400" />
              {humanChecksCount} Human Check Required
            </span>
          ) : (
            <span className="text-[10px] font-mono font-semibold px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-300 border border-emerald-500/30 flex items-center gap-1.5">
              <CheckCircle className="w-3 h-3 text-emerald-400" />
              All Verified (3/3 Confirm)
            </span>
          )}

          <button
            type="button"
            onClick={() => setIsExpanded(!isExpanded)}
            className="p-1 rounded text-zinc-400 hover:text-zinc-200 transition-colors"
          >
            {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </button>
        </div>
      </div>

      {isExpanded && (
        <div className="p-4 flex flex-col gap-4">
          {checks.map((chk, idx) => {
            const isHumanCheck = chk.decision === "2/3_HUMAN_CHECK" || chk.requires_human_review;
            const isConfirmed = chk.decision === "3/3_CONFIRM";
            const resolution = resolvedStatus[chk.tag];

            return (
              <div
                key={`${chk.tag}-${idx}`}
                className={`p-4 rounded-xl border flex flex-col gap-3 transition-all ${
                  isHumanCheck
                    ? "bg-amber-950/15 border-amber-500/40 shadow-sm shadow-amber-500/10"
                    : isConfirmed
                    ? "bg-emerald-950/10 border-emerald-500/30"
                    : "bg-rose-950/10 border-rose-500/30"
                }`}
              >
                {/* Symbol Summary Header */}
                <div className="flex flex-wrap items-center justify-between gap-2 pb-2.5 border-b border-[var(--color-border)]">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-bold font-mono text-[var(--color-text-primary)]">
                      {chk.tag}
                    </span>
                    <span className="text-xs text-[var(--color-text-secondary)]">
                      ({chk.symbol_type.replace(/_/g, " ")})
                    </span>

                    {/* ISA Standard Badge */}
                    {chk.is_isa_standard ? (
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                        ISA 5.1 Standard
                      </span>
                    ) : (
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-amber-500/15 text-amber-300 border border-amber-500/40 flex items-center gap-1 font-semibold">
                        <ShieldAlert className="w-3 h-3 text-amber-400" />
                        Non-ISA 5.1 Refinery Hardware
                      </span>
                    )}
                  </div>

                  {/* Decision Gate Badge */}
                  <div className="flex items-center gap-2">
                    <span
                      className={`text-[11px] font-mono font-bold px-2.5 py-1 rounded-md uppercase tracking-wider flex items-center gap-1.5 ${
                        isConfirmed
                          ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/40"
                          : isHumanCheck
                          ? "bg-amber-500/25 text-amber-200 border border-amber-500/50 shadow-[0_0_12px_rgba(245,158,11,0.25)]"
                          : "bg-rose-500/20 text-rose-300 border border-rose-500/40"
                      }`}
                    >
                      {isConfirmed && <CheckCircle className="w-3.5 h-3.5 text-emerald-400" />}
                      {isHumanCheck && <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />}
                      {!isConfirmed && !isHumanCheck && <XCircle className="w-3.5 h-3.5 text-rose-400" />}
                      {chk.decision_label} ({chk.passed_count}/3)
                    </span>
                  </div>
                </div>

                {/* Two-Column Visual & 3-Way Diagram Layout */}
                <div className="grid grid-cols-1 md:grid-cols-12 gap-4 items-center">
                  {/* Left Column: YOLO Localized Cropped Symbol Preview */}
                  <div className="md:col-span-4 flex flex-col items-center justify-center p-3 rounded-lg bg-zinc-950/80 border border-zinc-800">
                    <div className="text-[10px] font-mono uppercase text-zinc-400 mb-2 flex items-center gap-1">
                      <Layers className="w-3 h-3 text-amber-400" />
                      YOLO Localized Region
                    </div>

                    {chk.cropped_image_base64 ? (
                      <div
                        onClick={() =>
                          onPreviewImage?.(
                            chk.cropped_image_base64!,
                            `P&ID Localized Symbol: ${chk.tag} (${chk.symbol_type})`
                          )
                        }
                        className="relative group cursor-pointer"
                        title="Click to view full preview"
                      >
                        <img
                          src={chk.cropped_image_base64}
                          alt={`Localized symbol for ${chk.tag}`}
                          className="w-32 h-32 object-contain rounded-lg border-2 border-amber-500/50 bg-zinc-900 p-1 group-hover:border-amber-400 transition-all shadow-md shadow-black"
                        />
                        <div className="absolute inset-0 bg-black/40 rounded-lg opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center text-white text-xs gap-1 font-semibold">
                          <Eye className="w-3.5 h-3.5" /> Inspect
                        </div>
                      </div>
                    ) : (
                      <div className="w-32 h-32 rounded-lg border border-dashed border-zinc-700 bg-zinc-900/50 flex flex-col items-center justify-center text-[10px] text-zinc-500 p-2 text-center">
                        <Eye className="w-5 h-5 mb-1 text-zinc-600" />
                        No region crop
                      </div>
                    )}

                    <div className="text-[9px] font-mono text-zinc-500 mt-2">
                      {chk.bbox ? `BBox: [${chk.bbox.join(", ")}]` : "Detected Candidate Region"}
                    </div>
                  </div>

                  {/* Right Column: The 3-Way Check Decision Diagram Component */}
                  <div className="md:col-span-8 flex flex-col gap-3">
                    {/* The 3 Input Blocks matching user's architecture */}
                    <div className="grid grid-cols-3 gap-2">
                      {/* Check 1: Symbol Probability */}
                      <div
                        className={`p-2.5 rounded-lg border flex flex-col gap-1 ${
                          chk.symbol_prob_passed
                            ? "bg-zinc-900/90 border-emerald-500/30"
                            : "bg-zinc-900/90 border-rose-500/30"
                        }`}
                      >
                        <div className="text-[10px] font-medium text-zinc-400 flex items-center gap-1 truncate">
                          <Cpu className="w-3 h-3 text-indigo-400 shrink-0" />
                          Symbol probability
                        </div>
                        <div className="flex items-baseline justify-between mt-0.5">
                          <span className="text-xs font-bold font-mono text-[var(--color-text-primary)]">
                            {(chk.symbol_probability * 100).toFixed(0)}%
                          </span>
                          <span
                            className={`text-[9px] font-mono font-bold px-1.5 py-0.5 rounded ${
                              chk.symbol_prob_passed
                                ? "bg-emerald-500/20 text-emerald-300"
                                : "bg-rose-500/20 text-rose-300"
                            }`}
                          >
                            {chk.symbol_prob_passed ? "PASS" : "FAIL"}
                          </span>
                        </div>
                      </div>

                      {/* Check 2: OCR Confidence */}
                      <div
                        className={`p-2.5 rounded-lg border flex flex-col gap-1 ${
                          chk.ocr_conf_passed
                            ? "bg-zinc-900/90 border-emerald-500/30"
                            : "bg-zinc-900/90 border-rose-500/30"
                        }`}
                      >
                        <div className="text-[10px] font-medium text-zinc-400 flex items-center gap-1 truncate">
                          <Type className="w-3 h-3 text-blue-400 shrink-0" />
                          OCR Confidence
                        </div>
                        <div className="flex items-baseline justify-between mt-0.5">
                          <span className="text-xs font-bold font-mono text-[var(--color-text-primary)]">
                            {(chk.ocr_confidence * 100).toFixed(0)}%
                          </span>
                          <span
                            className={`text-[9px] font-mono font-bold px-1.5 py-0.5 rounded ${
                              chk.ocr_conf_passed
                                ? "bg-emerald-500/20 text-emerald-300"
                                : "bg-rose-500/20 text-rose-300"
                            }`}
                          >
                            {chk.ocr_conf_passed ? "PASS" : "FAIL"}
                          </span>
                        </div>
                      </div>

                      {/* Check 3: In Asset Register */}
                      <div
                        className={`p-2.5 rounded-lg border flex flex-col gap-1 ${
                          chk.asset_reg_passed
                            ? "bg-zinc-900/90 border-emerald-500/30"
                            : "bg-zinc-900/90 border-rose-500/30"
                        }`}
                      >
                        <div className="text-[10px] font-medium text-zinc-400 flex items-center gap-1 truncate">
                          <Database className="w-3 h-3 text-amber-400 shrink-0" />
                          In asset register
                        </div>
                        <div className="flex items-baseline justify-between mt-0.5">
                          <span className="text-xs font-bold font-mono text-[var(--color-text-primary)]">
                            {chk.in_asset_register ? "Present" : "Not Found"}
                          </span>
                          <span
                            className={`text-[9px] font-mono font-bold px-1.5 py-0.5 rounded ${
                              chk.asset_reg_passed
                                ? "bg-emerald-500/20 text-emerald-300"
                                : "bg-rose-500/20 text-rose-300"
                            }`}
                          >
                            {chk.asset_reg_passed ? "PASS" : "FAIL"}
                          </span>
                        </div>
                      </div>
                    </div>

                    {/* Routing Diagram Diamond Representation */}
                    <div className="p-2.5 rounded-lg bg-zinc-950/70 border border-zinc-800 text-[11px] text-zinc-300 flex flex-col gap-1.5">
                      <div className="text-[10px] font-mono text-zinc-400 flex items-center justify-between">
                        <span>Decision Routing (3-Way Architecture):</span>
                        <span className="text-amber-400 font-semibold">{chk.decision_label}</span>
                      </div>

                      {/* Diagnostic Breakdown */}
                      <p className="text-[11px] leading-relaxed text-zinc-300">
                        {chk.two_way_breakdown?.summary || (
                          isHumanCheck
                            ? `Symbol '${chk.tag}' passed 2 of 3 checks. Visual crop localized with YOLO and presented for operator sign-off.`
                            : `All 3 dimensions verified against refinery memory.`
                        )}
                      </p>

                      {/* Passed & Failed Badges */}
                      <div className="flex flex-wrap items-center gap-1.5 pt-1">
                        {chk.two_way_breakdown?.passed_checks?.map((p, i) => (
                          <span
                            key={i}
                            className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 flex items-center gap-1"
                          >
                            <CheckCircle className="w-2.5 h-2.5" /> {p}
                          </span>
                        ))}
                        {chk.two_way_breakdown?.failed_checks?.map((f, i) => (
                          <span
                            key={i}
                            className="text-[10px] font-mono px-2 py-0.5 rounded bg-rose-500/10 text-rose-300 border border-rose-500/20 flex items-center gap-1"
                          >
                            <XCircle className="w-2.5 h-2.5" /> {f}
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>

                {/* Operator Verification Action Bar (for 2/3 Human Check) */}
                {isHumanCheck && (
                  <div className="mt-2 pt-3 border-t border-[var(--color-border)] flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
                    {resolution ? (
                      <div className="flex items-center gap-2 text-xs font-semibold text-emerald-400 bg-emerald-500/10 px-3 py-2 rounded-lg border border-emerald-500/30 w-full">
                        <CheckCircle className="w-4 h-4 text-emerald-400 shrink-0" />
                        <span>{resolution.message}</span>
                      </div>
                    ) : (
                      <>
                        <div className="text-xs text-zinc-400 flex items-center gap-1.5">
                          <AlertTriangle className="w-3.5 h-3.5 text-amber-400 shrink-0" />
                          <span>Operator Sign-Off Required for Non-Standard / 2-Way Check:</span>
                        </div>

                        <div className="flex flex-wrap items-center gap-2 shrink-0">
                          <button
                            type="button"
                            disabled={resolvingTag === chk.tag}
                            onClick={() => handleResolve(chk.tag, "APPROVE_AND_REGISTER")}
                            className="px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold transition-all shadow-md flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
                          >
                            <CheckCircle className="w-3.5 h-3.5" />
                            <span>Confirm & Add to Asset Graph</span>
                          </button>

                          <button
                            type="button"
                            disabled={resolvingTag === chk.tag}
                            onClick={() =>
                              handleResolve(
                                chk.tag,
                                "RECLASSIFY",
                                prompt(`Enter correct equipment class for ${chk.tag}:`, chk.symbol_type) || chk.symbol_type
                              )
                            }
                            className="px-2.5 py-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-xs font-medium border border-zinc-700 transition-colors cursor-pointer disabled:opacity-50"
                          >
                            Reclassify
                          </button>

                          <button
                            type="button"
                            disabled={resolvingTag === chk.tag}
                            onClick={() => handleResolve(chk.tag, "REJECT")}
                            className="px-2.5 py-1.5 rounded-lg bg-rose-950/40 hover:bg-rose-900/60 text-rose-300 text-xs font-medium border border-rose-800/40 transition-colors cursor-pointer disabled:opacity-50"
                          >
                            Reject Noise
                          </button>
                        </div>
                      </>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
