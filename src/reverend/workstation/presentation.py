"""Bounded presentation data shared by chat, history and source drawers."""
from __future__ import annotations


def source_metadata(source: dict, index: int) -> dict:
    return {
        **{
            key:value
            for key,value in source.items()
            if key!='content' and not str(key).startswith('_')
        },
        'excerpt':str(source.get('content',''))[:1400],
        'citation_label':str(source.get('citation_label',f'K{index}')),
    }


def _compact(values: dict) -> dict:
    return {
        key:value for key,value in values.items()
        if value is not None and value != "" and value != [] and value != {}
    }


def response_details(metadata: dict) -> dict:
    """Safe normalized observability without prompts, source bodies, or reasoning text."""
    if not isinstance(metadata, dict):
        raise ValueError("Response metadata must be an object")
    routing=metadata.get("routing") if isinstance(metadata.get("routing"),dict) else {}
    verification=metadata.get("verification") if isinstance(metadata.get("verification"),dict) else {}
    agent=metadata.get("agent_loop") if isinstance(metadata.get("agent_loop"),dict) else {}
    checkpoint=metadata.get("checkpoint") if isinstance(metadata.get("checkpoint"),dict) else {}
    evidence=metadata.get("evidence") if isinstance(metadata.get("evidence"),dict) else {}
    citation=metadata.get("citation") if isinstance(metadata.get("citation"),dict) else {}
    web_search=evidence.get("web_search") if isinstance(evidence.get("web_search"),dict) else {}
    sources=metadata.get("sources")
    sections={
        "model":_compact({
            "role":metadata.get("role") or routing.get("model_role"),
            "model":metadata.get("model"),
            "context_window":metadata.get("context") or metadata.get("context_window"),
            "output_budget_tokens":metadata.get("requested_output_tokens") or metadata.get("output_budget") or routing.get("output_tokens"),
            "residency_policy":metadata.get("residency_policy"),
            "exclusive_memory":metadata.get("exclusive_memory"),
            "unloaded_model_count":metadata.get("residency_unload_count"),
        }),
        "completion":_compact({
            "reason":metadata.get("completion_reason"),
            "provider_reason":metadata.get("done_reason"),
            "incomplete":metadata.get("incomplete"),
            "continuation_eligible":metadata.get("continuation_eligible"),
            "answer_started":metadata.get("answer_started"),
            "generated_tokens":metadata.get("generated_tokens"),
            "prompt_tokens":metadata.get("prompt_tokens"),
            "hidden_reasoning_used":metadata.get("hidden_reasoning_present"),
            "thinking_activity_count":metadata.get("thinking_activity_count"),
        }),
        "context":_compact({
            "compiler_version":metadata.get("context_compiler_version"),
            "estimated_prompt_tokens":metadata.get("estimated_prompt_tokens"),
            "generation_reserve_tokens":metadata.get("generation_reserve_tokens"),
            "prompt_chars":metadata.get("prompt_chars"),
            "authoritative_task_chars":metadata.get("authoritative_task_chars"),
            "recent_message_count":metadata.get("recent_message_count"),
            "retrieved_message_count":metadata.get("retrieved_message_count"),
            "omitted_layers":metadata.get("omitted_layers"),
            "clipped_layers":metadata.get("clipped_layers"),
        }),
        "task":_compact({
            "task_id":metadata.get("task_id"),
            "state":metadata.get("task_state"),
            "specification_version":metadata.get("specification_version"),
            "requirements":metadata.get("requirement_count"),
            "acceptance_criteria":metadata.get("acceptance_criteria_count"),
            "high_assurance":metadata.get("high_assurance"),
        }),
        "verification":_compact({
            "outcome":verification.get("outcome"),
            "checked":verification.get("checked_count"),
            "passed":verification.get("passed_count"),
            "failed":verification.get("failed_count"),
            "unchecked":verification.get("unchecked_count"),
            "repair_attempted":verification.get("repair_attempted"),
            "repair_role":verification.get("repair_role"),
        }),
        "continuation":_compact({
            "auto_continuations":agent.get("auto_continuations"),
            "stop_reason":agent.get("stop_reason"),
            "iterations":len(agent.get("iterations") or []),
            "checkpoint_available":checkpoint.get("available"),
            "checkpoint_reason":checkpoint.get("reason"),
            "continuation_count":checkpoint.get("continuation_count"),
            "checkpoint_chars":checkpoint.get("partial_response_chars"),
        }),
        "evidence":_compact({
            "source_count":len(sources) if isinstance(sources,list) else 0,
            "evidence_outcome":evidence.get("outcome"),
            "gate_outcome":evidence.get("gate_outcome"),
            "retrieval_rounds":metadata.get("retrieval_rounds"),
            "web_search_attempted":web_search.get("attempted"),
            "web_search_provider":web_search.get("provider"),
            "web_search_fetched":web_search.get("fetched_count"),
            "freshness_window":web_search.get("freshness"),
            "citation_status":citation.get("status"),
            "citations_complete":citation.get("complete"),
            "abstained":metadata.get("abstained"),
        }),
        "performance":_compact({
            "model_calls":metadata.get("model_calls"),
            "generation_calls":metadata.get("generation_calls"),
            "embedding_calls":metadata.get("embedding_calls"),
            "queue_wait_seconds":metadata.get("queue_wait_seconds"),
            "setup_seconds":metadata.get("setup_seconds"),
            "provider_elapsed_seconds":metadata.get("provider_elapsed_seconds"),
            "total_elapsed_seconds":metadata.get("total_elapsed_seconds"),
        }),
        "error":_compact({
            "code":metadata.get("error_code"),
            "message":metadata.get("error"),
        }),
    }
    return {key:value for key,value in sections.items() if value}
