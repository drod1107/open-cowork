---
description: Debugging methodology
---

# Debugging

You are debugging an issue. Follow these principles:

- Reproduce the problem first — never debug from assumptions
- Check logs and error messages before changing code
- Binary search: narrow the scope by halving
- Verify your fix actually resolves the root cause, not just a symptom
- Ask: what changed recently? What's different about this environment?
- Check dependencies, versions, and configuration
- Write a test that proves the bug exists before fixing it
