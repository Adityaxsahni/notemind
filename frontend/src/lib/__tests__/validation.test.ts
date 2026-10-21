import { describe, expect, it } from "vitest";

import { emailProblem, passwordProblem, passwordStrength, textProblem } from "../validation";

describe("emailProblem", () => {
  it.each([["", "Enter"], ["alice", "doesn't look"], ["a@b", "doesn't look"]])("rejects %j", (email, msg) => {
    expect(emailProblem(email)).toContain(msg);
  });
  it("accepts a normal address", () => expect(emailProblem("alice@college.edu")).toBeNull());
});

describe("passwordProblem", () => {
  it("only checks presence at login (the policy isn't revealed)", () => {
    expect(passwordProblem("x", "a@b.co", false)).toBeNull();
    expect(passwordProblem("", "a@b.co", false)).toContain("Enter");
  });
  it("mirrors the backend rules at sign-up", () => {
    expect(passwordProblem("short", "a@b.co", true)).toContain("10");
    expect(passwordProblem("aaaaaaaaaaaa", "a@b.co", true)).toContain("repetitive");
    expect(passwordProblem("alice-rocks-2026", "alice@b.co", true)).toContain("email");
    expect(passwordProblem("correct-horse-battery", "bob@b.co", true)).toBeNull();
  });
  it("scores strength", () => {
    expect(passwordStrength("abc")).toBe(0);
    expect(passwordStrength("Correct-Horse-42!")).toBe(4);
  });
});

describe("textProblem", () => {
  it("rejects control characters the backend would refuse", () => {
    expect(textProblem("DBMS\u0000", "name", 120)).toContain("aren't allowed");
    expect(textProblem("Evil‮name", "name", 120)).toContain("aren't allowed");
    expect(textProblem("DBMS Sem 5", "name", 120)).toBeNull();
  });
});
