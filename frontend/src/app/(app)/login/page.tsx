import type { Metadata } from "next";
import { AuthForm } from "@/components/AuthForm";

export const metadata: Metadata = {
  title: "Log in",
  description: "Log in to NoteMind to ask questions about your course notes.",
  robots: { index: true, follow: true },
};

export default function LoginPage() {
  return <AuthForm mode="login" />;
}
