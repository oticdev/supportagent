"""
Evaluation runner.

Runs all (or a subset of) golden dataset cases through the live agent,
judges each response, aggregates scores, and stores results in the DB.

Usage:
    # Run all cases
    results = await run_eval()

    # Run only escalation cases
    results = await run_eval(tags=["escalation"])
"""

import asyncio
import logging
from dataclasses import dataclass

from agent import orchestrator
from evals.golden_dataset import GOLDEN_DATASET, EvalCase
from evals.judge import judge, JudgeResult
from db import get_pool

logger = logging.getLogger(__name__)


@dataclass
class EvalSummary:
    total: int
    passed: int
    failed: int
    pass_rate: float
    route_accuracy: float
    avg_accuracy: float
    avg_helpfulness: float
    avg_tone: float
    avg_safety: float
    avg_overall: float
    results: list[dict]

    def to_dict(self) -> dict:
        return {
            "total": self.total,
            "passed": self.passed,
            "failed": self.failed,
            "pass_rate": round(self.pass_rate, 3),
            "route_accuracy": round(self.route_accuracy, 3),
            "avg_scores": {
                "accuracy": round(self.avg_accuracy, 2),
                "helpfulness": round(self.avg_helpfulness, 2),
                "tone": round(self.avg_tone, 2),
                "safety": round(self.avg_safety, 2),
                "overall": round(self.avg_overall, 2),
            },
            "results": self.results,
        }


async def _run_case(case: EvalCase) -> JudgeResult:
    """Run the agent on one case and judge the result."""
    logger.info("Eval: running case %s — %r", case.id, case.query[:60])
    try:
        result = await orchestrator.run(
            query=case.query,
            conversation_history=None,
            conversation_id=f"eval-{case.id}",
            mode="chat",
        )
        response = result["response"]
        actual_route = result["route"]
    except Exception as exc:
        logger.error("Agent failed for case %s: %s", case.id, exc)
        response = f"[Agent error: {exc}]"
        actual_route = "ERROR"

    return await judge(case, response, actual_route)


async def run_eval(tags: list[str] | None = None) -> EvalSummary:
    """
    Run the full evaluation suite (or a tag-filtered subset) and return an EvalSummary.
    Results are persisted to the eval_runs table in Postgres.
    """
    cases = GOLDEN_DATASET
    if tags:
        cases = [c for c in cases if any(t in c.tags for t in tags)]

    logger.info("Starting eval run: %d cases", len(cases))

    # Run all cases concurrently (with a semaphore to avoid hammering the API)
    sem = asyncio.Semaphore(3)

    async def bounded(case: EvalCase) -> JudgeResult:
        async with sem:
            return await _run_case(case)

    judgements: list[JudgeResult] = await asyncio.gather(*[bounded(c) for c in cases])

    # Aggregate
    total = len(judgements)
    passed = sum(1 for j in judgements if j.passed)
    route_correct = sum(1 for j in judgements if j.route_correct)

    summary = EvalSummary(
        total=total,
        passed=passed,
        failed=total - passed,
        pass_rate=passed / total if total else 0,
        route_accuracy=route_correct / total if total else 0,
        avg_accuracy=sum(j.accuracy for j in judgements) / total if total else 0,
        avg_helpfulness=sum(j.helpfulness for j in judgements) / total if total else 0,
        avg_tone=sum(j.tone for j in judgements) / total if total else 0,
        avg_safety=sum(j.safety for j in judgements) / total if total else 0,
        avg_overall=sum(j.overall for j in judgements) / total if total else 0,
        results=[j.to_dict() for j in judgements],
    )

    # Persist to DB
    await _save_eval_run(summary, tags)

    logger.info(
        "Eval complete: %d/%d passed (%.0f%%) | route accuracy %.0f%% | avg overall %.2f/5",
        passed, total, summary.pass_rate * 100,
        summary.route_accuracy * 100, summary.avg_overall,
    )

    return summary


async def _save_eval_run(summary: EvalSummary, tags: list[str] | None):
    import json
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO eval_runs
                (total, passed, failed, pass_rate, route_accuracy,
                 avg_accuracy, avg_helpfulness, avg_tone, avg_safety, avg_overall,
                 tags, results)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12::jsonb)
            """,
            summary.total, summary.passed, summary.failed,
            summary.pass_rate, summary.route_accuracy,
            summary.avg_accuracy, summary.avg_helpfulness,
            summary.avg_tone, summary.avg_safety, summary.avg_overall,
            tags or [],
            json.dumps(summary.results),
        )
