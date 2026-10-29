# Message drafts

`build_board.py` fills these from `out/scores.json` and writes one file per candidate to
`out/messages/<slug>-<status>.md`. The assistant never sends them. You read the draft, change
what you want, and send it yourself from your own email, LinkedIn or WhatsApp.

Placeholders: `[Name]` (first name), `[role]` (from criteria.md), `[what you sent]` ("your
message and your CV", or "your message" when there was no CV), `[questionnaire link]`, `[call link]`,
`[your name]`. Anything in brackets that the script cannot fill stays in brackets so you see it
before sending.

A draft is written once. A rebuild never touches a draft that is already in `out/messages/`, so your
edits stay, and it writes no draft for a message the dossier Log says you sent.

Two sentences are fixed and stay in every first reply: the notice that an AI assistant helps
organise the applications, a person makes every decision, and they can ask for a human re-read.
The invite to a call also carries the reference sentence: "Before an offer I will speak with one
or two people who worked with you; you will set those calls up."

Each section below is one template. The heading is the key the script looks for. Keep the
headings; edit the text as you like.

## late-reply-line

Sorry for the slow reply, it took me a few days to get through the applications.

## invite-questionnaire

Hi [Name],

Thank you for applying for the [role] role. I read [what you sent], and I would like to know more.

The next step is a short questionnaire. It asks for a few concrete examples of your work and how you see yourself across the areas of the role. It takes about 20 minutes: [questionnaire link]

One thing you should know: an AI assistant helps me organise the applications. A person makes every decision, and if you would like a human re-read of anything you sent, just say so.

[your name]

## invite-call

Hi [Name],

Thank you for applying for the [role] role. I read [what you sent], and I would like to talk.

Pick a time that works for you here: [call link]. It is a 30 minute video call. Bring one piece of work you are proud of, I will ask you to walk me through it on a shared screen.

Before an offer I will speak with one or two people who worked with you; you will set those calls up. Nothing to do now, I just want you to know how the process ends.

One more thing: an AI assistant helps me organise the applications. A person makes every decision, and if you would like a human re-read of anything you sent, just say so.

[your name]

## hold

Hi [Name],

Thank you for applying for the [role] role. I have read your application and I am keeping it. I am talking to a few people first and will come back to you within two weeks either way.

An AI assistant helps me organise the applications. A person makes every decision, and if you would like a human re-read of anything you sent, just say so.

[your name]

## decline

Hi [Name],

Thank you for taking the time to apply for the [role] role. I will not take your application further this time. If I need another person I will go back through the applications.

An AI assistant helped me organise the applications; I read yours and the decision is mine. If you would like a human re-read, just say so.

I wish you luck with your search.

[your name]

## out-of-budget

Hi [Name],

Thank you for applying for the [role] role. Your rate is above the budget I have for this position, so I will not take it further. If that changes I will reach out.

An AI assistant helps me organise the applications. This decision is about budget, and it is mine. If you would like a human re-read, just say so.

[your name]

## closing

Hi [Name],

Thank you again for applying for the [role] role. The role has been filled. If I need another person I will go back through the applications.

I wish you luck with your search.

[your name]
