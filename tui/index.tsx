import React, { useState, useEffect, useRef } from "react";
import { render, Text } from "ink";
import { WebSocketServer } from "ws";
import { spawn, type ChildProcess } from "child_process";
import { resolve, dirname } from "path";
import { fileURLToPath } from "url";
import type { TelemetryState } from "./types.js";
import { Dashboard } from "./components/Dashboard.js";

const __dirname = dirname(fileURLToPath(import.meta.url));
const projectRoot = resolve(__dirname, "..");

const WS_PORT = 9999;

const App: React.FC = () => {
  const [state, setState] = useState<TelemetryState | null>(null);
  const [pythonExited, setPythonExited] = useState(false);
  const [exitCode, setExitCode] = useState<number | null>(null);
  const childRef = useRef<ChildProcess | null>(null);

  useEffect(() => {
    // 1. Start WebSocket server
    const wss = new WebSocketServer({ port: WS_PORT });

    wss.on("connection", (ws) => {
      ws.on("message", (raw) => {
        try {
          const data = JSON.parse(raw.toString()) as TelemetryState;
          setState(data);
        } catch {
          // ignore malformed messages
        }
      });
    });

    // 2. Spawn Python simulation (forward CLI args after --)
    const args = process.argv.slice(2);
    const child = spawn("uv", ["run", "python", "scripts/run_simulation.py", ...args], {
      cwd: projectRoot,
      stdio: ["inherit", "ignore", "ignore"],
      env: { ...process.env, MILPO_WS_PORT: String(WS_PORT) },
    });
    childRef.current = child;

    child.on("exit", (code) => {
      setExitCode(code);
      setPythonExited(true);
    });

    // Cleanup on Ctrl+C
    const onExit = () => {
      child.kill("SIGINT");
      wss.close();
      process.exit(0);
    };
    process.on("SIGINT", onExit);
    process.on("SIGTERM", onExit);

    return () => {
      child.kill();
      wss.close();
      process.off("SIGINT", onExit);
      process.off("SIGTERM", onExit);
    };
  }, []);

  if (!state) {
    return <Text color="yellow"> Starting MILPO simulation (waiting for telemetry on ws://localhost:{WS_PORT})...</Text>;
  }

  return <Dashboard state={state} done={pythonExited} />;
};

render(<App />);
