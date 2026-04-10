import React from "react";
import { Box, Text } from "ink";

type EventEntry = { ts: string; msg: string; type?: "event" | "api" | "error" };

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

        // Important events get color based on content
        const color = ev.msg.includes("PROMOTED")
          ? "green"
          : ev.msg.includes("ROLLBACK")
            ? "red"
            : ev.msg.includes("FAILED") || ev.msg.includes("TIMEOUT")
              ? "yellow"
              : ev.msg.includes("REWRITE")
                ? "cyan"
                : undefined;

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
