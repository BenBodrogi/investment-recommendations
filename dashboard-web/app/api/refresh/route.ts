import { spawn } from "node:child_process";
import { pipelineDir, pipelinePythonPath } from "@/lib/data";

// GET (not POST) deliberately mirrors project-sentinel's sentinel-dashboard
// logs/route.ts precedent, since the browser's native EventSource can only
// issue GET requests - this route is only ever invoked via `new
// EventSource(...)` from an explicit button click, never linked/prefetched,
// so the GET-with-side-effect tradeoff is acceptable for a local single-user
// tool.
export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const encoder = new TextEncoder();

  const stream = new ReadableStream({
    start(controller) {
      let closed = false;

      // Three independent paths (natural completion, process error, client
      // abort) can each try to close the stream. Without a shared guard,
      // a process that outlives an aborted request throws "Controller is
      // already closed" as an uncaught exception when it finally exits -
      // which can take down the whole dev server, not just this request.
      const safeClose = () => {
        if (closed) return;
        closed = true;
        try {
          controller.close();
        } catch {
          // already closed by a racing path - fine to ignore
        }
      };

      const send = (event: string, data: string) => {
        if (closed) return;
        try {
          controller.enqueue(
            encoder.encode(`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`)
          );
        } catch {
          // stream already closed - nothing to do
        }
      };

      let proc: ReturnType<typeof spawn>;
      try {
        proc = spawn(pipelinePythonPath(), ["run_pipeline.py"], {
          cwd: pipelineDir(),
          stdio: ["ignore", "pipe", "pipe"],
          shell: false,
        });
      } catch (err) {
        send("error", err instanceof Error ? err.message : String(err));
        safeClose();
        return;
      }

      proc.stdout?.on("data", (chunk: Buffer) => send("log", chunk.toString()));
      proc.stderr?.on("data", (chunk: Buffer) => send("log", chunk.toString()));

      proc.on("close", (code) => {
        send("done", String(code));
        safeClose();
      });
      proc.on("error", (err) => {
        send("error", err.message);
        safeClose();
      });

      request.signal.addEventListener("abort", () => {
        // Node's cross-platform proc.kill() does not reliably terminate a
        // process tree on Windows, which would otherwise leave an
        // abandoned pipeline run (e.g. navigating away mid-refresh) alive
        // in the background, still burning real API quota. taskkill with
        // /T (tree) /F (force) actually kills it.
        if (proc.pid) {
          if (process.platform === "win32") {
            spawn("taskkill", ["/pid", String(proc.pid), "/T", "/F"], {
              stdio: "ignore",
            });
          } else {
            proc.kill();
          }
        }
        safeClose();
      });
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
    },
  });
}
