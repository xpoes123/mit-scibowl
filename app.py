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
PLACEMENT_FILE = ROOT / "data" / "placement-math.json"
LESSONS_FILE = ROOT / "data" / "lessons.json"
BIO_FILE = ROOT / "data" / "bio-topics.json"
PROFILE_FILE = ROOT / "data" / "profile.md"
PROFILE = PROFILE_FILE.read_text() if PROFILE_FILE.exists() else ""

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
    "memorize cold so it's instant next time. Be concrete and terse. No preamble. "
    "Format with markdown (short **bold** lead-ins, a bullet list if it helps) and "
    "write ALL math as LaTeX in $...$ (inline) or $$...$$ (display) so it renders."
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


ASK_SYSTEM = (
    "You are David's personal Science Bowl coach, embedded as a help assistant inside "
    "his study app. Here is everything you know about him — tailor every answer to it:\n\n"
    + PROFILE +
    "\n\nAnswer his question directly and concisely. Always give the WHY / the intuition, "
    "not just the answer. Write math as LaTeX ($...$ inline, $$...$$ display). Use short "
    "paragraphs and bullets — never a wall of text. If page context is provided, he is "
    "probably asking about that; use it."
)


class AskReq(BaseModel):
    messages: list[dict]  # [{role: 'user'|'assistant', content: str}]
    context: str | None = None


@app.post("/ask")
def ask(req: AskReq):
    if client is None:
        raise HTTPException(503, "ANTHROPIC_API_KEY not set on server")
    system = ASK_SYSTEM
    if req.context:
        system += f"\n\n## What David is currently looking at\n{req.context[:6000]}"
    msgs = [{"role": m["role"], "content": m["content"]}
            for m in req.messages if m.get("content")][-20:]
    while msgs and msgs[0]["role"] != "user":  # Anthropic requires the first turn to be user
        msgs.pop(0)
    if not msgs:
        raise HTTPException(400, "no message")
    resp = client.messages.create(
        model=MODEL, max_tokens=1024, system=system, messages=msgs)
    text = "".join(b.text for b in resp.content if b.type == "text").strip()
    return {"reply": text}


@app.get("/questions.json")
def questions():
    return JSONResponse(QUESTIONS)


@app.get("/placement-math.json")
def placement():
    if not PLACEMENT_FILE.exists():
        raise HTTPException(404, "placement test not generated")
    return JSONResponse(json.loads(PLACEMENT_FILE.read_text()))


@app.get("/lessons.json")
def lessons():
    if not LESSONS_FILE.exists():
        raise HTTPException(404, "lessons not generated")
    return JSONResponse(json.loads(LESSONS_FILE.read_text()))


@app.get("/bio-topics.json")
def bio_topics():
    if not BIO_FILE.exists():
        raise HTTPException(404, "bio topics not generated")
    return JSONResponse(json.loads(BIO_FILE.read_text()))


ANALYZE_SYSTEM = (
    "You are an elite Science Bowl math coach analyzing a student's placement-test "
    "results. For each item you get the topic, the question, the correct answer, the "
    "student's answer, whether they got it right, how many seconds they took, and the "
    "work they wrote out. Diagnose their skill: identify weak topics (wrong answers), "
    "shaky-but-correct topics (right but slow or messy work), and misconceptions "
    "visible in the written work — quote the specific wrong step. Speed matters: "
    "Science Bowl gives ~5s to buzz, so flag topics where they're accurate but slow. "
    "Then write a focused, personalized study plan in markdown: start with a 2-3 "
    "sentence diagnosis, then a prioritized list of the weakest/highest-leverage "
    "topics to drill (most urgent first) with the specific sub-skill to fix and why, "
    "then a concrete 4-day schedule weighted to their gaps. Reference their actual "
    "mistakes. Be specific and terse — no filler."
)


class TestResult(BaseModel):
    results: list[dict]


@app.post("/analyze-test")
def analyze_test(req: TestResult):
    if client is None:
        raise HTTPException(503, "ANTHROPIC_API_KEY not set on server")
    lines = []
    for i, r in enumerate(req.results, 1):
        q = BY_ID.get(r.get("id"), {})
        lines.append(
            f"--- Item {i} [{r.get('topic','?')}] ---\n"
            f"Question: {q.get('question','(missing)')}\n"
            f"Correct answer: {q.get('answer','?')}\n"
            f"Student answer: {r.get('userAnswer','(blank)')}\n"
            f"Got it right: {r.get('correct')}\n"
            f"Time: {r.get('seconds','?')}s\n"
            f"Their work: {r.get('work','(none written)')}"
        )
    msg = client.messages.create(
        model=MODEL, max_tokens=1800, system=ANALYZE_SYSTEM,
        messages=[{"role": "user", "content": "\n\n".join(lines)}],
    )
    text = "".join(b.text for b in msg.content if b.type == "text").strip()
    return {"plan": text}


@app.get("/")
def index():
    return FileResponse(ROOT / "static" / "index.html")


app.mount("/", StaticFiles(directory=ROOT / "static"), name="static")
