import React from "react";
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
  const title = done
    ? ` MILPO Simulation \u2014 run #${state.runId} \u2014 DONE`
    : ` MILPO Simulation \u2014 run #${state.runId}`;

  return (
    <Box flexDirection="column" borderStyle="round" borderColor={done ? "green" : "blue"} paddingX={1}>
      <Text bold color={done ? "green" : "blue"}>{title}</Text>
      <Text>{""}</Text>
      <ProgressBar state={state} />
      <Text dimColor>{" "}{"\u2500".repeat(52)}</Text>
      <AccuracyPanel state={state} />
      <StatusIndicator state={state} />
      <EventLog events={state.events} />
    </Box>
  );
};
