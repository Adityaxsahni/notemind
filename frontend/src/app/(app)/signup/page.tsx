import type { Metadata } from "next";
import { AuthForm } from "@/components/AuthForm";

export const metadata: Metadata = {
  title: "Create your free account",
  description: "Sign up for NoteMind: upload your notes and get cited answers and quizzes.",
  robots: { index: true, follow: true },
};

export default function SignupPage() {
  return <AuthForm mode="signup" />;
}
