import React from "react";
import { Box, Text } from "ink";
import type { TelemetryState } from "../types.js";

function fmtTime(sec: number): string {
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return m > 0 ? `${m}m${s}s` : `${s}s`;
}

function fmtTokens(n: number): string {
  return n >= 1_000_000
    ? `${(n / 1_000_000).toFixed(1)}M`
    : `${Math.round(n / 1_000)}K`;
}

export const ProgressBar: React.FC<{ state: TelemetryState }> = ({ state }) => {
  const { cursor, total, rate, elapsedSec, etaSec, costUsd, inputTokens, outputTokens } = state;
  const pct = total > 0 ? Math.round((cursor / total) * 100) : 0;
  const width = Math.max(process.stdout.columns - 8, 40);
  const barWidth = Math.min(30, width - 30);
  const filled = total > 0 ? Math.round((cursor / total) * barWidth) : 0;
  const bar = "\u2588".repeat(filled) + "\u2591".repeat(barWidth - filled);

  return (
    <Box flexDirection="column">
      <Text>
        {" "}{bar}{"  "}
        <Text bold>{cursor}</Text>/{total} ({pct}%){"  "}
        <Text color="cyan">{rate.toFixed(1)}p/s</Text>
      </Text>
      <Text>
        {" "}Elapsed <Text bold>{fmtTime(elapsedSec)}</Text>
        {"    "}ETA <Text bold>{fmtTime(etaSec)}</Text>
        {"    "}cost <Text color="yellow">${costUsd.toFixed(2)}</Text>
        {"    "}{fmtTokens(inputTokens)} in / {fmtTokens(outputTokens)} out
      </Text>
    </Box>
  );
};
