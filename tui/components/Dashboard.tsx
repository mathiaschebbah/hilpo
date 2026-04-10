import React, { useState, useEffect, useRef } from "react";
import { Box, Text } from "ink";
import type { TelemetryState } from "../types.js";
import { ProgressBar } from "./ProgressBar.js";
import { AccuracyPanel } from "./AccuracyPanel.js";
import { EventLog } from "./EventLog.js";

const StatusIndicator: React.FC<{ state: TelemetryState }> = ({ state }) => {
  const { lastActivitySec, lastActivityLabel, phase, rewriteSubPhase } = state;

  let statusColor: string;
  let statusText: string;
  if (lastActivitySec < 10) {
    statusColor = "green";
    statusText = "active";
  } else if (lastActivitySec < 30) {
    statusColor = "yellow";
    statusText = `idle ${lastActivitySec}s`;
  } else {
    statusColor = "red";
    statusText = `IDLE ${lastActivitySec}s`;
  }

  return (
    <Box flexDirection="column">
      <Text>
        {" "}v{state.maxPromptVersion}{"    "}
        err={state.errorBufferSize}/{state.batchSize}{"    "}
        <Text color={statusColor} bold>{statusText}</Text>
      </Text>
      {phase !== "classification" && (
        <Text>
          {" "}<Text color="cyan" bold>{phase}</Text>
          {rewriteSubPhase && <Text dimColor>{"  \u2514\u2500 "}{rewriteSubPhase}</Text>}
        </Text>
      )}
      {(state.rewritesPromoted > 0 || state.rewritesRollback > 0 || state.skipped > 0) && (
        <Text>
          {" "}Rewrites{"   "}
          {state.rewritesPromoted > 0 && <Text color="green">promoted={state.rewritesPromoted} </Text>}
          {state.rewritesRollback > 0 && <Text color="red">rollback={state.rewritesRollback} </Text>}
          {state.skipped > 0 && <Text color="yellow">skipped={state.skipped}</Text>}
        </Text>
      )}
    </Box>
  );
};

export const Dashboard: React.FC<{ state: TelemetryState; done: boolean }> = ({ state, done }) => {
  const [, setTick] = useState(0);
  const stateReceivedAt = useRef(Date.now());
  const prevState = useRef(state);

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
  const localState: TelemetryState = {
    ...state,
    elapsedSec: state.elapsedSec + sinceLastState,
    lastActivitySec: state.lastActivitySec + sinceLastState,
    etaSec: state.etaSec !== null ? Math.max(0, state.etaSec - sinceLastState) : null,
  };

  const title = done
    ? ` MILPO Simulation \u2014 run #${localState.runId} \u2014 DONE`
    : ` MILPO Simulation \u2014 run #${localState.runId}`;

  return (
    <Box flexDirection="column" borderStyle="round" borderColor={done ? "green" : "blue"} paddingX={1}>
      <Text bold color={done ? "green" : "blue"}>{title}</Text>
      <Text>{""}</Text>
      <ProgressBar state={localState} />
      <Text dimColor>{" "}{"\u2500".repeat(52)}</Text>
      <AccuracyPanel state={localState} />
      <StatusIndicator state={localState} />
      <EventLog events={localState.events} />
    </Box>
  );
};
