import type { Metadata } from "next";

import { AccountView } from "./AccountView";

export const metadata: Metadata = {
  title: "Account",
  description: "Export your NoteMind data or delete your account.",
};

export default function AccountPage() {
  return <AccountView />;
}
