# Demo video script (2–3 minutes)

Record at 1440×900, browser zoom 100 %, using the production site. Wake the Render instance first (open `/api/v1/health`).
Use only `sample_data/` files.

| Time | Screen | Say |
|---|---|---|
| 0:00–0:15 | Landing page | "StudyPilot AI lets students study from their own course materials, with answers they can verify." |
| 0:15–0:30 | Sign in → Dashboard (empty) | "Supabase Auth; every user's data is isolated by Postgres row-level security." |
| 0:30–0:55 | Create *Database Systems* workspace, drag in `database-systems-week3.md` + a PDF; status goes Processing → Ready | "Files are validated, stored privately, split into chunks and embedded with Gemini into pgvector." |
| 0:55–1:30 | AI Chat: *"Why is Enrolment not in second normal form?"* → click `[S1]`, show source card with page. Then *"Who won the 2018 World Cup?"* | "Every answer cites the exact passage. Citations the model invents are rejected by the backend — and when the notes don't cover a question, it says so instead of guessing." |
| 1:30–1:50 | Document summary | "Long documents are summarised section by section, then combined, and cached." |
| 1:50–2:20 | Quiz Studio: 5 questions, mixed types → answer → results with explanation + source | "The model's JSON is validated before it's saved; grading is automatic and links back to the material." |
| 2:20–2:35 | Flashcards: flip, Mastered | "Flashcards track mastery and review history." |
| 2:35–2:50 | Dashboard + Learning progress (charts, AI usage) | "All numbers come from the database, including AI usage against a daily quota." |
| 2:50–3:00 | GitHub README (architecture diagram, CI badge/tests) | "React, FastAPI, Supabase, pgvector and Gemini — with automated tests and CI." |
