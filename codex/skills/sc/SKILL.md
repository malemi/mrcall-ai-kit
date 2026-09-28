---
name: sc
description: Answer one question with an in-turn re-read against the installed checklist. Invoke ONLY when the operator's message opens with the literal token `$sc`, or explicitly asks for this skill by name; the question is the rest of that message. Never self-trigger on a plain question or infer it from context. Do not announce skill use or progress; return only the answer. No always-on mode.
---

# sc — one re-read pass for this answer

Use this skill only for the operator's `$sc <question>` message or an explicit
request for the sc skill. Take the question from that message, not from an
assumed previous turn. If there is no question, reply `Usage: $sc <question>`
and stop. If the entire question is `on`, `off`, `status`, or `unregister`, reply
`This $sc supports questions only; use $sc <question>.` and stop.

Do not announce that you are using this skill or reading the checklist. Send
no progress commentary about this pass; the user receives only the answer or
the one-line usage/error response.

For any other question, read `~/.config/mrcall-ai-kit/sc-core.md` in full and
follow it. If that file is missing or unreadable, reply `The re-read procedure
is not installed; run ./install.sh --features reread.` and stop. Do not claim a
re-read pass when either installed file is unavailable.
