from dataclasses import dataclass,field
from types import MappingProxyType

from reverend.benchmarks.wave2_validation import run_live_specialists


class Stakeholder:
    def __init__(self,*args):
        self.args=args


@dataclass(frozen=True)
class Product:
    requirements:tuple[str,...]=("read only",)
    metadata:object=field(
        default_factory=lambda:MappingProxyType({"model":"reasoner"})
    )


@dataclass(frozen=True)
class Architecture:
    decision:str="reuse existing API"


@dataclass(frozen=True)
class Security:
    promotion_blocked:bool=False


def test_wave2_live_harness_composes_specialist_calls_without_hidden_global_state():
    calls=[]

    def product(scheduler,**kwargs):
        calls.append(("product",scheduler,kwargs))
        return Product()

    def architect(scheduler,**kwargs):
        calls.append(("architecture",scheduler,kwargs))
        return Architecture()

    def security(scheduler,**kwargs):
        calls.append(("security",scheduler,kwargs))
        return Security()

    report=run_live_specialists(
        scheduler="scheduler",
        product_runner=product,
        architect_runner=architect,
        security_runner=security,
        stakeholder_factory=Stakeholder,
    )

    assert report["passed"] is True
    assert [call[0] for call in calls]==["product","architecture","security"]
    assert calls[1][2]["requirements"]==("read only",)
    assert "reuse existing API" in calls[2][2]["architecture_data"]
    assert report["stages"]["product"]["result"]["metadata"]=={"model":"reasoner"}
