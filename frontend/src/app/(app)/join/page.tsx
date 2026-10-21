import type { Metadata } from "next";
import { Suspense } from "react";

import { JoinView } from "./JoinView";

export const metadata: Metadata = {
  title: "Join a course",
  description: "Accept an invite to a classmate's NoteMind course.",
};

export default function JoinPage() {
  return (
    <Suspense>
      <JoinView />
    </Suspense>
  );
}
