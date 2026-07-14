# Tiffany Web Logo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Match every web logo surface to the mobile Tiffany mark.

**Architecture:** Reuse the existing `.logo-icon` and `.avatar` selectors, replace their gradient with mobile's `#0ABAB5`, and update the existing SVG favicon to the same Tiffany background and white outline.

**Tech Stack:** CSS, SVG, Python unittest.

## Global Constraints

- Keep the existing cat geometry, sizing, and rotation animation.
- Do not change the broader application color theme.

---

### Task 1: Unify Web Logo Colors

- [x] Add a failing static test for Tiffany backgrounds and white favicon stroke.
- [x] Update `styles.css` and `favicon.svg` with the mobile mark colors.
- [x] Run focused/full tests and syntax checks.
- [x] Bump the app version, update Coho docs, and restart port 8090.
