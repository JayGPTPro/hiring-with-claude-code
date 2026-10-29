---
name: hire-first-month
description: 'From the offer call to day thirty for a founder hiring one remote person. Before the call: the offer letter and a contract checklist, worded for the structure the founder chose (contractor, employer of record or local entity; never assumed), with a not-legal-advice line. After the yes: the role scorecard becomes the onboarding plan (five tasks mapped by day 14, one AI workflow with human checks by day 60, SOP and handoff by day 90); a least-privilege access plan (personal accounts, Seller Central view-only until approved, no customer data early, two-factor); a two-week onboarding checklist; check-ins on day 7, 14 and 30 with a day-30 table (Expected result / Actual evidence / Missing training / Next action); the offboarding list. Use when the user says "I am about to make the offer", "offer letter", "they accepted", "they said yes", "first 30 days", "onboarding plan", "access plan", "Seller Central permissions", "day 30 check-in" or "offboarding". Never sends, pays, grants access or touches a calendar.'
---

# /hire-first-month

Two moments. **Before the offer call**, the letter is ready, so it goes out within the hour of a
verbal yes. **After the yes**, the same scorecard that chose the person plans their first ninety days
and tells both of you, at day 30, whether the role is working.

Claude writes files into `hiring/out/first-month/`. It never emails, messages, pays, creates a
calendar event, grants a permission or stores a login. You send the letter, sign, pay, click the
permissions and import the `.ics`. Most of what is here is practitioner consensus, not studies; where a
line is a heuristic it says so. Nothing here is legal advice. The check-ins look at the work and the
conditions for it, never at personality or protected traits.

## What you need

- `hiring/criteria.md` with the outcomes for the first ninety days: a list under a heading such as
  "Outcomes for the first 90 days" or "Results", each item starting "By day 14:", "By day 60:",
  "By day 90:". Numbered or bulleted, one line or wrapped. If none are found the script says so loudly
  and uses three defaults; write your own and rerun.
- The structure, chosen by the founder: `contractor`, `eor` (employer of record) or `entity` (a local
  company). **Ask; never assume.** It changes what the letter may promise.
- The agreed pay, the start date (a Monday is best), both time zones, who pays the transfer fee.
- Every system the person will touch, with the account it lives under. Optional: `task-log.md` with
  "## Five candidates for the day-14 map" (a numbered list), or `five_tasks` in the config.

## Files

```
hiring/first-month/config.json     the hire, dates, pay, raise, overlap, structure, systems
hiring/out/first-month/
  offer.md               before the call: your checklist, the dates, the letter (plan.py --offer)
  contract-checklist.md  the three structures and the clauses to tick, not legal advice (plan.py --offer)
  onboarding.md          the scorecard as the plan, the five task maps with dates, two weeks day by day
  access-plan.md         least privilege: the rules, the grid per system, the ladder, the log
  access.html            the grid as a page, with the offboarding checklist
  checkpoints.md         day 7, day 14, the day-30 check-in, day 60 and 90
  day-30.html            the day-30 check-in as a page you fill on the call
  checkpoints.ics        three all-day events; you import them
  silence.md             the one calm message and the ladder before it
  offboarding.md         the 24-hour routine, with the systems table
  phishing-talk.md       the five-line first security conversation
```

The script runs from `hiring/` or the folder above it, uses only the Python standard library, and
prints the scorecard it read, every date and each file it wrote. Pages carry a FICTIONAL DEMO badge
when `criteria.md` says so near the top. Every string from a file is escaped on the pages.

## Step 1. Config

Copy `templates/config.example.json` to `hiring/first-month/config.json` and fill it.

- **`structure`** has no default. Ask the founder; until it is set the offer is not written.
- **`pay`**: monthly, in `currency`; weekly for the first `weekly_weeks`, then monthly. `transfer_fee`
  is `founder`, `hire` or `split`; empty leaves a blank in the letter. `rail` names the service; check
  its live fees before the first payment. **`raise`** percentages are yours.
- **Systems**: one level string per system per phase, starting `None`, `View`, `Edit` or `Full`, then a
  colon and the detail. `never` is what the person never gets.
- **`day30_extra`** adds a row to the day-30 check-in, for example the open question from the
  hire-test-task Decision Challenge.
- **Dates**: day N is the start date plus N minus 1 days. A checkpoint on a weekend is held on the
  Monday after, with no note. A start that is not a Monday gets a note.

## Step 2. Before the offer call: the letter

When the founder says "I'm about to make the offer":

```
python3 <skill>/scripts/plan.py --offer
```

It writes only `offer.md` and `contract-checklist.md`, and refuses while `structure` is not set.
`offer.md` opens with the not-legal-advice line (check with a local adviser, or let an employer of
record write the contract), then your checklist for the call: verbal first, on video; the letter
within the hour; the signature before they resign; no bidding against a counter-offer; no system access
before the agreement and the IP assignment are signed. Then the dates it sets, then the letter.

- **Contractor**: deliverables (the scorecard outcomes), a monthly fee for the scope, availability
  ("you set your own hours", a window when you are reachable), other clients allowed with disclosure,
  deliverable reviews and notice, a rate review. No full-time hours, no probation, no raises.
