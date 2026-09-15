"""Live Wave-2 specialist acceptance on the configured local model runtime."""
from __future__ import annotations
import argparse
import json
import time
from collections.abc import Mapping
from dataclasses import fields,is_dataclass
from pathlib import Path
from typing import Any,Callable

def _pack(value:Any)->Any:
    """Convert typed specialist outputs without deepcopy/pickle semantics."""
    if is_dataclass(value):
        return {
            field.name:_pack(getattr(value,field.name))
            for field in fields(value)
        }
    if isinstance(value,Mapping):
        return {
            str(key):_pack(item)
            for key,item in value.items()
        }
    if isinstance(value,(tuple,list)):
        return [_pack(item) for item in value]
    if isinstance(value,(str,int,float,bool)) or value is None:
        return value
    if hasattr(value,"__dict__"):
        return {
            str(key):_pack(item)
            for key,item in vars(value).items()
            if not str(key).startswith("_")
        }
    raise ValueError("Wave-2 specialist runner returned an unsupported result")

def run_live_specialists(
    *,
    scheduler=None,
    product_runner:Callable|None=None,
    architect_runner:Callable|None=None,
    security_runner:Callable|None=None,
    stakeholder_factory:Callable|None=None,
)->dict[str,Any]:
    if scheduler is None:
        from reverend.development.coder import create_local_scheduler
        scheduler=create_local_scheduler()
    if product_runner is None or stakeholder_factory is None:
        from reverend.intelligence.product_specialist import StakeholderFinding,run_product_strategy
        product_runner=product_runner or run_product_strategy
        stakeholder_factory=stakeholder_factory or StakeholderFinding
    if architect_runner is None:
        from reverend.intelligence.architecture_specialist import run_architect
        architect_runner=run_architect
    if security_runner is None:
        from reverend.intelligence.security_specialist import run_security_assessment
        security_runner=run_security_assessment

    objective="Design a read-only local runtime health card without creating a second control plane."
    stakeholder=stakeholder_factory(
        "wave2-live-user","local developer","fast health visibility",
        "hidden runtime failures","A local developer needs understandable operational status.",
    )
    stages={}
    started=time.monotonic()
    try:
        t=time.monotonic()
        product=product_runner(
            scheduler,objective=objective,
            evidence_summary=(
                "Accepted Wave-1 evidence: Reverend is a modular local application; "
                "the authoritative control plane and model/runtime health already exist; "
                "GUI control-plane access must remain read-only."
            ),
            stakeholder_findings=(stakeholder,),
            project_constraints=("local-only UI","single authoritative control plane","no new daemon"),
            evidence_refs=("baseline:vnext-wave1-accepted",),
        )
        stages["product"]={"passed":True,"seconds":round(time.monotonic()-t,4),"result":_pack(product)}

        t=time.monotonic()
        architecture=architect_runner(
            scheduler,objective=objective,
            requirements=tuple(product.requirements),
            current_architecture=(
                "Local modular monolith. Workstation server exposes authenticated loopback APIs. "
                "ControlPlaneStore owns vNext workflow/task/job/artifact state. GUI is a consumer."
            ),
            evidence_refs=("baseline:vnext-wave1-accepted",),
            resource_constraints=("no new service","reuse existing status/control-plane APIs"),
        )
        stages["architecture"]={"passed":True,"seconds":round(time.monotonic()-t,4),"result":_pack(architecture)}

        t=time.monotonic()
        security=security_runner(
            scheduler,objective="Security-review the proposed read-only health card.",
            architecture_data=json.dumps(_pack(architecture),sort_keys=True)[:12000],
            capabilities=("repo.read",),
            evidence_refs=("baseline:vnext-wave1-accepted",),
        )
        stages["security"]={"passed":True,"seconds":round(time.monotonic()-t,4),"result":_pack(security)}
        passed=True
        error=None
    except Exception as exc:
        passed=False
        error={"type":type(exc).__name__,"message":str(exc)[:1000]}

    return {
        "schema_version":1,
        "suite":"Wave2 live specialist acceptance",
        "passed":passed,
        "elapsed_seconds":round(time.monotonic()-started,4),
        "stages":stages,
        "error":error,
    }

def main(argv:list[str]|None=None)->int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",type=Path)
    args=parser.parse_args(argv)
    report=run_live_specialists()
    text=json.dumps(report,indent=2,sort_keys=True,default=str)+"\n"
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(text,encoding="utf-8")
    print(text,end="")
    return 0 if report["passed"] else 1

if __name__=="__main__":
    raise SystemExit(main())
