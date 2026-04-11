import React from "react";
import { Box, Text } from "ink";
import type { StructuredTelemetryState } from "../types.js";

const PHASE_LABELS: Record<string, string> = {
  bootstrap: "bootstrap",
  eval_initial: "eval initiale",
  coord_ascent: "coordinate ascent",
  eval_holdout: "validation holdout",
  done: "done",
  failed: "failed",
};

export const StructuredStatusIndicator: React.FC<{ state: StructuredTelemetryState }> = ({ state }) => {
  const {
    phase, currentSlot, currentStep, currentStepMax, currentSubPhase,
    lastActivitySec, nPassesCompleted, nSlotsDone, nStepsAcceptedGlobal,
    nStepsGlobal, apiCallsCount, slots,
  } = state;
  const phaseLabel = PHASE_LABELS[phase] ?? phase;

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
        {" "}passes <Text bold>{nPassesCompleted}</Text>
        {"    "}slots <Text bold>{nSlotsDone}</Text>/{slots.length}
        {"    "}steps <Text bold color="green">{nStepsAcceptedGlobal}</Text>/{nStepsGlobal}
        {"    "}api <Text bold>{apiCallsCount}</Text>
        {"    "}<Text color={statusColor} bold>{statusText}</Text>
      </Text>
      <Text>
        {" "}<Text color="cyan" bold>{phaseLabel}</Text>
        {phase === "coord_ascent" && currentSlot && (
          <Text>
            {"  \u2514\u2500 "}
            <Text color="magenta">{currentSlot}</Text>
            <Text dimColor>{" step "}{currentStep}/{currentStepMax}</Text>
            {currentSubPhase && (
              <Text>{"  "}<Text color="cyan">({currentSubPhase})</Text></Text>
            )}
          </Text>
        )}
      </Text>
    </Box>
  );
};
