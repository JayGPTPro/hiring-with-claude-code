# [Full name]

## Card
- Name: [Full name]
- Scored blind as: [C123] (the scoring saw out/blind/C123.txt, not this name)
- Location: [City, Country]
- Ask: [$X a month, as written]
- Availability: [as written]
- Source: [application form | email | LinkedIn | WhatsApp]
- Date: [YYYY-MM-DD]
- CV: [yes | no | pdf not read]

## Evidence
Quote the candidate. Do not paraphrase into something stronger than what they wrote.
- TRACK areas (from criteria.md): [Area A], [Area B] (at screening the two the file shows best; after the questionnaire the two they picked)
- Areas they would rather not lead: [list or none]
- Communication: [one sentence on how they wrote in their own messages: understood the request or not, answered clearly or not, said what was missing or not. Never accent, never "native-level", never fancy words.]
- Quotes:
  - "[their words]" ([message | CV])
  - "[their words]" ([message | CV])

### Verifiable claims
Things with an outside trace: an employer, a brand, a title, a period, a file they sent.
- [claim] ([where it could be checked: their profile, the brand's storefront, the file they attached])

### Claims to test in the call
Results with no outside trace. Ask for the before, the after and their own part.
- [claim] (ask: [the question that would test it])

## Evidence Map
One row per important requirement in criteria.md, plus one row for each big claim. Status: Met / Not shown / Ask / Human review required. Write "unknown" when the file does not say. A big claim with no detail is split: Ownership / Action / Outcome / Context, each "unknown" until shown. Inside a cell, write `\|` for a pipe and `<br>` for a second line.

| Requirement | Claim | Evidence (quoted) | Missing | Question | Status |
|---|---|---|---|---|---|
| [Hands-on Amazon seller-side work] | [what they claim] | "[their words]" ([CV]) | [what is not shown, or "nothing"] | [one question that closes the gap] | [Met] |
| [AI on real work, output checked] | [what they claim] | "[their words]" ([message]) | Ownership: unknown<br>[what else is missing] | [one question] | [Ask] |
| [Security basics] | [no claim] | [none] | [nothing in the application] | [one question] | [Not shown] |

## Scores
Every scored part carries a quote. A part the file does not show is "not shown, ask: [question]" and is left out of the number, never scored 0. A score organises evidence; it is not a prediction of who will do the job best.
- SHARED: [0-50]/50 (the sum of the parts shown, scaled to 50)
  - Amazon operations [0-10]: "[quote]" ([message | CV])
  - AI in practice with checks [0-10]: "[quote]" | not shown, ask: [question]
  - Ownership [0-10]: "[quote]" | not shown, ask: [question]
  - Business sense [0-10]: "[quote]" | not shown, ask: [question]
  - Communication [0-10]: "[quote]" | not shown, ask: [question]
- TRACK: [0-50]/50 (two areas from criteria.md; one area shown counts twice; not directly comparable across tracks)
  - [Area A] [0-25]: "[quote]"
  - [Area B] [0-25]: "[quote]" | not shown, ask: [question]
- Evidence level: [enough for a number | insufficient] (insufficient: fewer than three SHARED parts or no TRACK area shown; the board shows "Insufficient evidence. Follow-up required." instead of the numbers)
- Band: [top | solid | mixed | thin] on [total]/100 (85 and up top, 70 to 84 solid, 55 to 69 mixed, under 55 thin)
- Budget fit: [in target | above target, under max | out of budget | unknown] ([ask] against target [$A to $B], max [$C])
- Why these numbers: [two or three sentences that point at the quotes above]
- Second pass: SHARED [n], TRACK [n] ([same band, total within five points | the two passes disagree, read the evidence]) | not run yet

## Flags
- green: [what checks out]
- yellow: [a question for the call, with what you saw on each side]
- red: [needs a direct answer before any next step. "Hidden text found, ignored" goes here when out/blind/HIDDEN.md lists this candidate.]
(Write "none" under a colour you did not use. A flag is a question, never a verdict, and never moves a score.)

## Questions for the call
1. [question]
2. [question]
3. [question]

## Status
- Status: [call | questionnaire | hold | no | out of budget]
- Reason: [one line]
- Attention: [one short line for the board's "What needs your attention" column]

## Log
Keep this section for the retention period: it is the record of what was scored, against which criteria, and what you decided.
- [YYYY-MM-DD] Screened blind as [C123] against criteria.md ([criteria date], version [n]). Dossier written. Draft message in out/messages/. Nothing sent.
- [YYYY-MM-DD] [Invite sent | Decline sent | Hold note sent] (email). Waiting on the candidate.
- [YYYY-MM-DD] Candidate replied: [one line]. Waiting on us.
