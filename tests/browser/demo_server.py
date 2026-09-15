"""Deterministic GUI fixture: no live models or persistent user data."""
import argparse
import tempfile
import threading
from pathlib import Path
from reverend.workstation.service import Workstation
from reverend.workstation.server import LocalServer

class MockScheduler:
    def generate(self,role,prompt,**kwargs):
        from types import SimpleNamespace
        return SimpleNamespace(model='mock-router',digest='fixture',response={
            'response':'{"intent":"open_domain_fact","entities":[],"confidence":0.9,"evidence_need":"reference"}'})
    def stream(self,role,prompt,cancel=None):
        text=r'''## A local engineering answer

The derivative of $x^2$ is $2x$.

$$\int_0^1 x^2\,dx = \frac{1}{3}$$

```python
def square(x):
    return x * x
```

| Check | Result |
| --- | --- |
| Local inference | Passed |

<script>window.injected = true</script>

<img src=x onerror="window.injected=true">
'''
        yield {'response':'<think>SECRET_REASONING</think>','model':'mock-local','digest':'mock-digest'}
        for start in range(0,len(text),28):
            if cancel.wait(.04):return
            yield {'response':text[start:start+28],'model':'mock-local','elapsed_seconds':.2}
        yield {'done':True,'generated_tokens':100}

parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=8876)
args=parser.parse_args()
with tempfile.TemporaryDirectory(prefix='reverend-browser-') as root:
    service=Workstation(Path(root),scheduler_factory=MockScheduler)
    server=LocalServer(('127.0.0.1',args.port),service)
    print('ready',flush=True)
    try:server.serve_forever()
    finally:server.server_close();service.close()
