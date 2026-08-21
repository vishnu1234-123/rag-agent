"""
FastAPI backend for FilingsIQ — thin HTTP wrapper over the existing pipeline.
"""
from dataclasses import asdict, is_dataclass
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from filingsiq.pipeline.pipeline import answer as run_pipeline
from filingsiq.synthesize.synthesizer import synthesize

app = FastAPI(title="FilingsIQ API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class QueryRequest(BaseModel):
    question: str


def _serialize(obj):
    if is_dataclass(obj):
        return asdict(obj)
    return obj


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/query")
def query(req: QueryRequest):
    q = (req.question or "").strip()
    if not q:
        raise HTTPException(status_code=400, detail="question must not be empty")
    try:
        plan, nums, proses = run_pipeline(q)
        result = synthesize(plan, nums, proses)
    except Exception as e:
        raise HTTPException(status_code=500,
                            detail=f"pipeline error: {type(e).__name__}")
    return _serialize(result)
