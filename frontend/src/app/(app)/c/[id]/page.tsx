import type { Metadata } from "next";
import { Suspense } from "react";

import { CollectionView } from "./CollectionView";

export const metadata: Metadata = {
  title: "Course",
  description: "Ask questions about this course's notes and quiz yourself.",
};

export default function CollectionPage() {
  return (
    <Suspense>
      <CollectionView />
    </Suspense>
  );
}
