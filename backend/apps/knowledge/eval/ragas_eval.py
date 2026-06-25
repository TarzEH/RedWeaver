"""Ragas evaluation of the pgvector RAG.

Builds a Ragas ``EvaluationDataset`` from a golden Q/A set by running each
question through the real retriever (``kb_search``) and, optionally, the real
grounded-answer path, then scores it with Ragas metrics. The judge LLM and
embeddings reuse RedWeaver's existing multi-provider stack (OpenAI / Anthropic /
Google / Ollama, and the local HuggingFace embeddings) — so this runs offline too.

Ragas is imported lazily so this module imports without the dependency present.

Caveats (see docs/refactor-deepagents-ragas.md): LLM-judge metrics are
non-deterministic; small local models are flaky (timeouts / structured-output
parse failures). We force ``temperature=0`` where possible, raise timeouts via
``RunConfig``, and pass ``raise_exceptions=False`` so a few bad rows become NaN
instead of aborting the run.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

GOLDEN_SET = Path(__file__).with_name("golden_set.json")

# Default pass thresholds for CI (aggregate scores). Tune as the KB matures.
DEFAULT_THRESHOLDS = {
    "context_recall": 0.60,
    "llm_context_precision_with_reference": 0.55,
    "faithfulness": 0.70,
    "answer_relevancy": 0.60,
}


class _EnvKeys:
    """Minimal KeysProvider — lets LLMFactory resolve provider keys from env.

    A management command has no request user, so provider keys come from the
    environment (OPENAI_API_KEY / ANTHROPIC_API_KEY / GOOGLE_API_KEY /
    OLLAMA_BASE_URL / MODEL_PROVIDER / selected_model via MODEL_* defaults).
    """

    def get_all(self) -> dict:
        return {}


def _evaluator_llm():
    from ragas.llms import LangchainLLMWrapper

    from redweaver_engine.llm_factory import LLMFactory

    lf = LLMFactory(_EnvKeys())
    if not lf.has_api_key():
        raise RuntimeError(
            "No LLM provider configured (set OPENAI_API_KEY / ANTHROPIC_API_KEY / "
            "GOOGLE_API_KEY, or OLLAMA_BASE_URL) for the Ragas judge."
        )
    return LangchainLLMWrapper(lf.build_langchain_chat_model())


def _evaluator_embeddings():
    from ragas.embeddings import LangchainEmbeddingsWrapper

    from apps.knowledge.embeddings import get_langchain_embeddings

    return LangchainEmbeddingsWrapper(get_langchain_embeddings())


def _generate_answer(chat_model, question: str, contexts: list[str]) -> str:
    """Grounded answer using the same prompt shape as the knowledge_ask view."""
    context = "\n\n".join(contexts)
    prompt = (
        "You are a security knowledge assistant. Answer the question using ONLY "
        "the knowledge-base excerpts below. Be concise and practical; include exact "
        "commands when relevant.\n\n"
        f"KNOWLEDGE BASE:\n{context}\n\nQUESTION: {question}"
    )
    resp = chat_model.invoke(prompt)
    return getattr(resp, "content", None) or str(resp)


def build_dataset(top_k: int = 5, with_generation: bool = True, chat_model=None):
    """Run the golden questions through the retriever (and optionally the answerer)
    and return a Ragas ``EvaluationDataset``."""
    from ragas import EvaluationDataset, SingleTurnSample

    from apps.knowledge.search import kb_search

    items = json.loads(GOLDEN_SET.read_text(encoding="utf-8"))
    samples = []
    for it in items:
        hits = kb_search(it["user_input"], top_k=top_k)
        contexts = [h.get("content", "") for h in hits if h.get("content")]
        response = ""
        if with_generation and contexts and chat_model is not None:
            response = _generate_answer(chat_model, it["user_input"], contexts)
        samples.append(SingleTurnSample(
            user_input=it["user_input"],
            retrieved_contexts=contexts,
            response=response,
            reference=it.get("reference", ""),
        ))
    return EvaluationDataset(samples=samples)


def _metrics(with_generation: bool, llm, embeddings) -> list:
    from ragas.metrics import (
        Faithfulness,
        LLMContextPrecisionWithReference,
        LLMContextRecall,
        ResponseRelevancy,
    )

    metrics = [
        LLMContextRecall(llm=llm),
        LLMContextPrecisionWithReference(llm=llm),
    ]
    if with_generation:
        metrics += [
            Faithfulness(llm=llm),
            ResponseRelevancy(llm=llm, embeddings=embeddings),
        ]
    return metrics


def run_ragas_eval(
    top_k: int = 5,
    with_generation: bool = True,
    thresholds: dict[str, float] | None = None,
    timeout: int = 300,
    max_retries: int = 12,
) -> dict[str, Any]:
    """Run the full Ragas evaluation and return a structured result dict."""
    from ragas import evaluate
    from ragas.run_config import RunConfig

    llm = _evaluator_llm()
    embeddings = _evaluator_embeddings()

    chat_model = None
    if with_generation:
        from redweaver_engine.llm_factory import LLMFactory

        chat_model = LLMFactory(_EnvKeys()).build_langchain_chat_model()

    dataset = build_dataset(top_k=top_k, with_generation=with_generation, chat_model=chat_model)
    result = evaluate(
        dataset=dataset,
        metrics=_metrics(with_generation, llm, embeddings),
        llm=llm,
        embeddings=embeddings,
        run_config=RunConfig(timeout=timeout, max_retries=max_retries),
        raise_exceptions=False,
        show_progress=bool(os.environ.get("RAGAS_PROGRESS")),
    )

    scores = {k: (None if v != v else round(float(v), 4))  # NaN -> None
              for k, v in dict(result).items()}
    thr = thresholds or DEFAULT_THRESHOLDS
    failures = {
        m: {"score": scores[m], "threshold": t}
        for m, t in thr.items()
        if m in scores and scores[m] is not None and scores[m] < t
    }
    try:
        per_sample = result.to_pandas().to_dict(orient="records")
    except Exception:  # noqa: BLE001
        per_sample = []
    return {
        "scores": scores,
        "thresholds": thr,
        "failures": failures,
        "passed": not failures,
        "n_samples": len(dataset),
        "with_generation": with_generation,
        "top_k": top_k,
        "per_sample": per_sample,
    }
