import { describe, expect, it } from "vitest";

import { splitCitations } from "@/components/AnswerText";
import { errorMessage } from "@/lib/api";
import { safeNext } from "@/lib/auth";
import { SSEParser } from "@/lib/sse";

describe("SSEParser", () => {
  const stream =
    'event: token\ndata: {"text": "Third normal form"}\n\n' +
    'event: token\ndata: {"text": " [S1]."}\n\n' +
    'event: done\ndata: {"answer": "Third normal form [S1].", "citations": [], "grounded": true, "cached": false, "truncated": false}\n\n';

  it("parses a complete stream", () => {
    const events = new SSEParser().push(stream);
    expect(events.map((e) => e.type)).toEqual(["token", "token", "done"]);
    expect(events[0]).toEqual({ type: "token", text: "Third normal form" });
  });

  it("handles events split across arbitrary network chunks", () => {
    const parser = new SSEParser();
    const events = [];
    for (let i = 0; i < stream.length; i += 7) events.push(...parser.push(stream.slice(i, i + 7)));
    expect(events).toEqual(new SSEParser().push(stream));
  });

  it("handles CRLF line endings and errors", () => {
    const events = new SSEParser().push('event: error\r\ndata: {"message": "Unavailable"}\r\n\r\n');
    expect(events).toEqual([{ type: "error", message: "Unavailable" }]);
  });

  it("ignores unknown event types", () => {
    expect(new SSEParser().push('event: ping\ndata: {}\n\n')).toEqual([]);
  });
});

describe("splitCitations", () => {
  it("separates markers from text", () => {
    expect(splitCitations("A [S1] b[S2].")).toEqual([
      { text: "A " },
      { text: "[S1]", sourceId: "S1" },
      { text: " b" },
      { text: "[S2]", sourceId: "S2" },
      { text: "." },
    ]);
  });

  it("leaves other brackets as text", () => {
    expect(splitCitations("a[1] and <script>")).toEqual([{ text: "a[1] and <script>" }]);
  });
});

describe("safeNext", () => {
  it.each([
    ["/c/123", "/c/123"],
    ["/join?token=x", "/join?token=x"],
    ["https://evil.example", "/courses"],
    ["//evil.example", "/courses"],
    [null, "/courses"],
  ])("%s -> %s", (input, expected) => {
    expect(safeNext(input)).toBe(expected);
  });
});

describe("errorMessage", () => {
  it("reads FastAPI string details", async () => {
    expect(await errorMessage(Response.json({ detail: "Collection not found" }, { status: 404 }))).toBe(
      "Collection not found",
    );
  });

  it("joins validation errors without the 'Value error' prefix", async () => {
    const body = { detail: [{ loc: ["body"], msg: "Value error, Password is too common", type: "value_error" }] };
    expect(await errorMessage(Response.json(body, { status: 422 }))).toBe("Password is too common");
  });

  it("falls back for non-JSON bodies", async () => {
    expect(await errorMessage(new Response("oops", { status: 502 }))).toBe("Request failed (502)");
  });
});
