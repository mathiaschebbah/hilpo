import React from "react";
import { Box, Text } from "ink";
import type { StructuredSlot } from "../types.js";

const COLS = {
  done: 3,
  slot: 22,
  steps: 7,
  accepted: 5,
  jInit: 10,
  jCurr: 10,
  delta: 11,
  tabu: 5,
};

function fmtDelta(delta: number): string {
  const sign = delta >= 0 ? "+" : "";
  return `${sign}${delta.toFixed(4)}`;
}

const Header: React.FC = () => (
  <Box>
    <Box width={COLS.done}><Text dimColor> </Text></Box>
    <Box width={COLS.slot}><Text dimColor>slot</Text></Box>
    <Box width={COLS.steps} justifyContent="flex-end"><Text dimColor>steps</Text></Box>
    <Box width={COLS.accepted} justifyContent="flex-end"><Text dimColor>acc</Text></Box>
    <Box width={COLS.jInit} justifyContent="flex-end"><Text dimColor>J_init</Text></Box>
    <Box width={COLS.jCurr} justifyContent="flex-end"><Text dimColor>J_curr</Text></Box>
    <Box width={COLS.delta} justifyContent="flex-end"><Text dimColor>Δ</Text></Box>
    <Box width={COLS.tabu} justifyContent="flex-end"><Text dimColor>tabu</Text></Box>
  </Box>
);

const SlotRow: React.FC<{ slot: StructuredSlot }> = ({ slot }) => {
  const delta = slot.jCurrent - slot.jInitial;
  const positive = delta > 0;
  const negative = delta < 0;
  const dColor = positive ? "green" : negative ? "red" : undefined;
  const doneMark = slot.done ? "\u25CF" : "\u00B7";
  const markColor = slot.done ? "green" : undefined;
  const slotKey = slot.key.length > COLS.slot - 1 ? slot.key.slice(0, COLS.slot - 2) + "…" : slot.key;
  return (
    <Box>
      <Box width={COLS.done}>
        <Text color={markColor}> {doneMark} </Text>
      </Box>
      <Box width={COLS.slot}>
        <Text>{slotKey}</Text>
      </Box>
      <Box width={COLS.steps} justifyContent="flex-end">
        <Text>{slot.stepsTaken}</Text>
      </Box>
      <Box width={COLS.accepted} justifyContent="flex-end">
        <Text color="green">{slot.stepsAccepted}</Text>
      </Box>
      <Box width={COLS.jInit} justifyContent="flex-end">
        <Text>{slot.jInitial.toFixed(4)}</Text>
      </Box>
      <Box width={COLS.jCurr} justifyContent="flex-end">
        <Text bold>{slot.jCurrent.toFixed(4)}</Text>
      </Box>
      <Box width={COLS.delta} justifyContent="flex-end">
        {dColor ? (
          <Text color={dColor}>{fmtDelta(delta)}</Text>
        ) : (
          <Text dimColor>{fmtDelta(delta)}</Text>
        )}
      </Box>
      <Box width={COLS.tabu} justifyContent="flex-end">
        <Text dimColor>{slot.tabuHits}</Text>
      </Box>
    </Box>
  );
};

export const SlotsTable: React.FC<{ slots: StructuredSlot[] }> = ({ slots }) => {
  if (slots.length === 0) {
    return <Text dimColor> no slots yet...</Text>;
  }
  return (
    <Box flexDirection="column">
      <Header />
      {slots.map((s) => <SlotRow key={s.key} slot={s} />)}
    </Box>
  );
};
