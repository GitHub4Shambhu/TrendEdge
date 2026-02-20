/**
 * TrendEdge Frontend - Utility Functions
 *
 * Common utility functions used across the application.
 */

import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

/**
 * Merge Tailwind CSS classes with proper conflict resolution
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * Format a number as currency
 */
export function formatCurrency(value: number, currency: string = "USD"): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}

/**
 * Format a number as percentage
 */
export function formatPercent(value: number, decimals: number = 2): string {
  const sign = value >= 0 ? "+" : "";
  return `${sign}${value.toFixed(decimals)}%`;
}

/**
 * Format momentum score for display
 */
export function formatScore(score: number): string {
  const sign = score >= 0 ? "+" : "";
  return `${sign}${(score * 100).toFixed(1)}`;
}

/**
 * Get color class based on value (positive/negative)
 */
export function getValueColor(value: number): string {
  if (value > 0) return "text-green-500";
  if (value < 0) return "text-red-500";
  return "text-gray-500";
}

/**
 * Get signal color and background
 */
export function getSignalStyle(signal: "buy" | "sell" | "hold"): {
  bg: string;
  text: string;
  border: string;
} {
  switch (signal) {
    case "buy":
      return {
        bg: "bg-green-500/10",
        text: "text-green-500",
        border: "border-green-500/20",
      };
    case "sell":
      return {
        bg: "bg-red-500/10",
        text: "text-red-500",
        border: "border-red-500/20",
      };
    default:
      return {
        bg: "bg-gray-500/10",
        text: "text-gray-500",
        border: "border-gray-500/20",
      };
  }
}

/**
 * Get risk level color
 */
export function getRiskColor(risk: "low" | "medium" | "high"): string {
  switch (risk) {
    case "low":
      return "text-green-500";
    case "medium":
      return "text-yellow-500";
    case "high":
      return "text-red-500";
    default:
      return "text-gray-500";
  }
}

/**
 * Format relative time (e.g., "2 minutes ago")
 */
export function formatRelativeTime(date: string | Date): string {
  const now = new Date();
  const then = new Date(date);
  const diffMs = now.getTime() - then.getTime();
  const diffSecs = Math.floor(diffMs / 1000);
  const diffMins = Math.floor(diffSecs / 60);
  const diffHours = Math.floor(diffMins / 60);

  if (diffSecs < 60) return "Just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  return then.toLocaleDateString();
}
