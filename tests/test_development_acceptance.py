from __future__ import annotations

from reverend.development.acceptance import (
    compile_acceptance_criteria,
    render_acceptance_contract,
)


def test_acceptance_compiler_preserves_exact_user_text():
    text = (
        "Zero division raises ValueError with exactly 'division by zero'. "
        "Existing tests pass."
    )
    contract = compile_acceptance_criteria(text)

    assert [item.criterion_id for item in contract.criteria] == ["AC-01", "AC-02"]
    assert contract.criteria[0].text == (
        "Zero division raises ValueError with exactly 'division by zero'."
    )
    assert contract.criteria[0].exact_literals == ("division by zero",)
    assert contract.criteria[0].testability == "deterministic_candidate"
    assert contract.criteria[1].testability == "deterministic"
    assert contract.criteria[1].regression_sensitive


def test_acceptance_compiler_handles_bullets_without_rewriting():
    contract = compile_acceptance_criteria(
        "- Public API remains compatible\n"
        "- Tests pass\n"
        "- Do not modify src/legacy.py"
    )

    assert tuple(item.text for item in contract.criteria) == (
        "Public API remains compatible",
        "Tests pass",
        "Do not modify src/legacy.py",
    )
    assert contract.criteria[0].category == "compatibility"
    assert contract.criteria[2].regression_sensitive


def test_acceptance_contract_digest_is_stable():
    first = compile_acceptance_criteria("Returns 3. Tests pass.")
    second = compile_acceptance_criteria("Returns 3. Tests pass.")
    assert first.digest == second.digest
    assert first.criterion_ids == ("AC-01", "AC-02")


def test_empty_acceptance_contract_is_valid_and_explicit():
    contract = compile_acceptance_criteria(None)
    assert contract.original_text == ""
    assert contract.criteria == ()
    assert len(contract.digest) == 64
    rendered = render_acceptance_contract(contract)
    assert '"criteria": []' in rendered
