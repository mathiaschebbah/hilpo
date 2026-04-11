import React from "react";
import { Box, Text } from "ink";

type EventEntry = { ts: string; msg: string; type?: string };

function colorForEvent(ev: EventEntry): string | undefined {
  if (ev.type === "accept") return "green";
  if (ev.type === "reject") return "yellow";
  if (ev.type === "step") return "cyan";
  if (ev.type === "error") return "red";
  if (ev.msg.includes("PROMOTED") || ev.msg.includes("ACCEPT")) return "green";
  if (ev.msg.includes("ROLLBACK")) return "red";
  if (ev.msg.includes("FAILED") || ev.msg.includes("TIMEOUT")) return "yellow";
  if (ev.msg.includes("REWRITE")) return "cyan";
  return undefined;
}

export const EventLog: React.FC<{
  events: EventEntry[];
  maxLines?: number;
}> = ({ events, maxLines = 12 }) => {
  if (events.length === 0) {
    return (
      <Box flexDirection="column" flexGrow={1}>
        <Text dimColor> Waiting for API calls...</Text>
      </Box>
    );
  }

  const visible = events.slice(0, maxLines);

  return (
    <Box flexDirection="column" flexGrow={1}>
      {visible.map((ev, i) => {
        if (ev.type === "api") {
          return (
            <Text key={i} dimColor>
              {" "}<Text color="gray">{ev.ts}</Text>{"  "}{ev.msg}
            </Text>
          );
        }

        const color = colorForEvent(ev);

        return (
          <Text key={i} bold>
            {" "}<Text dimColor>{ev.ts}</Text>{"  "}
            <Text color={color}>{ev.msg}</Text>
          </Text>
        );
      })}
    </Box>
  );
};
