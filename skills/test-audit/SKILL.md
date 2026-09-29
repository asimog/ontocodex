---
name: test-audit
description: Gate new or changed OntoJev tests for independent behavioral value.
---

# Test Audit

Each test names its observable contract, credible regression, primary owner boundary, and why
existing coverage does not catch it. Prefer one strong integration proof over duplicated helper
assertions. Reject source inventories, private call-shape checks, self-comparisons, fixtures that
implement the behavior, and production seams used only by tests.

