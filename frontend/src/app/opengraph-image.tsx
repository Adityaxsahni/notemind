import { ImageResponse } from "next/og";

// Social preview (Open Graph / Twitter): rendered once at build time into a static PNG.
export const alt = "NoteMind: answers from your own notes, with page citations";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function OpenGraphImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          background: "#f6f1e7",
          color: "#1c1b17",
          fontFamily: "sans-serif",
        }}
      >
        <div style={{ display: "flex", flexDirection: "column", justifyContent: "center", padding: "72px", width: 760 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 18, fontSize: 36 }}>
            <div
              style={{
                width: 60,
                height: 60,
                borderRadius: 16,
                background: "#1c1b17",
                color: "#f6f1e7",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: 36,
              }}
            >
              N
            </div>
            NoteMind
          </div>
          <div style={{ marginTop: 44, fontSize: 18, letterSpacing: 4, color: "#c8391c" }}>STUDY ASSISTANT</div>
          <div style={{ marginTop: 14, fontSize: 84, lineHeight: 1.0, display: "flex", flexDirection: "column" }}>
            <span>Your notes.</span>
            <span style={{ fontStyle: "italic" }}>Your answers.</span>
          </div>
          <div style={{ marginTop: 28, fontSize: 28, color: "#4a473f", maxWidth: 620 }}>
            Ask questions about your own notes, even handwritten ones. Every answer cites its page.
          </div>
        </div>
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            justifyContent: "flex-end",
            margin: "48px 48px 48px 0",
            flex: 1,
            borderRadius: 28,
            border: "3px solid #1c1b17",
            background: "#dcd4c0",
            overflow: "hidden",
          }}
        >
          <div style={{ display: "flex", flexDirection: "column", background: "#fefdf9", padding: 28 }}>
            <div style={{ fontSize: 40 }}>Cell Biology</div>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 10 }}>
              <span style={{ fontSize: 18, color: "#5f5a4f" }}>412 pages · cited</span>
              <span
                style={{
                  background: "#c8391c",
                  color: "white",
                  borderRadius: 999,
                  padding: "8px 22px",
                  fontSize: 20,
                }}
              >
                Enter
              </span>
            </div>
          </div>
        </div>
      </div>
    ),
    size,
  );
}
