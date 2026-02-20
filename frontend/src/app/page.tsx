/**
 * TrendEdge - Home Page
 *
 * Main entry point for the TrendEdge dashboard application.
 */

import { Dashboard } from "@/components";

export default function Home() {
  return (
    <main className="min-h-screen bg-black">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <Dashboard />
      </div>
    </main>
  );
}
