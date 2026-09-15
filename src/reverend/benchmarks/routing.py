"""Deterministic M8 routing acceptance using the permanent benchmark runner."""
from __future__ import annotations
from dataclasses import asdict
from datetime import datetime,timezone
from pathlib import Path
from uuid import uuid4
from reverend.intelligence.understanding import understand
from reverend.intelligence.routing import plan_request
from .evaluator import evaluate_expectations
from .models import BenchmarkBudget,BenchmarkCase,BenchmarkCategory,BenchmarkObservation
from .reporting import BenchmarkRun,save_run
from .runner import BenchmarkRunner


def routing_cases():
    examples=(
        ('conversation','Hello','fast_general'),
        ('translation','Translate this sentence into French: Good morning.','fast_general'),
        ('small-code','Explain a Python generator function','fast_code'),
        ('complex-code','Design a multi-file Rust architecture','strong_code'),
        ('hard-reasoning','Prove the matrix identity rigorously','deep_reason'),
        ('personal-evidence','Find my notes about project planning','fast_general'),
    )
    return tuple(BenchmarkCase(case_id='routing-'+identity,name=identity,category=BenchmarkCategory.ROUTING,
        prompt=prompt,expected={'metadata_equals':{'routing.model_role':role,'routing.network_allowed':False}},
        budget=BenchmarkBudget(timeout_seconds=2,max_model_calls=0,max_retrieval_rounds=0),tags=('m8','deterministic'))
        for identity,prompt,role in examples)


def observe(case):
    request=understand(case.prompt)
    plan=plan_request(request)
    return BenchmarkObservation(response='Planned local role: '+plan.model_role.value,
        metadata={'understanding':asdict(request),'routing':asdict(plan),'model_calls':0,'retrieval_rounds':0})


def run_routing(root: Path):
    started=datetime.now(timezone.utc)
    results=BenchmarkRunner(executor=observe,evaluator=evaluate_expectations).run(routing_cases())
    run=BenchmarkRun(run_id=started.strftime('%Y%m%dT%H%M%S%fZ')+'-'+uuid4().hex[:8],
        started_at=started.isoformat(),completed_at=datetime.now(timezone.utc).isoformat(),
        results=results,
        metadata={'execution_kind':'deterministic_policy','live_inference':False,'case_definitions':[asdict(c) for c in routing_cases()]})
    return run,save_run(run,root=root)
