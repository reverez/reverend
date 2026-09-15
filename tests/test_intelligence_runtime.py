from types import SimpleNamespace
import pytest
from reverend.intelligence.contracts import RequestBudget
from reverend.intelligence.runtime import BudgetedScheduler,ModelBudgetExceeded,classify
from reverend.runtime import ModelRole
from reverend.runtime.models import ModelRegistry
from reverend.runtime.providers import ModelInfo

class Scheduler:
    def generate(self,role,prompt,**kwargs):
        return SimpleNamespace(model='mock',digest='abc',response={'response':'{"intent":"open_domain_fact","entities":[]}',
            'prompt_eval_count':20,'eval_count':10},elapsed_seconds=.4,queue_wait_seconds=.1,
            setup_seconds=.2,total_elapsed_seconds=.7)
    def embed(self,texts):return [[1.,0.] for _ in texts]
    def stream(self,role,prompt,**kwargs):yield {'response':'answer','model':'mock','digest':'abc','prompt_tokens':30,
        'generated_tokens':5,'elapsed_seconds':.5,'queue_wait_seconds':.1,'setup_seconds':.2,
        'total_elapsed_seconds':.8,'done':True,'done_reason':'stop',
        'completion_reason':'complete','output_budget':kwargs.get('predict',1536),
        'response_chars':6,'answer_started':True,'hidden_reasoning_present':False,
        'thinking_activity_count':0,'cancelled':False,'context':8192,
        'exclusive_memory':False,'residency_policy':'shared',
        'residency_unloaded_models':[],'residency_unload_count':0}


def test_budget_counts_all_inference_and_stops_before_extra_call():
    scheduler=BudgetedScheduler(Scheduler(),RequestBudget(max_model_calls=2))
    scheduler.embed(['query']);list(scheduler.stream(ModelRole.FAST_GENERAL,'prompt'))
    with pytest.raises(ModelBudgetExceeded):scheduler.generate(ModelRole.ROUTER,'query')
    metrics=scheduler.metrics()
    assert metrics['model_calls']==2 and metrics['embedding_calls']==1
    assert metrics['total_prompt_tokens']==30 and metrics['total_generated_tokens']==5
    assert metrics['total_queue_wait_seconds']==.1
    assert metrics['total_setup_seconds']==.2
    assert metrics['total_provider_seconds']==.5
    assert all(r['status']=='complete' for r in metrics['model_runs'])
    generation_run=metrics['model_runs'][1]
    assert generation_run['completion_reason']=='complete'
    assert generation_run['answer_started'] is True
    assert generation_run['hidden_reasoning_present'] is False
    assert generation_run['context']==8192
    assert generation_run['residency_policy']=='shared'
    assert generation_run['residency_unload_count']==0
    assert all('response' not in run for run in metrics['model_runs'])


def test_local_classifier_uses_existing_json_contract():
    scheduler=BudgetedScheduler(Scheduler(),RequestBudget())
    assert classify(scheduler,'A question')['intent']=='open_domain_fact'
    assert scheduler.metrics()['model_runs'][0]['role']=='router'



class InventoryProvider:
    def __init__(self):
        self.calls = 0

    def list_models(self):
        self.calls += 1
        return [
            ModelInfo(
                name="qwen3.5:4b",
                digest="inventory-digest",
                size_bytes=1,
                modified_at=None,
                details={},
            )
        ]


class InventoryScheduler(Scheduler):
    def __init__(self):
        self.provider = InventoryProvider()
        self.registry = ModelRegistry(
            self.provider,
            inventory_ttl_seconds=30.0,
        )

    def generate(
        self,
        role,
        prompt,
        **kwargs,
    ):
        resolved = self.registry.resolve(
            role
        )
        return SimpleNamespace(
            model=resolved.spec.model,
            digest=resolved.digest,
            response={
                "response": "{}",
                "prompt_eval_count": 5,
                "eval_count": 2,
            },
            elapsed_seconds=0.1,
            queue_wait_seconds=0.0,
            setup_seconds=0.01,
            total_elapsed_seconds=0.11,
        )


def test_budgeted_scheduler_reports_request_inventory_deltas():
    raw = InventoryScheduler()
    scheduler = BudgetedScheduler(
        raw,
        RequestBudget(
            max_model_calls=2
        ),
    )

    scheduler.generate(
        ModelRole.ROUTER,
        "classify",
    )
    scheduler.generate(
        ModelRole.FAST_GENERAL,
        "answer",
    )

    metrics = scheduler.metrics()

    assert raw.provider.calls == 1
    assert (
        metrics[
            "inventory_provider_reads"
        ]
        == 1
    )
    assert (
        metrics[
            "inventory_cache_hits"
        ]
        == 1
    )
    assert (
        metrics[
            "inventory_cached_models"
        ]
        == 1
    )
    assert (
        metrics[
            "inventory_ttl_seconds"
        ]
        == 30.0
    )
