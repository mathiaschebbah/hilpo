import React, { useState, useEffect, useRef } from "react";
import { Box, Text, useStdout } from "ink";
import type { StructuredTelemetryState } from "../types.js";
import { StructuredProgressBar } from "./StructuredProgressBar.js";
import { JPanel } from "./JPanel.js";
import { SlotsTable } from "./SlotsTable.js";
import { StructuredStatusIndicator } from "./StructuredStatusIndicator.js";
import { EventLog } from "./EventLog.js";

const SEP = "\u2500".repeat(60);

export const StructuredDashboard: React.FC<{
  state: StructuredTelemetryState;
  done: boolean;
  exitCode?: number | null;
}> = ({ state, done }) => {
  const completed = done && state.phase === "done";
  const failed = done && !completed;
  const { stdout } = useStdout();
  const [termRows, setTermRows] = useState(stdout.rows ?? 24);
  const [, setTick] = useState(0);
  const stateReceivedAt = useRef(Date.now());
  const prevState = useRef(state);

  useEffect(() => {
    const onResize = () => setTermRows(stdout.rows ?? 24);
    stdout.on("resize", onResize);
    return () => {
      stdout.off("resize", onResize);
    };
  }, [stdout]);

  if (prevState.current !== state) {
    stateReceivedAt.current = Date.now();
    prevState.current = state;
  }

  useEffect(() => {
    if (done) return;
    const id = setInterval(() => setTick((t) => t + 1), 1000);
    return () => clearInterval(id);
  }, [done]);

  const sinceLastState = Math.floor((Date.now() - stateReceivedAt.current) / 1000);
  const localState: StructuredTelemetryState = {
    ...state,
    elapsedSec: state.elapsedSec + sinceLastState,
    phaseElapsedSec: state.phaseElapsedSec + sinceLastState,
    lastActivitySec: state.lastActivitySec + sinceLastState,
    etaSec: state.etaSec !== null ? Math.max(0, state.etaSec - sinceLastState) : null,
  };

  const borderColor = failed ? "red" : completed ? "green" : "blue";
  const title = failed
    ? ` MILPO Structured \u2014 run #${state.runId} \u2014 FAILED`
    : completed
      ? ` MILPO Structured \u2014 run #${state.runId} \u2014 DONE`
      : ` MILPO Structured \u2014 run #${state.runId}`;

  const nSlots = Math.max(1, localState.slots.length);
  const hasFlags = localState.flags.length > 0;
  const hasHoldout = localState.jHoldout !== null;
  // border(2) + title(1) + [flags(1)] + blank(1) + progress(2) + sep(1)
  // + J(2) + [holdout(2)] + status(2) + sep(1) + table header(1) + slots(n) + sep(1)
  const headerOverhead =
    2 + 1 + (hasFlags ? 1 : 0) + 1 + 2 + 1 + 2 + (hasHoldout ? 2 : 0) + 2 + 1 + 1 + nSlots + 1;
  const eventsHeight = Math.max(3, termRows - headerOverhead);

  return (
    <Box
      flexDirection="column"
      borderStyle="round"
      borderColor={borderColor}
      paddingX={1}
      height={termRows}
    >
      <Text bold color={borderColor}>{title}</Text>
      {hasFlags && (
        <Text color="magenta" bold>{" "}{localState.flags.join("  ")}</Text>
      )}
      <Text>{""}</Text>
      <StructuredProgressBar state={localState} />
      <Text dimColor>{" "}{SEP}</Text>
      <JPanel state={localState} />
      <StructuredStatusIndicator state={localState} />
      <Text dimColor>{" "}{SEP}</Text>
      <SlotsTable slots={localState.slots} />
      <Text dimColor>{" "}{SEP}</Text>
      <EventLog events={localState.events} maxLines={eventsHeight} />
    </Box>
  );
};
