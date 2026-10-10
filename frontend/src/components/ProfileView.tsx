"use client";

import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { 
  User, Briefcase, Award, Layers, Tag, Plus, X, 
  CheckCircle2, AlertCircle, Loader2, RefreshCw, Sparkles, Shield
} from "lucide-react";
import { ApiClient, UserProfileInfo, UserInfo } from "@/services/api";

interface ProfileViewProps {
  currentUser: UserInfo | null;
  onProfileUpdated?: (updated: UserProfileInfo) => void;
}

const COMMON_SKILLS = [
  "Heat Exchangers",
  "Distillation Columns",
  "Centrifugal Pumps",
  "Control Valves",
  "Process Safety Management (PSM)",
  "HazMat Protocols",
  "Lockout / Tagout (LOTO)",
  "P&ID Verification",
  "Root Cause Failure Analysis",
];

export function ProfileView({ currentUser, onProfileUpdated }: ProfileViewProps) {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Form State
  const [name, setName] = useState("");
  const [designation, setDesignation] = useState("");
  const [skills, setSkills] = useState<string[]>([]);
  const [newSkillInput, setNewSkillInput] = useState("");
  const [experienceLevel, setExperienceLevel] = useState<"beginner" | "intermediate" | "advanced" | "expert">("beginner");
  const [explanationDepth, setExplanationDepth] = useState<"concise" | "moderate" | "detailed">("detailed");
  const [showPromptPreview, setShowPromptPreview] = useState(false);

  useEffect(() => {
    loadProfile();
  }, []);

  const loadProfile = async () => {
    setLoading(true);
    setError(null);
    try {
      const p = await ApiClient.getProfile();
      setName(p.name || "");
      setDesignation(p.designation || "");
      setSkills(Array.isArray(p.skill_set) ? p.skill_set : []);
      setExperienceLevel(p.refinery_experience_level || "beginner");
      setExplanationDepth(p.preferred_explanation_depth || "detailed");
    } catch (err: any) {
      console.error("Failed to load user profile:", err);
      setError(err?.message || "Failed to load user profile from server.");
    } finally {
      setLoading(false);
    }
  };

  const handleAddSkill = (skillToAdd?: string) => {
    const target = (skillToAdd || newSkillInput).trim();
    if (!target) return;
    if (!skills.includes(target)) {
      setSkills(prev => [...prev, target]);
    }
    if (!skillToAdd) {
      setNewSkillInput("");
    }
  };

  const handleRemoveSkill = (skillToRemove: string) => {
    setSkills(prev => prev.filter(s => s !== skillToRemove));
  };

  const handleKeyDownSkill = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      e.preventDefault();
      handleAddSkill();
    }
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError(null);
    setSuccessMsg(null);

    try {
      const updated = await ApiClient.updateProfile({
        name: name.trim() || "Operator",
        designation: designation.trim() || "Plant Engineer",
        skill_set: skills,
        refinery_experience_level: experienceLevel,
        preferred_explanation_depth: explanationDepth,
      });

      setSuccessMsg("Persona profile updated successfully. Next AI queries will adopt this cognitive stance.");
      if (onProfileUpdated) {
        onProfileUpdated(updated);
      }
    } catch (err: any) {
      console.error("Failed to save profile:", err);
      setError(err?.message || "Failed to save profile updates.");
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex-1 h-full flex flex-col items-center justify-center bg-[var(--color-surface)] gap-3">
        <Loader2 className="w-6 h-6 animate-spin text-indigo-400" />
        <span className="text-xs font-mono text-[var(--color-text-muted)] tracking-wider uppercase">
          Loading Persona Configuration...
        </span>
      </div>
    );
  }

  return (
    <div className="flex-1 h-full flex flex-col bg-[var(--color-surface)] overflow-hidden">
      {/* View Header */}
      <div className="h-14 border-b border-[var(--color-border)] flex items-center justify-between px-6 shrink-0 bg-[var(--color-surface-elevated)]/50">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-indigo-500/15 border border-indigo-500/40 flex items-center justify-center">
            <User className="w-4 h-4 text-indigo-400" />
          </div>
          <div>
            <h2 className="text-sm font-bold tracking-wide text-[var(--color-text-primary)] uppercase">
              Operator Profile & Cognitive Persona
            </h2>
            <p className="text-[11px] text-[var(--color-text-muted)] font-mono">
              Customizes AI explanation depth, vocabulary density, and diagnostic reasoning
            </p>
          </div>
        </div>

        <button
          onClick={loadProfile}
          disabled={loading || saving}
          className="p-1.5 rounded-lg text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)] hover:bg-[var(--color-surface-hover)] transition-colors cursor-pointer"
          title="Reload profile from server"
        >
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>

      {/* Main Content Form */}
      <div className="flex-1 overflow-y-auto p-6 max-w-5xl mx-auto w-full space-y-6">
        {/* Status Alerts */}
        <AnimatePresence>
          {successMsg && (
            <motion.div
              initial={{ opacity: 0, y: -8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              className="p-3.5 rounded-xl bg-emerald-500/10 border border-emerald-500/30 flex items-center gap-3 text-xs text-emerald-300"
            >
              <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
              <span>{successMsg}</span>
            </motion.div>
          )}

          {error && (
            <motion.div
              initial={{ opacity: 0, y: -8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              className="p-3.5 rounded-xl bg-rose-500/10 border border-rose-500/30 flex items-center gap-3 text-xs text-rose-300"
            >
              <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />
              <span>{error}</span>
            </motion.div>
          )}
        </AnimatePresence>

        <form onSubmit={handleSave} className="space-y-6">
          {/* Section 1: Identity & Plant Role */}
          <div className="bg-[var(--color-surface-elevated)] border border-[var(--color-border)] rounded-2xl p-5 space-y-4">
            <div className="flex items-center gap-2 border-b border-[var(--color-border)] pb-3">
              <Briefcase className="w-4 h-4 text-indigo-400" />
              <h3 className="text-xs font-semibold text-[var(--color-text-primary)] tracking-wide uppercase">
                Plant Role & Identification
              </h3>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="space-y-1.5">
                <label className="text-xs font-medium text-[var(--color-text-secondary)]">
                  Full Name
                </label>
                <input
                  type="text"
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g. Alex Chen"
                  className="w-full px-3.5 py-2.5 rounded-xl bg-[var(--color-surface)] border border-[var(--color-border)] text-sm text-[var(--color-text-primary)] placeholder-[var(--color-text-muted)] focus:outline-none focus:border-indigo-500 transition-colors"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-medium text-[var(--color-text-secondary)]">
                  Plant Designation
                </label>
                <input
                  type="text"
                  required
                  value={designation}
                  onChange={(e) => setDesignation(e.target.value)}
                  placeholder="e.g. Graduate Trainee / Senior Safety Engineer"
                  className="w-full px-3.5 py-2.5 rounded-xl bg-[var(--color-surface)] border border-[var(--color-border)] text-sm text-[var(--color-text-primary)] placeholder-[var(--color-text-muted)] focus:outline-none focus:border-indigo-500 transition-colors"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-medium text-[var(--color-text-secondary)]">
                  Account Email
                </label>
                <input
                  type="text"
                  readOnly
                  disabled
                  value={currentUser?.email || "Authenticated Operator"}
                  className="w-full px-3.5 py-2.5 rounded-xl bg-[var(--color-surface)]/50 border border-[var(--color-border)] text-sm text-[var(--color-text-muted)] cursor-not-allowed font-mono text-xs"
                />
              </div>
            </div>
          </div>

          {/* Section 2: Refinery Experience Level */}
          <div className="bg-[var(--color-surface-elevated)] border border-[var(--color-border)] rounded-2xl p-5 space-y-4">
            <div className="flex items-center justify-between border-b border-[var(--color-border)] pb-3">
              <div className="flex items-center gap-2">
                <Award className="w-4 h-4 text-indigo-400" />
                <h3 className="text-xs font-semibold text-[var(--color-text-primary)] tracking-wide uppercase">
                  Refinery Experience Level
                </h3>
              </div>
              <span className="text-[10px] font-mono text-indigo-400 uppercase tracking-wider">
                Selects AI Terminology Density
              </span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
              {[
                {
                  id: "beginner",
                  title: "Beginner / Trainee",
                  desc: "Foundational process physics, explicit definitions for all technical acronyms (DP, P&ID, LOTO), sequential step-by-step diagnostic reasoning.",
                },
                {
                  id: "intermediate",
                  title: "Intermediate",
                  desc: "Standard plant operational terminology without remedial definitions; structured unit operation workflows.",
                },
                {
                  id: "advanced",
                  title: "Advanced",
                  desc: "Detailed process parameters, control loop dynamics, thermodynamic constraints, and unit-specific tolerances.",
                },
                {
                  id: "expert",
                  title: "Senior Expert",
                  desc: "High-density technical analysis, specialized diagnostic metrics, direct root cause investigations, zero remedial explanations.",
                },
              ].map((tier) => {
                const isSelected = experienceLevel === tier.id;
                return (
                  <div
                    key={tier.id}
                    onClick={() => setExperienceLevel(tier.id as any)}
                    className={`p-4 rounded-xl border transition-all cursor-pointer flex flex-col justify-between ${
                      isSelected
                        ? "bg-indigo-500/15 border-indigo-500 text-[var(--color-text-primary)] shadow-lg shadow-indigo-500/10"
                        : "bg-[var(--color-surface)] border-[var(--color-border)] text-[var(--color-text-secondary)] hover:border-slate-700"
                    }`}
                  >
                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-xs font-semibold">{tier.title}</span>
                        <div
                          className={`w-3.5 h-3.5 rounded-full border flex items-center justify-center ${
                            isSelected
                              ? "border-indigo-400 bg-indigo-500"
                              : "border-[var(--color-border)]"
                          }`}
                        >
                          {isSelected && <div className="w-1.5 h-1.5 rounded-full bg-white" />}
                        </div>
                      </div>
                      <p className="text-[11px] leading-relaxed text-[var(--color-text-muted)]">
                        {tier.desc}
                      </p>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Section 3: Explanation Depth Preference */}
          <div className="bg-[var(--color-surface-elevated)] border border-[var(--color-border)] rounded-2xl p-5 space-y-4">
            <div className="flex items-center justify-between border-b border-[var(--color-border)] pb-3">
              <div className="flex items-center gap-2">
                <Layers className="w-4 h-4 text-indigo-400" />
                <h3 className="text-xs font-semibold text-[var(--color-text-primary)] tracking-wide uppercase">
                  Preferred Explanation Depth
                </h3>
              </div>
              <span className="text-[10px] font-mono text-indigo-400 uppercase tracking-wider">
                Controls Output Verbosity
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              {[
                {
                  id: "concise",
                  title: "Concise & Direct",
                  desc: "Immediate summary, primary operational variables, and numbered action checklist. Minimum conversational fluff.",
                },
                {
                  id: "moderate",
                  title: "Moderate & Balanced",
                  desc: "Balanced operational context, key physical mechanisms, and standard diagnostic guidance.",
                },
                {
                  id: "detailed",
                  title: "Detailed & Comprehensive",
                  desc: "Exhaustive diagnostic workflow, mechanical breakdown, inspection points, and full engineering correlations.",
                },
              ].map((depth) => {
                const isSelected = explanationDepth === depth.id;
                return (
                  <div
                    key={depth.id}
                    onClick={() => setExplanationDepth(depth.id as any)}
                    className={`p-4 rounded-xl border transition-all cursor-pointer flex flex-col justify-between ${
                      isSelected
                        ? "bg-indigo-500/15 border-indigo-500 text-[var(--color-text-primary)] shadow-lg shadow-indigo-500/10"
                        : "bg-[var(--color-surface)] border-[var(--color-border)] text-[var(--color-text-secondary)] hover:border-slate-700"
                    }`}
                  >
                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-xs font-semibold">{depth.title}</span>
                        <div
                          className={`w-3.5 h-3.5 rounded-full border flex items-center justify-center ${
                            isSelected
                              ? "border-indigo-400 bg-indigo-500"
                              : "border-[var(--color-border)]"
                          }`}
                        >
                          {isSelected && <div className="w-1.5 h-1.5 rounded-full bg-white" />}
                        </div>
                      </div>
                      <p className="text-[11px] leading-relaxed text-[var(--color-text-muted)]">
                        {depth.desc}
                      </p>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Section 4: Domain Skill Set Tags */}
          <div className="bg-[var(--color-surface-elevated)] border border-[var(--color-border)] rounded-2xl p-5 space-y-4">
            <div className="flex items-center justify-between border-b border-[var(--color-border)] pb-3">
              <div className="flex items-center gap-2">
                <Tag className="w-4 h-4 text-indigo-400" />
                <h3 className="text-xs font-semibold text-[var(--color-text-primary)] tracking-wide uppercase">
                  Industrial Domain Skill Set
                </h3>
              </div>
              <span className="text-[10px] font-mono text-[var(--color-text-muted)]">
                {skills.length} skills active
              </span>
            </div>

            {/* Current Active Tags */}
            <div className="flex flex-wrap gap-2 min-h-[42px] p-3 rounded-xl bg-[var(--color-surface)] border border-[var(--color-border)]">
              {skills.length === 0 ? (
                <span className="text-xs text-[var(--color-text-muted)] italic self-center">
                  No specialized skills tagged. The AI will assume general refinery operations background.
                </span>
              ) : (
                skills.map((skill) => (
                  <span
                    key={skill}
                    className="inline-flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-medium bg-indigo-500/15 border border-indigo-500/30 text-indigo-300"
                  >
                    {skill}
                    <button
                      type="button"
                      onClick={() => handleRemoveSkill(skill)}
                      className="p-0.5 rounded hover:bg-indigo-500/30 hover:text-white transition-colors cursor-pointer"
                    >
                      <X className="w-3 h-3" />
                    </button>
                  </span>
                ))
              )}
            </div>

            {/* Input to add custom skill */}
            <div className="flex gap-2">
              <input
                type="text"
                value={newSkillInput}
                onChange={(e) => setNewSkillInput(e.target.value)}
                onKeyDown={handleKeyDownSkill}
                placeholder="Type custom skill tag (e.g. Boilers, Flare Systems, Centrifugal Compressors)..."
                className="flex-1 px-3.5 py-2 rounded-xl bg-[var(--color-surface)] border border-[var(--color-border)] text-xs text-[var(--color-text-primary)] placeholder-[var(--color-text-muted)] focus:outline-none focus:border-indigo-500 transition-colors"
              />
              <button
                type="button"
                onClick={() => handleAddSkill()}
                className="px-4 py-2 rounded-xl text-xs font-semibold bg-indigo-600 hover:bg-indigo-500 text-white flex items-center gap-1.5 transition-colors cursor-pointer"
              >
                <Plus className="w-3.5 h-3.5" /> Add
              </button>
            </div>

            {/* Quick Suggestion Chips */}
            <div className="space-y-1.5 pt-1">
              <span className="text-[10px] font-mono text-[var(--color-text-muted)] uppercase tracking-wider">
                Common Refinery Skill Templates:
              </span>
              <div className="flex flex-wrap gap-1.5">
                {COMMON_SKILLS.map((cs) => {
                  const alreadyAdded = skills.includes(cs);
                  return (
                    <button
                      key={cs}
                      type="button"
                      disabled={alreadyAdded}
                      onClick={() => handleAddSkill(cs)}
                      className={`text-[11px] px-2.5 py-1 rounded-lg border transition-all cursor-pointer ${
                        alreadyAdded
                          ? "bg-[var(--color-surface)] border-[var(--color-border)] text-[var(--color-text-muted)] opacity-50 cursor-not-allowed"
                          : "bg-[var(--color-surface)] border-[var(--color-border)] text-[var(--color-text-secondary)] hover:border-indigo-500/50 hover:text-indigo-300"
                      }`}
                    >
                      + {cs}
                    </button>
                  );
                })}
              </div>
            </div>
          </div>

          {/* Section 5: Transparency Directives Preview Toggle */}
          <div className="border border-[var(--color-border)] rounded-2xl bg-[var(--color-surface-elevated)] p-4">
            <button
              type="button"
              onClick={() => setShowPromptPreview(!showPromptPreview)}
              className="w-full flex items-center justify-between text-xs text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] transition-colors cursor-pointer"
            >
              <div className="flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-amber-400" />
                <span className="font-semibold uppercase tracking-wider font-mono text-[11px]">
                  Inspect Live AI Directive Construction
                </span>
              </div>
              <span className="text-[10px] text-indigo-400 font-mono">
                {showPromptPreview ? "Hide Preview [-]" : "Show Preview [+]"}
              </span>
            </button>

            {showPromptPreview && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                exit={{ opacity: 0, height: 0 }}
                className="mt-3 pt-3 border-t border-[var(--color-border)] text-xs text-[var(--color-text-secondary)] font-mono leading-relaxed bg-[var(--color-surface)] p-3 rounded-xl border border-[var(--color-border)] whitespace-pre-wrap"
              >
{`[AUTHENTICATED USER COGNITIVE PERSONA DIRECTIVES]
Operator Name: ${name || "Operator"}
Plant Designation: ${designation || "Engineer"}
Refinery Experience Level: ${experienceLevel.toUpperCase()}
Preferred Explanation Depth: ${explanationDepth.toUpperCase()}
Recognized Domain Skills: ${skills.length > 0 ? skills.join(", ") : "General Engineering"}

DIRECTIVE CONSTRAINTS:
- ${
  experienceLevel === "beginner"
    ? "Explain foundational mechanisms and define all acronyms (e.g., DP, P&ID, fouling)."
    : experienceLevel === "expert"
    ? "Provide concise, high-density technical analysis with zero remedial definitions."
    : "Use standard industrial terminology without exhaustive definitions."
}
- ${
  explanationDepth === "concise"
    ? "Deliver a direct summary and immediate checklist."
    : explanationDepth === "detailed"
    ? "Provide a comprehensive mechanical and diagnostic root-cause breakdown."
    : "Provide a balanced diagnostic overview."
}
- MANDATORY SAFETY INVARIANT: Never omit Lockout/Tagout (LOTO), PPE, or high-pressure hazard warnings under any circumstance.`}
              </motion.div>
            )}
          </div>

          {/* Save Action Button Bar */}
          <div className="flex items-center justify-between pt-2">
            <div className="flex items-center gap-2 text-xs text-[var(--color-text-muted)]">
              <Shield className="w-3.5 h-3.5 text-indigo-400" />
              <span>Persona changes are saved in PostgreSQL and applied live on your next query.</span>
            </div>

            <button
              type="submit"
              disabled={saving}
              className="py-2.5 px-6 rounded-xl font-medium text-sm bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white flex items-center justify-center gap-2 shadow-lg shadow-indigo-600/25 transition-all cursor-pointer"
            >
              {saving ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" /> Saving Changes...
                </>
              ) : (
                <>
                  Save Persona Profile <CheckCircle2 className="w-4 h-4" />
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
