---
name: dev-work
description: Professional developer workflow - read docs first, test incrementally, never guess, ask when unclear. Use for any development task, bug fix, or feature implementation.
license: MIT
compatibility: opencode
metadata:
  audience: developers
  workflow: test-driven
---

1. **Understand completely** - Read request carefully, ask clarifying questions, never assume "obvious next steps"

2. **Read docs FIRST** - Before touching code, read official docs for any tool/library/framework involved, read source code if docs unclear, never rely on memory or "what usually works", if stuck after 2 failed attempts → STOP and read source documentation

3. **Check current state** - What exists? What's running? What's broken? Run health checks, status commands, existing tests, verify assumptions before building on top of them

4. **ONE small, testable change** - Not "a few changes" - ONE change, run the relevant test/check immediately after, if it passes commit it, if it fails fix it before continuing

5. **Verify incrementally** - After EVERY single change: run tests, curl endpoints, check logs, never batch multiple untested changes, "Test what exists BEFORE adding anything new"

6. **STOP at 2 failures** - Read official docs, not StackOverflow guesses, ask the user if the path forward is unclear

7. **Commit working code only** - Atomic commits: one logical change per commit, never commit broken code, write clear commit messages

8. **Communicate, don't assume** - Ask before proceeding when uncertain, don't guess what the user wants, confirm the next step before doing it
