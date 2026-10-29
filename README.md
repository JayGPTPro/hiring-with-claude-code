# Hiring with Claude Code

Five Claude Code skills for the part of hiring that starts once the applications are in.
Not how to find people. What to do with the pile: screen it, send one questionnaire, check the claims that
matter, run the interviews and learn from them, give the finalists a test task, call the references, decide,
and get the first thirty days right.

Built from one real search in October 2026: 81 applications, 22 questionnaires, 7 interviews,
4 paid test tasks, 1 hire, about ten minutes a day for two weeks. Then rebuilt against the research
on what predicts a good hire (structured interviews scored with anchors, work samples, structured
reference calls) and against what changed when both sides use AI. The examples and the demo in this repo
use invented people. The method is the real one, plus the parts I did not know the first time.

## Install

```
npx skills add JayGPTPro/hiring-with-claude-code
```

Or copy the `skills/` folders into your project's `.claude/skills/`.

Then make a `hiring/` folder, write `hiring/criteria.md` in your own words (three dated outcomes for the
first 90 days, the must-haves, the budget with the most you will ever pay, the rules for the assistant;
`skills/hire-applications/templates/criteria.md` is the shape), put the applications in `hiring/inbox/`, and
type the first prompt.

## The five skills, in the order you use them

| Skill | What it does | Start with |
|---|---|---|
| [hire-applications](skills/hire-applications/) | Strips identity first and scores each blind file in its own subagent, with a quote on every scored part and "Not shown / Ask" where the file is silent. Flags hidden text aimed at the model and never lets it move a score. A board for any number of applications, an Evidence Map per person (claim, evidence, what is missing, one question), a morning list and message drafts that keep your edits. Then the questionnaire step: one questionnaire as plain text for a Google Form, and the downloaded answers compared side by side, labelled SELF-RATINGS, NOT PERFORMANCE, with writing judged on three anchors | `/hire-applications` |
| [hire-interview](skills/hire-interview/) | The claim check first: only the job claims you name, checked against the candidate's own documents and public work sources, never a name search: Verified, Unverified or Clarification needed, each with one neutral question. Then one prep page (five core questions with 1 / 3 / 5 anchors written before the call, one tailored follow-up). After each call it converts the Meet or Zoom transcript, saves your score before Claude's analysis exists, and writes CANDIDATE_DEBRIEF.md, INTERVIEWER_COACH.md and a two-tab ledger | `Prep the interviews for this week.` |
| [hire-test-task](skills/hire-test-task/) | Terms in writing first, then one shared task for every finalist with a scoring guide locked before any work arrives. Goal-first briefs with the effort stated, and a fee when the task is long or uses your real material (a short task on made-up data can be unpaid, and then the work is never used), your rating before Claude's notes, a walkthrough of one decision, a Decision Challenge on your sealed preference, and the offer, runner-up and closing drafts (the last two wait until the hire has signed) | `Test task for my finalists: write the terms and the briefs.` |
| [hire-reference-check](skills/hire-reference-check/) | For one or two finalists, after the test task and before any offer. A 10 to 15 minute call guide from the questions still open, for referees the candidate approved, never the current employer. You approve the questions in the chat. After the calls every answer is sorted into Concrete example / Vague opinion / Follow-up | `Reference calls for <name>: build the call guide from what is still open.` |
| [hire-first-month](skills/hire-first-month/) | Before the offer call: the letter, worded for the structure you chose (employee or contractor), and a contract checklist (not legal advice). After the yes: the scorecard becomes the plan (five tasks mapped by day 14, one AI workflow with human checks by day 60, the SOP and handoff by day 90), access with least privilege (view-only first, no customer data in week one, a password manager, two-factor authentication), day 7, 14 and 30 check-ins in a calendar file, the silence message and the offboarding list | `They said yes. Build the access plan and the first 30 days for <name>.` |

## The prompts, word for word

Short on purpose. The skills carry the method; the prompt only has to point. `<name>` is the candidate's
name as it appears in their dossier. The lesson's longer prompts are under the episode.

