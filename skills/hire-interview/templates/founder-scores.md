# Your scoring sheet: {name}

<!-- demo -->

Your own score for each question, 1 to 5 against the anchors on the prep page, with one line of evidence. Write it right after the call (or question by question during it), before you read any analysis. `scoresheet.py` saves a fingerprint of this sheet and only then creates CANDIDATE_DEBRIEF.md for Claude's analysis.

- Interview: {when}
- Interviewer: {interviewer}
- Written: [date and time, before reading any analysis]

## Your scoring sheet

| # | Question | Your score | One line of evidence (what they said or showed, with the minute) |
|---|---|---|---|
{rows}

Score 1 to 5, or "not asked". A question you did not ask is unknown, not the candidate's weakness, and it is left out of the total.
