import type { AskEvent } from "./types";

/**
 * Incremental parser for the /ask server-sent event stream. Network chunks can end
 * anywhere (mid-line, mid-event), so incomplete text is buffered until a blank line.
 */
export class SSEParser {
  private buffer = "";

  push(chunk: string): AskEvent[] {
    this.buffer += chunk.replace(/\r\n/g, "\n");
    const events: AskEvent[] = [];
    let end: number;
    while ((end = this.buffer.indexOf("\n\n")) !== -1) {
      const block = this.buffer.slice(0, end);
      this.buffer = this.buffer.slice(end + 2);
      const event = parseBlock(block);
      if (event) events.push(event);
    }
    return events;
  }
}

function parseBlock(block: string): AskEvent | null {
  let name = "message";
  const data: string[] = [];
  for (const line of block.split("\n")) {
    if (line.startsWith("event:")) name = line.slice(6).trim();
    else if (line.startsWith("data:")) data.push(line.slice(5).trimStart());
  }
  if (data.length === 0) return null;
  const payload = JSON.parse(data.join("\n"));
  switch (name) {
    case "sources":
      return { type: "sources", sources: payload.sources };
    case "token":
      return { type: "token", text: payload.text };
    case "done":
      return { type: "done", data: payload };
    case "error":
      return { type: "error", message: payload.message };
    default:
      return null; // ignore event types this client doesn't know yet
  }
}
