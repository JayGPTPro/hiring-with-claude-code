# Terms before the trial (to each finalist, before the brief goes out)

Saved as `hiring/out/messages/<slug>-terms-before-trial.md` by `build_briefs.py --terms`. The
assistant never sends it. Pay, hours and the start date in writing before anyone does a minute of
work. Non-binding, two to four lines. It removes the fear that makes strong candidates refuse
trials, and it stops you from drifting into a renegotiation after they have already done the work.
The mirror red flag, asking for commitment before stating pay, is the one candidates walk away from.

The role's terms come from `role` in `challenge/config.json`. The last line comes from `fee_usd`:
the fee and the effort for a paid task, "unpaid" and that you will not use the work for an unpaid one.
Record the date you sent it as `terms_sent` for that finalist. `build_briefs.py` will not build a
brief while it is null.

---

Hi {first_name},

Before the test task, the terms so you can decide with them in hand: the role pays {role_pay} a month, full time, about {role_hours} hours a week, starting {start}. This is not an offer yet and nothing here binds either of us; it is what the role is, in writing, before you spend time on the task.

{task_line}

{signoff}

---

Rules:

- The same numbers for every finalist. A pay line that differs by person leaks into how you read
  the work.
- "Not an offer yet" stays in. So does "nothing here binds either of us".
- No "we are talking to a few people", no count of finalists, nothing about the other candidates.
- If the candidate's ask is above what you wrote here, this message is where they find out, before
  the task, not after.
