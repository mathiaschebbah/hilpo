import React from "react";
import { Box, Text } from "ink";

export const EventLog: React.FC<{ events: Array<{ ts: string; msg: string }> }> = ({ events }) => {
  if (events.length === 0) return null;

  const maxEvents = Math.min(events.length, 12);

  return (
    <Box flexDirection="column">
      <Text dimColor>{" "}{"\u2500".repeat(52)}</Text>
      <Text dimColor>{" "}Events</Text>
      {events.slice(0, maxEvents).map((ev, i) => {
        const color = ev.msg.includes("PROMOTED")
          ? "green"
          : ev.msg.includes("ROLLBACK")
            ? "red"
            : ev.msg.includes("FAILED") || ev.msg.includes("skipped") || ev.msg.includes("TIMEOUT")
              ? "yellow"
              : undefined;

        return (
          <Text key={i}>
            {" "}<Text dimColor>{ev.ts}</Text>{"  "}
            <Text color={color}>{ev.msg}</Text>
          </Text>
        );
      })}
    </Box>
  );
};
