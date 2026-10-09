/**
 * TrendEdge Frontend - Signal Badges
 *
 * Small pills for engine signals (BUY/SELL/HOLD) and multi-engine consensus.
 */

import type { Consensus, EngineSignal } from "@/lib/api";
import { cn } from "@/lib/utils";

const SIGNAL_STYLES: Record<EngineSignal, string> = {
  BUY: "bg-green-500/15 text-green-400 border-green-500/30",
  SELL: "bg-red-500/15 text-red-400 border-red-500/30",
  HOLD: "bg-gray-500/15 text-gray-400 border-gray-500/30",
};

const CONSENSUS_STYLES: Record<Consensus, string> = {
  BULLISH: "bg-green-500/15 text-green-400 border-green-500/40",
  BEARISH: "bg-red-500/15 text-red-400 border-red-500/40",
  MIXED: "bg-amber-500/15 text-amber-400 border-amber-500/40",
  NEUTRAL: "bg-gray-500/15 text-gray-400 border-gray-500/40",
};

export function SignalPill({ signal }: { signal: EngineSignal | null | undefined }) {
  if (!signal) return <span className="text-xs text-gray-600">—</span>;
  return (
    <span
      className={cn(
        "inline-block px-2 py-0.5 rounded text-[10px] font-bold tracking-wide border",
        SIGNAL_STYLES[signal] ?? SIGNAL_STYLES.HOLD
      )}
    >
      {signal}
    </span>
  );
}

export function ConsensusBadge({
  consensus,
  size = "sm",
}: {
  consensus: Consensus;
  size?: "sm" | "lg";
}) {
  return (
    <span
      className={cn(
        "inline-block rounded-full font-bold tracking-wide border",
        size === "lg" ? "px-3 py-1 text-sm" : "px-2 py-0.5 text-[10px]",
        CONSENSUS_STYLES[consensus] ?? CONSENSUS_STYLES.NEUTRAL
      )}
    >
      {consensus}
    </span>
  );
}
