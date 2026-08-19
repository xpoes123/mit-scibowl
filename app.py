#!/usr/bin/env python3
"""MIT Science Bowl study tool — serves the flashcard app and proxies Claude.

Env: ANTHROPIC_API_KEY (required for /explain).
Run: uvicorn app:app --host 127.0.0.1 --port 7791
"""
import json
import os
from pathlib import Path

import anthropic
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

ROOT = Path(__file__).parent
QUESTIONS = json.loads((ROOT / "data" / "questions.json").read_text())
BY_ID = {q["id"]: q for q in QUESTIONS}
CACHE_FILE = ROOT / "data" / "explanations.json"
CACHE = json.loads(CACHE_FILE.read_text()) if CACHE_FILE.exists() else {}

MODEL = "claude-sonnet-5"
client = anthropic.Anthropic() if os.getenv("ANTHROPIC_API_KEY") else None

app = FastAPI(title="MIT SciBowl")


class ExplainReq(BaseModel):
    id: str


def coach_prompt(q):
    parts = [f"Category: {q['category']} | {q['kind']} | "
             f"{'multiple choice' if q['qtype']=='mc' else 'short answer'}",
             f"Question: {q['question']}"]
    if q["choices"]:
        parts += [f"  {k}) {v}" for k, v in q["choices"].items()]
    parts.append(f"Correct answer: {q['answer']}")
    return "\n".join(parts)


SYSTEM = (
    "You are an elite National Science Bowl coach. For the given question and its "
    "known answer, teach the competitor how to think about it FAST — Science Bowl "
    "gives ~5 seconds to buzz on tossups. In 3-5 tight sentences cover: (1) the "
    "recognition trigger — the few words that tell you what's being asked, (2) the "
    "fastest solution path or mental-math shortcut to the answer, (3) what to "
    "memorize cold so it's instant next time. Be concrete and terse. No preamble."
)


@app.post("/explain")
def explain(req: ExplainReq):
    q = BY_ID.get(req.id)
    if not q:
        raise HTTPException(404, "unknown question id")
    if req.id in CACHE:
        return {"explanation": CACHE[req.id], "cached": True}
    if client is None:
        raise HTTPException(503, "ANTHROPIC_API_KEY not set on server")
    msg = client.messages.create(
        model=MODEL, max_tokens=500, system=SYSTEM,
        messages=[{"role": "user", "content": coach_prompt(q)}],
    )
    text = "".join(b.text for b in msg.content if b.type == "text").strip()
    CACHE[req.id] = text
    CACHE_FILE.write_text(json.dumps(CACHE, ensure_ascii=False))
    return {"explanation": text, "cached": False}


@app.get("/questions.json")
def questions():
    return JSONResponse(QUESTIONS)


@app.get("/")
def index():
    return FileResponse(ROOT / "static" / "index.html")


app.mount("/", StaticFiles(directory=ROOT / "static"), name="static")
