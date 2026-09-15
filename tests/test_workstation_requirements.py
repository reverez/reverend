from __future__ import annotations

import time

import pytest

from reverend.workstation.service import Workstation
from reverend.workstation.task_state import (
    extract_authoritative_requirements,
)


class Scheduler:
    def stream(
        self,
        role,
        prompt,
        cancel=None,
        **kwargs,
    ):
        yield {
            'response':'ok',
            'done':True,
            'done_reason':'stop',
            'completion_reason':'complete',
            'output_budget':kwargs.get('predict',1536),
            'response_chars':2,
            'answer_started':True,
            'hidden_reasoning_present':False,
            'thinking_activity_count':0,
            'cancelled':False,
        }


def finished(app,identity):
    deadline=time.monotonic()+5
    while time.monotonic()<deadline:
        job=app.store.job(identity)
        if job['status'] not in {
            'queued','running','stopping'
        }:
            return job
        time.sleep(.01)
    pytest.fail('Job did not finish')


def test_extracts_explicit_requirements_and_acceptance_criteria():
    result=extract_authoritative_requirements(
        '''
# Milestone 16
Requirements:
- Keep qwen3-coder:30b.
- All inference remains local.
- DO NOT expose raw chain-of-thought.

Acceptance criteria:
1. Exactly 3 verification checks pass.
2. The original specification is preserved.
'''
    )

    assert result.immutable_requirements==(
        'Keep qwen3-coder:30b.',
        'All inference remains local.',
        'DO NOT expose raw chain-of-thought.',
    )
    assert result.acceptance_criteria==(
        'Exactly 3 verification checks pass.',
        'The original specification is preserved.',
    )
    assert result.high_assurance is True
    assert 'acceptance_criteria' in result.signals
    assert 'negative_constraint' in result.signals


def test_extracts_strong_inline_constraints_but_not_advisory_prose():
    result=extract_authoritative_requirements(
        '''
Please make the answer clear and useful.
The output MUST contain exactly 4 items.
Do not invent missing requirements.
You could mention examples if useful.
'''
    )

    assert result.immutable_requirements==(
        'The output MUST contain exactly 4 items.',
        'Do not invent missing requirements.',
    )
    assert result.acceptance_criteria==()
    assert result.high_assurance is True
    assert 'quantified_constraint' in result.signals


def test_ordinary_task_prose_does_not_become_immutable_requirement():
    result=extract_authoritative_requirements(
        'Explain how binary search works and give a short example.'
    )

    assert result.immutable_requirements==()
    assert result.acceptance_criteria==()
    assert result.high_assurance is False


def test_workstation_persists_extracted_requirements_in_task_state(
    tmp_path,
):
    app=Workstation(
        tmp_path,
        scheduler_factory=lambda:Scheduler(),
    )
    specification=(
        'Exercise 8\n'
        'Requirements:\n'
        '- Preserve the original algorithm.\n'
        '- DO NOT invent replacement exercises.\n'
        'Acceptance criteria:\n'
        '- Exactly 2 checks pass.'
    )
    try:
        submitted=app.chat(specification)
        job=finished(
            app,
            submitted['job_id'],
        )
        task=app.store.require_authoritative_task(
            submitted['conversation_id']
        )

        assert job['status']=='complete', job
        assert task.immutable_requirements==(
            'Preserve the original algorithm.',
            'DO NOT invent replacement exercises.',
        )
        assert task.acceptance_criteria==(
            'Exactly 2 checks pass.',
        )
        assert (
            task.provenance[
                'requirement_extraction'
            ]['method']
            == 'deterministic_v1'
        )
        assert task.metadata()['requirement_count']==2
        assert task.metadata()['acceptance_criteria_count']==1
        assert task.metadata()['high_assurance'] is True
        assert job['details']['requirement_count']==2
        assert job['details']['acceptance_criteria_count']==1
        assert job['details']['high_assurance'] is True
    finally:
        app.close()



def test_requirement_sections_allow_markdown_blank_lines():
    result=extract_authoritative_requirements(
        '''
Requirements:

- MUST preserve ALPHA.
- DO NOT emit BETA.

Acceptance criteria:

- Exactly 2 output items.
'''
    )

    assert result.immutable_requirements==(
        'MUST preserve ALPHA.',
        'DO NOT emit BETA.',
    )
    assert result.acceptance_criteria==(
        'Exactly 2 output items.',
    )
    assert 'negative_constraint' in result.signals
    assert 'quantified_constraint' in result.signals
