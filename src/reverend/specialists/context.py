"""Budgeted selected-context broker; it does not replace Context Compiler V2."""
from __future__ import annotations
import math
from .models import ContextItem,ContextPolicy,ContextSelection

class ContextBrokerError(RuntimeError):pass
class ContextBudgetExceeded(ContextBrokerError):pass

def estimate_tokens(text:str)->int:
    if not text:return 0
    # Deliberately conservative dependency-free estimate. The canonical Context
    # Engine remains authoritative for final provider admission.
    return max(1,math.ceil(len(text.encode("utf-8"))/3.0))

class ContextBroker:
    def select(self,items:tuple[ContextItem,...],policy:ContextPolicy)->ContextSelection:
        allowed=[item for item in items if item.layer in policy.allowed_layers]
        normalized=[]
        pre_omitted=[]
        seen=set()
        for item in allowed:
            if item.id in seen:continue
            seen.add(item.id)
            estimate=item.estimated_tokens if item.estimated_tokens is not None else estimate_tokens(item.text)
            if estimate>policy.max_item_tokens and not (item.mandatory or item.layer in policy.mandatory_layers):
                pre_omitted.append(item.id)
                continue
            normalized.append((item,estimate))
        mandatory=[pair for pair in normalized if pair[0].mandatory or pair[0].layer in policy.mandatory_layers]
        mandatory_ids={item.id for item,_ in mandatory}
        mandatory_tokens=sum(tokens for _,tokens in mandatory)
        if mandatory_tokens>policy.max_input_tokens:
            raise ContextBudgetExceeded(f"Mandatory context requires {mandatory_tokens} tokens but budget is {policy.max_input_tokens}")
        optional=[pair for pair in normalized if pair[0].id not in mandatory_ids]
        optional.sort(key=lambda pair:(-pair[0].priority,pair[0].id))
        selected=list(mandatory);used=mandatory_tokens;omitted=list(pre_omitted)
        for item,tokens in optional:
            if used+tokens<=policy.max_input_tokens:
                selected.append((item,tokens));used+=tokens
            else:omitted.append(item.id)
        # Preserve authority order first, then deterministic optional ranking.
        mandatory_order={layer:index for index,layer in enumerate(policy.mandatory_layers)}
        selected.sort(key=lambda pair:(0,mandatory_order.get(pair[0].layer,999),pair[0].id) if pair[0].id in mandatory_ids else (1,-pair[0].priority,pair[0].id))
        return ContextSelection(tuple(item for item,_ in selected),used,tuple(omitted),tuple(item.id for item,_ in selected if item.id in mandatory_ids))