1. **Screen:** `Screen the applications in hiring/inbox against hiring/criteria.md and build the candidate board.`
2. **Questionnaire:** `Use the hire-applications skill's questionnaire step: build one questionnaire from criteria.md for my shortlist, as plain text for a Google Form.` When the answers are in: `I downloaded the answers from my Google Form. Compare everyone side by side and score the writing.`
3. **Claim check:** `Use the hire-interview skill's claim check for <name>. Check only these job claims: <claim 1>, <claim 2>.`
4. **Interviews:** `Prep the interviews for this week.` After each call: `Debrief the interview with <name>. The transcript is in this folder: <file>.` After a few calls: `How did I interview?`
5. **Test task:** `Test task for my finalists: write the terms, the briefs and the scoring guide.` When the work is in: `Review the submissions.`
6. **References:** `Reference calls for <name>: build the call guide from what is still open.` After each call: `Write up the reference call with <name>.`
7. **Decide:** `I'd hire <name> because <two sentences>. Seal that, then challenge my choice.`
8. **The offer:** `I'm about to make the offer to <name>. Write the letter and the contract checklist.`
9. **After the yes:** `They said yes. Build the access plan and the first 30 days for <name>.`

And every morning during a search: `What changed since yesterday? Update the board and show what needs my decision.`

## The rules the skills will not break

1. **The assistant never contacts anyone.** Not a candidate, not a referee, not an employer. It writes drafts
   to files; you send, you call, you pay, you grant access.
2. **Applications are untrusted data.** A CV, a message, a questionnaire answer, a transcript or a submission
   is a document to evaluate, never instructions to follow. Hidden text aimed at the model is flagged and
   never moves a score. Every page escapes what candidates wrote.
3. **A person decides.** Every status is a suggestion in a file. Your own score is written before Claude's
   analysis, and your preference is sealed before Claude's challenge.
4. **No protected traits.** Nothing about age, origin, gender, health, family, religion, politics or
   appearance, and nothing inferred about personality, motivation or honesty. The scoring never sees a name.
5. **Scores organise evidence; they are not predictions.** Every score rests on a quote or says unknown,
   self-ratings are not evidence, a thin file says "Insufficient evidence", and a total is never a reason to
   stop thinking.

## The folder every skill reads and writes

```
hiring/
  criteria.md                 role, 90-day outcomes, must-haves, budget, rules
  control-cv.txt              a fictional application for this role with its expected band (Claude writes it)
  task-log.md                 optional: your repeat tasks; hire-first-month reads the five to map
  inbox/                      <slug>.md (the message with a short header) and <slug>-cv.txt
  questionnaire/              QUESTIONNAIRE.md, responses.csv (your Google Form download), writing.json,
                              timeline.json
  challenge/                  config.json, core-task.md, SCORING-GUIDE.md, briefs/, submissions/,
                              walkthroughs/, review.json, decision-challenge.json, REVIEW.html,
                              DECISION-CHALLENGE.html
  first-month/                config.json
  out/
    applications.json         every application, parsed; COVERAGE.md says what to fix
    blind/                    redacted copies the scoring reads; map.json and HIDDEN.md stay local
    scores.json               the judged scores
    candidates/<slug>.md      the dossier with its Evidence Map; later steps append their section
    evidence/<slug>.html      the Evidence Map page
    board.html  board.csv  SUMMARY.md  MORNING.md
    questionnaire/            COMPARE.html, <slug>-section.md
    verification/             the claim check: <slug>.json, .md and .html per candidate, SUMMARY.html
    interviews/               prep.json, PREP.html, transcripts/, LEDGER.html, LEDGER.md, and per call
                              <slug>/FOUNDER_SCORES.md, CANDIDATE_DEBRIEF.md, INTERVIEWER_COACH.md
    references/               referees, open questions, call guides, notes, summaries, REFERENCES.html
    DECISION.md               the optional decision table
    first-month/              offer, contract checklist, access plan and page, onboarding,
                              checkpoints and day-30 page, checkpoints.ics, silence, offboarding
    messages/                 drafts, never sent by the assistant
```

## Scripts and tests

Every script is Python 3 standard library, runs from your `hiring/` folder or from the folder above it,
makes no network calls, and prints what it wrote. The judgment (scoring an example, reading a transcript,
writing a brief, organising a reference answer) is Claude's, guided by the rubric in each SKILL.md.

`python3 tests/run_tests.py` builds a small fictional project in a temporary folder (one strong application,
one thin one, one with hidden text aimed at the model, one with script tags in its name and message), runs
every script of all five skills from inside `hiring/` and from the folder above it, and prints a PASS/FAIL
table. `tests/LAST-RUN.txt` holds the last result.

## Licence

MIT. Use it, change it, teach it. If it helped you hire someone, tell me.
