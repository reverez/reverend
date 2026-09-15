import json
from reverend.benchmarks.routing import run_routing


def test_routing_acceptance_records_no_inference(tmp_path):
    run,path=run_routing(tmp_path)
    assert run.summary.total==run.summary.passed==6
    report=json.loads(path.read_text())
    assert report['metadata']['live_inference'] is False
    assert all(r['metrics']['model_calls']==0 for r in report['results'])