- **Employer of record or entity**: full time, the overlap in both time zones, the daily report, the
  first term with reviews at 30, 60 and 90, the raise schedule with dates.

`contract-checklist.md` opens with the tension (full time, exclusive, fixed hours and core work is the
textbook employee profile) and the three structures, then the clauses to tick: IP assignment in the
present tense, no subcontracting without written approval, disclosure of other paid work, the reviews,
confidentiality, payment terms, personal credentials, termination that mirrors the offboarding. A
lawyer in each country reads the final draft.

## Step 3. After the yes: the scorecard becomes the plan

When the founder says the person accepted (start date and pay in hand):

```
python3 <skill>/scripts/plan.py
```

It writes the plan, the access plan and the check-ins. If `offer.md` is not there yet it writes it too
(when `structure` is set); an `offer.md` you already have is kept, so edits to a sent letter survive.

`onboarding.md` opens with the outcomes the person was chosen against, each with its date, what done
looks like and the checkpoint where it is checked. Nothing new is invented after the yes.

- **By day 14: five tasks mapped**, each with steps, inputs, time, what breaks when it is wrong, and
  whether a tool could help. The first map by Friday of week one, the other four across week two. At
  the day-14 call the two of you pick the task that becomes the day-60 workflow.
- **By day 60: one AI-assisted workflow with human checks, in use every week**, with a written check
  step for every run.
- **By day 90: the SOP and the handoff.** Someone else runs it once from the SOP alone.

Then two weeks day by day: two full weeks before real output; a short report at the end of each day
(did, problems, help needed, tomorrow), which is how async work runs, not surveillance; three calls in
week one; feedback on the onboarding on day five and day ten; and, said in words, that asking for help
is never punished.

## Step 4. Access, least privilege

`access-plan.md` and `access.html` carry the same grid: per system, the owner account, the login,
Week 1 (days 1 to 7), Month 1 (days 8 to 30), Month 3 (from day 31) and Never.

- **A personal account on every system.** Never a shared login, never the founder's.
- **Least privilege for the first task.** Mapping work needs reading.
- **Seller Central view-only until approved:** a secondary user on the hire's own work email. Edit
  arrives per task after the day-7 call. Never Administrator, banking, deposit, tax or account info.
- **No customer data early.** Orders shows buyer names and addresses, so it stays out of Week 1 and
  Month 1 and arrives in Month 3 only when the founder approves it. The script warns if it is earlier.
- **A password manager for every secret,** set up before the offer. **Two-factor on every login,** on an
  authenticator app. **No credentials in chat or email,** in either direction. AI tools work on exports
  and copies, never with a stored login or pasted customer names.
- **The first security conversation is the anti-phishing talk** (`phishing-talk.md`), on day one.
- **The access plan is the offboarding list:** the bottom of `access.html` is the same systems in revoke order.

## Step 5. Day 7, day 14 and the day-30 check-in

`checkpoints.md` and `checkpoints.ics`. Day 7: read the five daily reports in a row, check task map 1,
grant the Month 1 levels where the reports were clean, say what is held back and why. Day 14: read one
map cold, agree the day-60 workflow and where the person checks it, name what they own from Monday.
Import the `.ics` the day the offer is accepted; with no HR, the calendar entry is the HR.

Day 30 (`day-30.html`), one hour, both of you: did the work happen, what still needs training, which
expectations were unrealistic? Four columns: Expected result, Actual evidence, Missing training, Next
action. The rows come from the scorecard plus any `day30_extra`. Fill the evidence before the call.

Before any conclusion, three checks: were the expectations realistic (full speed takes about three
months), was the training given, were the conditions there (access, data, replies inside the overlap)?
Then: on track, say it and grant Month 3; a gap with a fixable cause, fix it this week with a dated next
action; a gap after all three checks, write it down with the evidence, tell the person the same day,
and agree what day 60 must show. The check-in never ends with an automatic "end it". Day 60 and day 90
use the same four columns against their outcomes.

## Step 6. Silence and offboarding

`silence.md`: silence is usually a skill gap or shame, not disrespect. Check in the day replies get
shorter; then one calm message with a reply-by date two working days out; pay to the day whatever
happens. `offboarding.md` exists before anyone needs it: revoke every login inside 24 hours (Seller
Central first), confirm deletion of local copies, collect the work, pay what is owed the same week.

## Self-check before you hand anything over

- The structure came from the founder; the letter's wording matches it, and `offer.md` carries the
  not-legal-advice line. Who pays the transfer fee is the founder's answer, not a default.
- `onboarding.md` opens with the scorecard read from `criteria.md` (whole outcomes, not cut lines), or
  the run printed a warning that it used defaults.
- The access grid: personal logins with two-factor, levels that start with None, View, Edit or Full, a
  Never line, Seller Central view-only in week one, no Orders before the approved step, no real credential.
- The day-30 check-in has the four columns, the three checks and no automatic "end it".
- `checkpoints.ics` has only the checkpoint events; nothing was added to any calendar.
- No long dashes, no local paths (`plan.py` checks both). Nothing was sent, signed, paid or granted.
