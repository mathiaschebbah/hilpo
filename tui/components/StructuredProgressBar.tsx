import React from "react";
import { Box, Text } from "ink";
import type { StructuredTelemetryState } from "../types.js";

function fmtTime(sec: number): string {
  if (sec < 60) return `${sec}s`;
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return s > 0 ? `${m}m${s}s` : `${m}m`;
}

function fmtTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1000).toFixed(1)}K`;
  return String(n);
}

function buildBar(pct: number, width = 30): string {
  const clamped = Math.max(0, Math.min(1, pct));
  const filled = Math.round(clamped * width);
  return "\u2588".repeat(filled) + "\u2591".repeat(width - filled);
}

const EvalProgressBar: React.FC<{ state: StructuredTelemetryState }> = ({ state }) => {
  const {
    phaseDone, phaseTotal, phaseUnit, rate, etaSec,
    phaseElapsedSec, costUsd, inputTokens, outputTokens,
  } = state;
  const pct = phaseTotal > 0 ? phaseDone / phaseTotal : 0;
  const bar = buildBar(pct, 30);
  const pctStr = `${Math.round(pct * 100)}%`;
  const unit = phaseUnit ?? "items";
  return (
    <Box flexDirection="column">
      <Text>
        {" "}{bar}{"  "}
        <Text bold>{phaseDone}</Text>/{phaseTotal} ({pctStr}){"  "}
        <Text color="cyan">{rate.toFixed(1)} {unit}/s</Text>
      </Text>
      <Text>
        {" "}Elapsed <Text bold>{fmtTime(phaseElapsedSec)}</Text>
        {"    "}ETA <Text bold>{etaSec !== null ? fmtTime(etaSec) : "..."}</Text>
        {"    "}cost <Text color="yellow">${costUsd.toFixed(2)}</Text>
        {"    "}{fmtTokens(inputTokens)} in / {fmtTokens(outputTokens)} out
      </Text>
    </Box>
  );
};

const CoordAscentProgressBar: React.FC<{ state: StructuredTelemetryState }> = ({ state }) => {
  const {
    passNum, passMax, currentStep, currentStepMax,
    nStepsGlobal, nStepsAcceptedGlobal, nSlotsDone, slots,
    phaseElapsedSec, costUsd, inputTokens, outputTokens, rate,
  } = state;
  const nSlots = slots.length;
  const passPct = passMax > 0 ? passNum / passMax : 0;
  const slotPct = nSlots > 0 ? nSlotsDone / nSlots : 0;
  const stepPct = currentStepMax > 0 ? currentStep / currentStepMax : 0;
  return (
    <Box flexDirection="column">
      <Text>
        {" "}pass  {buildBar(passPct, 10)} <Text bold>{passNum}</Text>/{passMax}
        {"   "}slot  {buildBar(slotPct, 10)} <Text bold>{nSlotsDone}</Text>/{nSlots}
        {"   "}step  {buildBar(stepPct, 10)} <Text bold>{currentStep}</Text>/{currentStepMax}
      </Text>
      <Text>
        {" "}Elapsed <Text bold>{fmtTime(phaseElapsedSec)}</Text>
        {"    "}accepted <Text bold color="green">{nStepsAcceptedGlobal}</Text>/{nStepsGlobal}
        {"    "}<Text color="cyan">{rate.toFixed(2)} steps/s</Text>
        {"    "}cost <Text color="yellow">${costUsd.toFixed(2)}</Text>
        {"    "}{fmtTokens(inputTokens)} in / {fmtTokens(outputTokens)} out
      </Text>
    </Box>
  );
};

const TerminalProgressBar: React.FC<{ state: StructuredTelemetryState }> = ({ state }) => {
  const {
    phase, phaseElapsedSec, nStepsGlobal, nStepsAcceptedGlobal,
    costUsd, inputTokens, outputTokens,
  } = state;
  const bar = buildBar(1, 30);
  const label = phase === "done" ? "DONE" : "FAILED";
  const color = phase === "done" ? "green" : "red";
  return (
    <Box flexDirection="column">
      <Text>
        {" "}{bar}{"  "}
        <Text bold color={color}>{label}</Text>
      </Text>
      <Text>
        {" "}Elapsed <Text bold>{fmtTime(phaseElapsedSec)}</Text>
        {"    "}steps <Text bold>{nStepsAcceptedGlobal}</Text>/{nStepsGlobal} accepted
        {"    "}cost <Text color="yellow">${costUsd.toFixed(2)}</Text>
        {"    "}{fmtTokens(inputTokens)} in / {fmtTokens(outputTokens)} out
      </Text>
    </Box>
  );
};

export const StructuredProgressBar: React.FC<{ state: StructuredTelemetryState }> = ({ state }) => {
  if (state.phase === "coord_ascent") return <CoordAscentProgressBar state={state} />;
  if (state.phase === "done" || state.phase === "failed") return <TerminalProgressBar state={state} />;
  return <EvalProgressBar state={state} />;
};
