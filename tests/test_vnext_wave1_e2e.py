from __future__ import annotations

from reverend.assurance import (
    CheckAuthority,
    CheckStatus,
    VerificationCheck,
    authorize_artifact_promotion,
    compose_verification,
)
from reverend.controlplane import (
    ControlPlaneStore,
    JobStatus,
    TaskStatus,
    WorkflowStatus,
)
from reverend.policy import (
    PermissionEvaluator,
    default_capability_registry,
    permissions_for_worker,
)
from reverend.runtime import (
    ModelInfo,
    ModelRegistry,
    ModelRole,
    ResourceBroker,
    ResourceCapacity,
    RuntimeResourceRequest,
)
from reverend.specialists import specialist_from_worker
from reverend.workers import WorkerRole, worker_policy


class Provider:
    def list_models(self):
        return [
            ModelInfo(
                name="qwen3-coder:30b",
                digest="digest",
                size_bytes=6_000_000_000,
                modified_at=None,
                details={},
            )
        ]

    def loaded_models(self):
        return []


def test_wave1_authoritative_chain_composes(tmp_path):
    store = ControlPlaneStore(tmp_path / "control-plane.db")

    workflow = store.create_workflow("Implement and verify a repository change")
    store.transition_workflow(workflow.id, WorkflowStatus.ACTIVE)

    task = store.create_task(
        workflow.id,
        kind="development",
        objective="Implement the requested change",
        acceptance_criteria=("tests pass",),
    )
    store.transition_task(task.id, TaskStatus.READY)
    store.transition_task(task.id, TaskStatus.RUNNING)

    job = store.create_job(
        task.id,
        executor=WorkerRole.CODER.value,
        trace_context={"trace_id": workflow.trace_id},
    )
    store.transition_job(job.id, JobStatus.ACQUIRING_RESOURCES)

    specialist = specialist_from_worker(WorkerRole.CODER)
    assert specialist.model_role is ModelRole.STRONG_CODE

    # Use the accepted production profile while binding through the logical role.
    registry = ModelRegistry(Provider())
    resolved = registry.resolve(ModelRole.STRONG_CODE)
    assert resolved.spec.model == "qwen3-coder:30b"

    broker = ResourceBroker(
        ResourceCapacity(
            cpu_cores=8,
            ram_bytes=32 * 1024**3,
            gpu_count=1,
            gpu_vram_bytes=8 * 1024**3,
        )
    )
    request = RuntimeResourceRequest(
        request_id="request-1",
        job_id=job.id,
        cpu_cores=1,
        ram_bytes=1 * 1024**3,
        gpu_required=True,
        estimated_vram_bytes=6_215_654_440,
        gpu_exclusive=True,
        model_id=resolved.spec.model,
    )
    lease = broker.acquire(request, timeout=1.0)
    assert lease.job_id == job.id and lease.active

    policy = worker_policy(WorkerRole.CODER)
    permissions = permissions_for_worker(
        specialist.id,
        policy,
        project_id="project-1",
    )
    evaluator = PermissionEvaluator(
        default_capability_registry(),
        permissions,
    )
    evaluator.require(
        specialist.id,
        "repo.read",
        resource={"project_id": "project-1"},
    )
    evaluator.require(
        specialist.id,
        "repo.propose_edit",
        resource={"project_id": "project-1"},
    )

    store.transition_job(job.id, JobStatus.RUNNING)
    store.append_event(
        "ToolAuthorized",
        actor=specialist.id,
        subject_ids=(job.id,),
        trace_context={"trace_id": workflow.trace_id},
        payload={"capability": "repo.propose_edit"},
    )

    artifact = store.create_artifact(
        "implementation_patch",
        inline_content="diff --git a/example.py b/example.py",
        producer_job_id=job.id,
        provenance={
            "specialist_id": specialist.id,
            "model_role": specialist.model_role.value,
            "model": resolved.spec.model,
            "lease_id": lease.lease_id,
        },
    )

    store.transition_job(job.id, JobStatus.VERIFYING)
    verification = compose_verification(
        producer_id=specialist.id,
        verifier_id=WorkerRole.CRITIC_VERIFIER.value,
        deterministic_checks=(
            VerificationCheck(
                "tests",
                CheckStatus.PASS,
                CheckAuthority.DETERMINISTIC,
                required=True,
                evidence="portable fixture passed",
            ),
        ),
    )
    authorize_artifact_promotion(artifact.id, verification)

    validated = store.validate_artifact(artifact.id, accepted=True)
    promoted = store.promote_artifact(validated.id)
    assert promoted.promotion_state.value == "promoted"

    store.transition_job(
        job.id,
        JobStatus.SUCCEEDED,
        result_ref=promoted.id,
    )
    store.transition_task(task.id, TaskStatus.COMPLETE)
    store.transition_workflow(workflow.id, WorkflowStatus.COMPLETE)

    broker.release(lease.lease_id, job_id=job.id)

    assert store.job(job.id).status is JobStatus.SUCCEEDED
    assert store.task(task.id).status is TaskStatus.COMPLETE
    assert store.workflow(workflow.id).status is WorkflowStatus.COMPLETE
    assert broker.active_leases() == ()
    assert store.events(event_type="ToolAuthorized")
