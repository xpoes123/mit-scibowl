# MIT SciBowl Trainer

Personal Science Bowl trainer built from 3 years of MIT HS Invitational packets
(2023–2025). **1,049 questions** in Chemistry / Biology / Math. Live at
**https://scibowl.djiang.xyz**.

## Features
- **Flashcards** — reveal answer, self-grade (got-it/missed → localStorage), filter by subject/year/type/set.
- **Buzz Trainer** — question reveals word-by-word (speed slider); hit `space` to *buzz* and it stops + shows the answer so you check if you'd have had it in time. Optional browser text-to-speech.
- **Explain approach** — asks Claude how to recognize + answer the question fast (server-side, cached).
- **Study Plan** — the 4-day high-leverage plan (`static/study-plan.md`).

## Data
`parse.py` turns `pdfs/*.pdf` → `data/questions.json` via `pdftotext -layout` +
regex. Keeps only Chemistry/Biology/Math. Re-run with `python parse.py`.
Note: complex math notation (superscripts/fractions) flattens in pdftotext —
the questions' own "(read: …)" glosses recover the meaning. 36 image-dependent
questions are flagged `visual:true` and hidden by default.

## Run locally
```
pip install -r requirements.txt
ANTHROPIC_API_KEY=sk-... uvicorn app:app --port 7792
```

## Deploy
See `DEPLOY.md`. Pull-to-deploy on the VPS; systemd unit `mit-scibowl` on
`127.0.0.1:7792` behind Caddy.
