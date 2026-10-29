# hire-reference-check

For one or two finalists, after the test task and before any offer: a 10 to 15 minute call guide built from the questions still open after the interviews and the work sample, for one or two referees the candidate approved (never the current employer), around "Would you hire this person again, and why?" and "Tell me about a time they had to handle difficult feedback." You name the approved referees in chat and approve the questions in chat; Claude records both with the date. After the calls, every answer is organised as Concrete example / Vague opinion / Follow-up in a summary per finalist and one board. One person's opinion is never a complete picture. You make every call; the assistant never contacts anyone.

Install: `npx skills add JayGPTPro/hiring-with-claude-code`

First command, from your `hiring/` folder, with the interview debriefs and the work-sample review in place: `Use the hire-reference-check skill for <name>. They approved these referees: <first name, role, where, dates>.`
