---
name: {name}
title: [the task in one line, as a title]
---
Thanks again for our conversation, {first_name}. Instead of another interview, I would like to see how you work on a task from {brand}. The time, the deadline and the terms are at the end.

## Goal

**The goal:** [what you want in the business and why it matters now, in two or three sentences. What a good result lets you do on Monday.]

## Context

[What the person needs to know to make good choices: the business in two lines, the team, the tools and limits that are real (no API, a part-time VA, who decides what). Say that the data is demo or copy data and that no account access is needed.]

[One sentence that ties this task to something they told you or showed you in the interview.]

## Task

### Part 1: [the shared task, the same text for every finalist]

[The ask in plain words, numbered if there are steps. Keep the information that is naturally missing in the real situation; do not add a trap and do not hide anything on purpose.]

{core_items}

### Part 2: [the specialist part, in the area they named as strongest]

**The goal:** [why this part matters to the business.]

[The ask. "Decide yourself what it contains and how it is built." One concrete anchor is fine.]

### What I will look at

Part 1 and part 2 are read separately. For both: did you understand the goal, is the work relevant to {brand}, can I see your reasoning, and would I use it. I prefer narrow and clear over wide and thin.

If anything is unclear, ask me at any point.

## Expected effort

About {effort} for both parts together. If it is taking much longer, stop and tell me what you left out. If the time does not fit your week, tell me and we will adjust.

## Pay

{pay_line}

## Deadline

{due}: return within {days_words} days. If you need more time, tell me.

## How to send

Reply in the same thread or send it to {submit_to}, as files or links.

## How the work may be used

{use_line}

Looking forward to it.

{signoff}

<!--
How to use this skeleton (build_briefs.py removes these notes):

The layout is the method. Keep the sections in this order:
  Goal / Context / Task (part 1, part 2, what I will look at) / Expected effort / Pay / Deadline / How to send / How the work may be used.
build_briefs.py checks that Goal, Context, Task, Expected effort, Pay, Deadline and How to send are there.

Rules the brief keeps:
  - Part 1 is the shared task: the same words for every finalist. {core_items} pulls its table from challenge/core-task.md.
  - Part 2 is one specialist part in the finalist's strongest area. It is judged against its own requirements.
  - Pay and use come from config.json: {pay_line} and {use_line}. Paid (fee_usd above 0): one fee for everyone,
    and you may use the work. Unpaid (fee_usd null or 0): no fee anywhere, and the work is never used.
  - The expected effort is stated ({effort}; about two hours is a good size) with a way to ask for an adjustment.
    A five-day window must not secretly mean five days of work.
  - No deliberately unclear line. Real situations have missing information; leave it missing, invite questions,
    and record in review.json which questions each finalist asked.
  - Never mention another candidate in any form. The build script refuses a brief that names another finalist.
  - No examples of a good answer, no required length or format. Do not list what they need not do.
  - Plain words. No long dashes (the build script refuses them).
-->
