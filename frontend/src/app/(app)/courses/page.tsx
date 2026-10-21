import type { Metadata } from "next";

import { CoursesView } from "./CoursesView";

export const metadata: Metadata = {
  title: "Your courses",
  description: "Your NoteMind collections: one per course, with your uploaded notes.",
};

export default function CoursesPage() {
  return <CoursesView />;
}
