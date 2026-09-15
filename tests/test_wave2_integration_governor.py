import pytest
from reverend.intelligence.integration_governor import IntegrationCheck,IntegrationCheckStatus,compose_integration_decision,integration_governor_methodology

def passing_checks():
    return tuple(IntegrationCheck(name,IntegrationCheckStatus.PASS,f"{name} passed") for name in integration_governor_methodology())

def test_integration_governor_requires_all_global_domains():
    checks=passing_checks()[:-1]
    result=compose_integration_decision(checks)
    assert result.outcome=="unverified"
    assert "whole_system_tests" in result.summary

def test_blocking_failure_overrides_other_passes():
    checks=list(passing_checks())
    checks[2]=IntegrationCheck("dependencies",IntegrationCheckStatus.FAIL,"dependency conflict")
    result=compose_integration_decision(checks)
    assert result.outcome=="block" and not result.accepted

def test_all_required_domains_pass_to_accept():
    result=compose_integration_decision(passing_checks())
    assert result.accepted
