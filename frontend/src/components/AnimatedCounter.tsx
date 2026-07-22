"use client";

import { useEffect, useState } from "react";
import { motion, useSpring, useTransform } from "framer-motion";

interface AnimatedCounterProps {
  value: number;
  label: string;
}

export function AnimatedCounter({ value, label }: AnimatedCounterProps) {
  const spring = useSpring(0, { mass: 1, stiffness: 50, damping: 20 });
  const display = useTransform(spring, (current) => Math.round(current));
  
  useEffect(() => {
    spring.set(value);
  }, [value, spring]);

  return (
    <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm flex flex-col items-center justify-center">
      <motion.span className="text-3xl font-bold text-slate-800 tabular-nums">
        {display}
      </motion.span>
      <span className="text-sm font-medium text-slate-500 mt-1 uppercase tracking-wider">{label}</span>
    </div>
  );
}
