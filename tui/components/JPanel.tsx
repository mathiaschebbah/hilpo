import React from "react";
import { Box, Text } from "ink";
import type { StructuredTelemetryState, JComponents } from "../types.js";

function fmtJ(j: number | null | undefined): string {
  return j === null || j === undefined ? "—" : j.toFixed(4);
}

function fmtDelta(delta: number): string {
  const sign = delta >= 0 ? "+" : "";
  return `${sign}${delta.toFixed(4)}`;
}

const JComponentsRow: React.FC<{ label: string; c: JComponents }> = ({ label, c }) => (
  <Text>
    {" "}<Text dimColor>{label}</Text>{"   "}
    <Text color="magenta">vf={fmtJ(c.macroF1_vf)}</Text>{"   "}
    <Text color="green">cat={fmtJ(c.macroF1_cat)}</Text>{"   "}
    <Text color="blue">strat={fmtJ(c.acc_strat)}</Text>
  </Text>
);

export const JPanel: React.FC<{ state: StructuredTelemetryState }> = ({ state }) => {
  const { jInitial, jCurrent, jComponents, jHoldout, jHoldoutComponents } = state;
  const delta = (jCurrent ?? 0) - (jInitial ?? 0);
  const hasJ = jInitial !== null && jCurrent !== null;
  const deltaPositive = delta > 0;
  const deltaNegative = delta < 0;

  return (
    <Box flexDirection="column">
      <Text>
        {" "}<Text dimColor>J_opt    </Text>
        {hasJ ? (
          <>
            {fmtJ(jInitial)} → {" "}
            <Text
              bold
              color={deltaPositive ? "green" : deltaNegative ? "red" : undefined}
            >
              {fmtJ(jCurrent)}
            </Text>
            {"    "}
            <Text color={deltaPositive ? "green" : deltaNegative ? "red" : undefined}>
              {fmtDelta(delta)}
            </Text>
          </>
        ) : (
          <Text dimColor>waiting for initial evaluation...</Text>
        )}
      </Text>
      <JComponentsRow label="macroF1 " c={jComponents} />
      {jHoldout !== null && (
        <>
          <Text>
            {" "}<Text dimColor>holdout  </Text>
            J=<Text bold color="cyan">{fmtJ(jHoldout)}</Text>
          </Text>
          <JComponentsRow label="         " c={jHoldoutComponents} />
        </>
      )}
    </Box>
  );
};
