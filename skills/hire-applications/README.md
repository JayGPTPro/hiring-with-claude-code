# hire-applications

A folder of applications in, a board you can work from out, then one questionnaire for the shortlist.

A script strips name, contact details, birth year, age, nationality and family status first (only the identifying value, never a line of experience). Each blind file is scored in its own subagent that sees only that file, criteria.md and the rubric, with a quote on every scored part. What the file does not show is "Not shown / Ask", never a 0. A control CV written for your role rides in every batch, and a second pass flags any total that moves more than five points or changes band. Each dossier gets an Evidence Map: per must-have, the claim, the quoted evidence, what is missing and one question. Out come `board.html`, an Evidence Map page per candidate, `MORNING.md` (what changed, what waits for you, who has waited more than five days) and message drafts that a rebuild never overwrites. Hidden text aimed at the model is flagged and never moves a score.

The questionnaire step writes one questionnaire from `criteria.md` as plain text you paste into a Google Form: self-ratings per area, the two strongest areas with one example each, one short situation from the job, practical fit. When the answers are in, it reads the Google Forms CSV export as downloaded, puts everyone side by side under SELF-RATINGS, NOT PERFORMANCE with each example beside its number, judges the writing on three anchors, scores the examples into TRACK, adds a Questionnaire section to each dossier and drafts the "what happens next, and when" message.

The assistant never sends anything.

Install: `npx skills add JayGPTPro/hiring-with-claude-code`. The scripts land in `.claude/skills/hire-applications/scripts/`.

First prompt, from the folder that holds `hiring/` with `criteria.md` and `inbox/` filled in: `/hire-applications`

Every morning after that: `What changed since yesterday? Update the board and show what needs my decision.`
