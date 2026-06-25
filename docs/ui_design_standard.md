# UI Design Standard v3.0

Generated: 2026-06-21

## Purpose

This document defines the visual and interaction standard for the v3.0 desktop product.
The UI must feel like an operator workbench for SolidWorks drawing production, not a
collection of backend buttons.

## Layout

- Every page must have a clear page title and a concise operational status line.
- Page margins must be at least 16 px.
- Related controls must be grouped with at least 12 px spacing.
- Tables must not touch page edges.
- Repeated item cards may use a small border radius, but full page sections should not be nested cards.
- Empty states must explain what is missing and show the next useful action.

## Visual Hierarchy

- Primary actions must be visually stronger than secondary actions.
- Destructive or interrupting actions must be visually distinct.
- Status summaries should be scannable before detailed logs.
- Dense operational views should prefer tables, compact status strips, and grouped panels over decorative layouts.

## Color

- Pass: green.
- Warning: yellow or orange.
- Fail: red.
- Info: blue or neutral gray.
- Recovering or retrying: blue or violet.
- Colors must not be the only carrier of meaning; every status also needs readable text.

## Typography

- Use a CJK-capable UI font for all screenshot automation and released builds.
- Page titles, section titles, body text, table text, and helper text must have clear hierarchy.
- Logs and JSONL/event output should use a monospaced font.
- Text must not overlap, truncate critical status without tooltip, or render as tofu squares.

## Tables

- Table headers must be visible and descriptive.
- Row height must be consistent.
- Status columns should use badges or short status text.
- Long paths may be elided visually, but the full path must be available through tooltip, details, or copy action.
- Tables must remain usable with hundreds of historical output rows.

## Errors And Warnings

- Every error must include a reason.
- Operator-facing errors must include a fix suggestion when one is known.
- Tracebacks may be available in diagnostics, but they must not be the only UI explanation.
- SolidWorks unavailable, missing model weights, missing API keys, and license gaps should degrade the relevant capability without crashing the app.

## Job Interaction

- Long tasks must be started through `JobRuntimeFacade`, `JobRunner`, and worker processes.
- UI controls must remain responsive during running, timeout, retry, cancel, and recovery states.
- Job events shown in the UI must come from structured worker JSONL when possible.

## Screenshot Acceptance

- Source-level screenshots must be readable and nonblank.
- EXE screenshots must prove the bundled product can render the same pages.
- Screenshot size thresholds are acceptance signals, not design goals; a large PNG is not sufficient if the page is visually broken.
- Visual inspection remains required for: no blank page, no tofu text, no major overlap, readable main state, and coherent navigation.
