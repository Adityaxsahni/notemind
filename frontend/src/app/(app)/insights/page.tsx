import type { Metadata } from "next";

import { InsightsView } from "./InsightsView";

export const metadata: Metadata = { title: "Insights", description: "Admin analytics and audit log." };

export default function InsightsPage() {
  return <InsightsView />;
}
