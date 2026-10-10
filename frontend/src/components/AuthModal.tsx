"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { 
  Lock, Mail, User, Shield, Briefcase, Award, 
  Layers, X, ArrowRight, CheckCircle2, AlertCircle, Loader2
} from "lucide-react";
import { ApiClient, UserInfo } from "@/services/api";

interface AuthModalProps {
  isOpen: boolean;
  canClose?: boolean;
  onClose?: () => void;
  onSuccess: (user: UserInfo) => void;
  initialMode?: "login" | "register";
}

export function AuthModal({
  isOpen,
  canClose = false,
  onClose,
  onSuccess,
  initialMode = "login",
}: AuthModalProps) {
  const [mode, setMode] = useState<"login" | "register">(initialMode);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Sign-in state
  const [loginEmail, setLoginEmail] = useState("");
  const [loginPassword, setLoginPassword] = useState("");

  // Registration state
  const [regEmail, setRegEmail] = useState("");
  const [regPassword, setRegPassword] = useState("");
  const [regName, setRegName] = useState("");
  const [regDesignation, setRegDesignation] = useState("Graduate Trainee");
  const [regSkills, setRegSkills] = useState("Heat Transfer, Process Safety, P&ID Reading");
  const [regExperience, setRegExperience] = useState<"beginner" | "intermediate" | "advanced" | "expert">("beginner");
  const [regDepth, setRegDepth] = useState<"concise" | "moderate" | "detailed">("detailed");

  const handleLoginSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!loginEmail.trim() || !loginPassword) {
      setError("Please enter both email and password.");
      return;
    }
    setError(null);
    setLoading(true);

    try {
      const res = await ApiClient.login({
        email: loginEmail.trim(),
        password: loginPassword,
      });
      onSuccess(res.user);
      if (onClose) onClose();
    } catch (err: any) {
      const msg = err?.message || "Failed to authenticate. Please check your credentials.";
      setError(msg.replace(/^API Error \d+:\s*/, ""));
    } finally {
      setLoading(false);
    }
  };

  const handleRegisterSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!regEmail.trim() || !regPassword) {
      setError("Please provide an email and password.");
      return;
    }
    setError(null);
    setLoading(true);

    const skillsArray = regSkills
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);

    try {
      const res = await ApiClient.register({
        email: regEmail.trim(),
        password: regPassword,
        name: regName.trim() || regEmail.split("@")[0],
        designation: regDesignation.trim() || "Process Engineer",
        skill_set: skillsArray,
        refinery_experience_level: regExperience,
        preferred_explanation_depth: regDepth,
      });
      onSuccess(res.user);
      if (onClose) onClose();
    } catch (err: any) {
      const msg = err?.message || "Registration failed. Please check inputs.";
      setError(msg.replace(/^API Error \d+:\s*/, ""));
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-md">
        <motion.div
          initial={{ opacity: 0, scale: 0.96, y: 14 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.96, y: 14 }}
          transition={{ type: "spring", damping: 25, stiffness: 320 }}
          className="relative w-full max-w-xl bg-[var(--color-surface)] border border-[var(--color-border)] rounded-2xl shadow-2xl overflow-hidden flex flex-col"
        >
          {/* Header Bar */}
          <div className="flex items-center justify-between px-6 py-4 border-b border-[var(--color-border)] bg-[var(--color-surface-elevated)]">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-indigo-500/15 border border-indigo-500/40 flex items-center justify-center">
                <Shield className="w-4 h-4 text-indigo-400" />
              </div>
              <div>
                <h3 className="text-sm font-semibold text-[var(--color-text-primary)] tracking-wide">
                  VigilOps Authentication & Persona Access
                </h3>
                <p className="text-[11px] text-[var(--color-text-muted)] font-mono">
                  Industrial Intelligence Platform v3.0
                </p>
              </div>
            </div>

            {canClose && onClose && (
              <button
                type="button"
                onClick={onClose}
                className="p-1.5 rounded-lg text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)] hover:bg-[var(--color-surface-hover)] transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            )}
          </div>

          {/* Mode Switch Tabs */}
          <div className="flex border-b border-[var(--color-border)] bg-[var(--color-surface)]">
            <button
              type="button"
              onClick={() => {
                setMode("login");
                setError(null);
              }}
              className={`flex-1 py-3 text-xs font-semibold tracking-wider uppercase transition-colors border-b-2 ${
                mode === "login"
                  ? "border-indigo-500 text-indigo-400 bg-indigo-500/5"
                  : "border-transparent text-[var(--color-text-muted)] hover:text-[var(--color-text-secondary)]"
              }`}
            >
              Sign In
            </button>
            <button
              type="button"
              onClick={() => {
                setMode("register");
                setError(null);
              }}
              className={`flex-1 py-3 text-xs font-semibold tracking-wider uppercase transition-colors border-b-2 ${
                mode === "register"
                  ? "border-indigo-500 text-indigo-400 bg-indigo-500/5"
                  : "border-transparent text-[var(--color-text-muted)] hover:text-[var(--color-text-secondary)]"
              }`}
            >
              Register Persona Profile
            </button>
          </div>

          {/* Error Banner */}
          {error && (
            <div className="mx-6 mt-4 p-3 rounded-lg bg-rose-500/10 border border-rose-500/30 flex items-start gap-2.5 text-xs text-rose-300">
              <AlertCircle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          {/* Modal Body */}
          <div className="p-6 overflow-y-auto max-h-[75vh]">
            {mode === "login" ? (
              <form onSubmit={handleLoginSubmit} className="space-y-4">
                <div className="space-y-1.5">
                  <label className="text-xs font-medium text-[var(--color-text-secondary)] flex items-center gap-1.5">
                    <Mail className="w-3.5 h-3.5 text-indigo-400" /> Operator Email
                  </label>
                  <input
                    type="email"
                    required
                    value={loginEmail}
                    onChange={(e) => setLoginEmail(e.target.value)}
                    placeholder="alex.chen@refinery.internal"
                    className="w-full px-3.5 py-2.5 rounded-lg bg-[var(--color-surface-elevated)] border border-[var(--color-border)] text-sm text-[var(--color-text-primary)] placeholder-[var(--color-text-muted)] focus:outline-none focus:border-indigo-500 transition-colors"
                  />
                </div>

                <div className="space-y-1.5">
                  <label className="text-xs font-medium text-[var(--color-text-secondary)] flex items-center gap-1.5">
                    <Lock className="w-3.5 h-3.5 text-indigo-400" /> Password
                  </label>
                  <input
                    type="password"
                    required
                    value={loginPassword}
                    onChange={(e) => setLoginPassword(e.target.value)}
                    placeholder="••••••••••••"
                    className="w-full px-3.5 py-2.5 rounded-lg bg-[var(--color-surface-elevated)] border border-[var(--color-border)] text-sm text-[var(--color-text-primary)] placeholder-[var(--color-text-muted)] focus:outline-none focus:border-indigo-500 transition-colors"
                  />
                </div>

                <div className="pt-2">
                  <button
                    type="submit"
                    disabled={loading}
                    className="w-full py-2.5 px-4 rounded-xl font-medium text-sm bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white flex items-center justify-center gap-2 shadow-lg shadow-indigo-600/20 transition-all cursor-pointer"
                  >
                    {loading ? (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin" /> Authenticating...
                      </>
                    ) : (
                      <>
                        Sign In to Workspace <ArrowRight className="w-4 h-4" />
                      </>
                    )}
                  </button>
                </div>

                <p className="text-[11px] text-center text-[var(--color-text-muted)] pt-2">
                  New refinery operator or engineer?{" "}
                  <button
                    type="button"
                    onClick={() => {
                      setMode("register");
                      setError(null);
                    }}
                    className="text-indigo-400 hover:underline cursor-pointer"
                  >
                    Register your profile
                  </button>
                </p>
              </form>
            ) : (
              <form onSubmit={handleRegisterSubmit} className="space-y-4">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="space-y-1.5">
                    <label className="text-xs font-medium text-[var(--color-text-secondary)] flex items-center gap-1.5">
                      <Mail className="w-3.5 h-3.5 text-indigo-400" /> Work Email
                    </label>
                    <input
                      type="email"
                      required
                      value={regEmail}
                      onChange={(e) => setRegEmail(e.target.value)}
                      placeholder="engineer@plant.internal"
                      className="w-full px-3 py-2 rounded-lg bg-[var(--color-surface-elevated)] border border-[var(--color-border)] text-xs text-[var(--color-text-primary)] placeholder-[var(--color-text-muted)] focus:outline-none focus:border-indigo-500 transition-colors"
                    />
                  </div>

                  <div className="space-y-1.5">
                    <label className="text-xs font-medium text-[var(--color-text-secondary)] flex items-center gap-1.5">
                      <Lock className="w-3.5 h-3.5 text-indigo-400" /> Password
                    </label>
                    <input
                      type="password"
                      required
                      value={regPassword}
                      onChange={(e) => setRegPassword(e.target.value)}
                      placeholder="••••••••••••"
                      className="w-full px-3 py-2 rounded-lg bg-[var(--color-surface-elevated)] border border-[var(--color-border)] text-xs text-[var(--color-text-primary)] placeholder-[var(--color-text-muted)] focus:outline-none focus:border-indigo-500 transition-colors"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="space-y-1.5">
                    <label className="text-xs font-medium text-[var(--color-text-secondary)] flex items-center gap-1.5">
                      <User className="w-3.5 h-3.5 text-indigo-400" /> Operator Name
                    </label>
                    <input
                      type="text"
                      value={regName}
                      onChange={(e) => setRegName(e.target.value)}
                      placeholder="e.g. Alex Chen"
                      className="w-full px-3 py-2 rounded-lg bg-[var(--color-surface-elevated)] border border-[var(--color-border)] text-xs text-[var(--color-text-primary)] placeholder-[var(--color-text-muted)] focus:outline-none focus:border-indigo-500 transition-colors"
                    />
                  </div>

                  <div className="space-y-1.5">
                    <label className="text-xs font-medium text-[var(--color-text-secondary)] flex items-center gap-1.5">
                      <Briefcase className="w-3.5 h-3.5 text-indigo-400" /> Plant Designation
                    </label>
                    <input
                      type="text"
                      value={regDesignation}
                      onChange={(e) => setRegDesignation(e.target.value)}
                      placeholder="e.g. Graduate Trainee or Lead Safety Eng"
                      className="w-full px-3 py-2 rounded-lg bg-[var(--color-surface-elevated)] border border-[var(--color-border)] text-xs text-[var(--color-text-primary)] placeholder-[var(--color-text-muted)] focus:outline-none focus:border-indigo-500 transition-colors"
                    />
                  </div>
                </div>

                <div className="space-y-1.5">
                  <label className="text-xs font-medium text-[var(--color-text-secondary)] flex items-center gap-1.5">
                    <Award className="w-3.5 h-3.5 text-indigo-400" /> Refinery Experience Level
                  </label>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                    {(["beginner", "intermediate", "advanced", "expert"] as const).map((lvl) => (
                      <button
                        key={lvl}
                        type="button"
                        onClick={() => setRegExperience(lvl)}
                        className={`px-2.5 py-2 rounded-lg border text-xs font-medium capitalize text-center transition-all cursor-pointer ${
                          regExperience === lvl
                            ? "bg-indigo-500/20 border-indigo-500 text-indigo-300"
                            : "bg-[var(--color-surface-elevated)] border-[var(--color-border)] text-[var(--color-text-muted)] hover:border-slate-700"
                        }`}
                      >
                        {lvl}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="space-y-1.5">
                  <label className="text-xs font-medium text-[var(--color-text-secondary)] flex items-center gap-1.5">
                    <Layers className="w-3.5 h-3.5 text-indigo-400" /> Explanation Depth Preference
                  </label>
                  <div className="grid grid-cols-3 gap-2">
                    {(["concise", "moderate", "detailed"] as const).map((dp) => (
                      <button
                        key={dp}
                        type="button"
                        onClick={() => setRegDepth(dp)}
                        className={`px-2.5 py-2 rounded-lg border text-xs font-medium capitalize text-center transition-all cursor-pointer ${
                          regDepth === dp
                            ? "bg-indigo-500/20 border-indigo-500 text-indigo-300"
                            : "bg-[var(--color-surface-elevated)] border-[var(--color-border)] text-[var(--color-text-muted)] hover:border-slate-700"
                        }`}
                      >
                        {dp}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="space-y-1.5">
                  <label className="text-xs font-medium text-[var(--color-text-secondary)]">
                    Skill Set Tags (Comma separated)
                  </label>
                  <input
                    type="text"
                    value={regSkills}
                    onChange={(e) => setRegSkills(e.target.value)}
                    placeholder="P&ID Reading, HazMat, Heat Exchangers"
                    className="w-full px-3 py-2 rounded-lg bg-[var(--color-surface-elevated)] border border-[var(--color-border)] text-xs text-[var(--color-text-primary)] placeholder-[var(--color-text-muted)] focus:outline-none focus:border-indigo-500 transition-colors"
                  />
                </div>

                <div className="pt-2">
                  <button
                    type="submit"
                    disabled={loading}
                    className="w-full py-2.5 px-4 rounded-xl font-medium text-sm bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white flex items-center justify-center gap-2 shadow-lg shadow-indigo-600/20 transition-all cursor-pointer"
                  >
                    {loading ? (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin" /> Creating Profile...
                      </>
                    ) : (
                      <>
                        Register & Save Persona <CheckCircle2 className="w-4 h-4" />
                      </>
                    )}
                  </button>
                </div>
              </form>
            )}
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
}
