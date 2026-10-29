# Reference call guide: {name}

{demo}Role: {role}. Written {written}. For one or two finalists, after the test task, before any offer.

**You make the call.** Voice, 10 to 15 minutes. The assistant wrote this guide and will organise your notes; it never contacts a referee or the candidate.

## Before you call

{referee_lines}
- Do not contact: {do_not_contact}
- Never the current employer before an offer.
- Raw notes are deleted on {delete_date}. The summary stays with the decision.
- One person's opinion is never a complete picture of a candidate. Look for concrete examples and weigh them.

## The call, 10 to 15 minutes

| Minutes | Ask | Listen for |
|---|---|---|
{guide_rows}

When an answer is an adjective, ask once: "Can you give me an example?" or "What happened next?" Then let them talk.

{if_time}

## Questions still open after the interviews and the work sample

| # | Question for the referee | Why it is still open | Source |
|---|---|---|---|
{open_rows}

{candidate_block}

## After the call

Write your notes the same day in `out/references/{slug}-notes-<n>.md` (from `templates/notes.md`): every answer as Concrete example / Vague opinion / Follow-up. Then run `summary.py`. Nothing about family, health, age, origin, religion or relationship status, even if it comes up. Don't share a referee's words with the candidate; if the candidate asks for their data under privacy law, follow your law.
