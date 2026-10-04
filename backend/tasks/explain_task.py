"""
Celery task: write one design's explanation. [2026-10-05].

The explanation is the one long model answer — 35–90 s measured on a composed
board — and it used to be written inside POST /design/generate, which kept the
whole design waiting behind it. It is now queued here and read back through
GET /design/{id}/explanation. The task returns the text or the reason there is
none; it never raises, so a failure is a result the route can show.
"""

from __future__ import annotations

from worker import app as celery_app


@celery_app.task(bind=True, name="tasks.explain_task.explain_design")
def explain_design(self, ir_json: dict) -> dict:
    """{status: written, explanation} or {status: failed, error}."""
    import anthropic

    from ai.explainer import ExplanationEngine
    from core.config import settings
    from core.ir_schema import CircuitIR
    from core.ir_validator import validate_ir

    self.update_state(state="STARTED")
    try:
        ir = CircuitIR.model_validate(ir_json)
        text = ExplanationEngine().explain(ir, validate_ir(ir))
    except anthropic.APITimeoutError:
        return {"status": "failed", "explanation": "",
                "error": f"the explanation timed out after {settings.ai_explainer_timeout_seconds:.0f} s "
                         f"({settings.ai_model})"}
    except Exception as exc:  # noqa: BLE001 — a result, not a crash: the design is already built
        return {"status": "failed", "explanation": "",
                "error": f"the explanation could not be written: {type(exc).__name__}: {str(exc)[:200]}"}
    if not text.strip():
        return {"status": "failed", "explanation": "", "error": "the model returned no text"}
    return {"status": "written", "explanation": text, "error": None}
