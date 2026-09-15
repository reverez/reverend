"""Adapters from accepted Reverend verifier evidence into assurance checks."""
from __future__ import annotations
from typing import Any
from .models import CheckAuthority,CheckStatus,VerificationCheck

def workstation_checks(report:Any)->tuple[VerificationCheck,...]:
    result=[]
    for check in getattr(report,"checks",()):
        status=str(getattr(check,"status","unchecked"))
        result.append(VerificationCheck(str(getattr(check,"requirement","requirement")),CheckStatus(status),CheckAuthority.DETERMINISTIC,required=True,evidence=str(getattr(check,"message",""))))
    return tuple(result)

def development_checks(report:Any)->tuple[VerificationCheck,...]:
    result=[]
    for check in getattr(report,"checks",()):
        passed=bool(getattr(check,"passed",False));required=bool(getattr(check,"required",True))
        result.append(VerificationCheck(str(getattr(check,"name","check")),CheckStatus.PASS if passed else CheckStatus.FAIL,CheckAuthority.DETERMINISTIC,required=required,evidence=str(getattr(check,"summary",""))))
    return tuple(result)
