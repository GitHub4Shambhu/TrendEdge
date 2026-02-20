/**
 * TrendEdge Frontend - Market Sentiment Gauge Component
 *
 * Displays overall market sentiment as a visual gauge.
 */

interface SentimentGaugeProps {
  sentiment: number; // -1 to 1
}

export function SentimentGauge({ sentiment }: SentimentGaugeProps) {
  // Convert -1 to 1 range to 0 to 100 for display
  const percentage = ((sentiment + 1) / 2) * 100;

  const getSentimentLabel = () => {
    if (sentiment > 0.3) return "Bullish";
    if (sentiment > 0.1) return "Slightly Bullish";
    if (sentiment < -0.3) return "Bearish";
    if (sentiment < -0.1) return "Slightly Bearish";
    return "Neutral";
  };

  const getSentimentColor = () => {
    if (sentiment > 0.3) return "text-green-400";
    if (sentiment > 0.1) return "text-green-300";
    if (sentiment < -0.3) return "text-red-400";
    if (sentiment < -0.1) return "text-red-300";
    return "text-gray-400";
  };

  const getBarColor = () => {
    if (sentiment > 0.3) return "bg-green-500";
    if (sentiment > 0.1) return "bg-green-400";
    if (sentiment < -0.3) return "bg-red-500";
    if (sentiment < -0.1) return "bg-red-400";
    return "bg-gray-500";
  };

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-6">
      <h3 className="text-sm font-medium text-gray-400 uppercase tracking-wider mb-4">
        Market Sentiment
      </h3>

      <div className="flex items-center justify-between mb-2">
        <span className="text-sm text-red-400">Bearish</span>
        <span className="text-sm text-green-400">Bullish</span>
      </div>

      {/* Sentiment Bar */}
      <div className="relative h-3 bg-gray-800 rounded-full overflow-hidden mb-4">
        {/* Background gradient */}
        <div className="absolute inset-0 bg-gradient-to-r from-red-500/20 via-gray-500/20 to-green-500/20" />

        {/* Indicator */}
        <div
          className="absolute top-0 bottom-0 w-1 bg-white rounded-full shadow-lg transition-all duration-500"
          style={{ left: `${percentage}%`, transform: "translateX(-50%)" }}
        />
      </div>

      {/* Value Display */}
      <div className="text-center">
        <p className={`text-3xl font-bold ${getSentimentColor()}`}>
          {getSentimentLabel()}
        </p>
        <p className="text-sm text-gray-500 mt-1">
          Score: {(sentiment * 100).toFixed(1)}
        </p>
      </div>
    </div>
  );
}
