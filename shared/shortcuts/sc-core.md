# One in-turn re-read pass

Apply this procedure to the question supplied by the entry point, once, in the
current turn. Follow the normal instructions for the question: use tools, keep
the repository work trace current, and honor review gates when the work calls
for them. This pass changes the answer, not those obligations.

1. Use the complete, current checklist supplied by the entry point. If it was
   not supplied, read `~/.config/mrcall-ai-kit/reread-checklist.md` now, in
   full. Do not re-read a checklist already supplied in the prompt through a
   tool call. If neither route supplies a readable checklist, tell the
   operator that it is not installed and name
   `./install.sh --features reread`. Stop rather than claim a pass happened.
2. Do the work needed to answer the question and compose a complete draft.
3. Read the draft against every item in the checklist. Run a check the answer
   names but has not performed when that check is available. Fix each failure
   in the draft. Apply this pass even when the answer is under 500 characters.
4. Present only the resulting answer. Do not announce the pass, describe the
   checklist, or append a review note. If a check is genuinely unavailable,
   state that limit in the answer rather than inventing a result.

This is an instruction to the answering model. No runtime hook intercepts the
answer, so do not claim that the pass is enforced before delivery.
