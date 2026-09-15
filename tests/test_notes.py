import json
from pathlib import Path

import pytest
from reverend import notes

TEMPLATE='''## 14. Mode: Individual Note
Required structure:
```markdown
# Example
## Contents
## 1. Orientation
## 4. Deep Explanation
## 9. Source Trace
## Note Production Checklist
```
## 15. Mode: Safe Batch
'''


def fixture(tmp_path,monkeypatch):
    vault=tmp_path/'vault';vault.mkdir()
    template=vault/'template.md';template.write_text(TEMPLATE)
    drafts=tmp_path/'external-drafts'
    evidence={'E1':dict(chunk_id='a',source=str(vault/'source.md'),source_title='Linear Maps',
                       section='Derivative',page=None,content_hash='hash',trust_class='TRUSTED_PRIMARY',
                       content='The derivative is the local linear approximation of a differentiable map.')}
    def gather(topic,plan):
        for i,item in enumerate(plan):
            item['evidence_ids']=['E1'] if i==0 else []
            item['gap']=None if i==0 else 'Insufficient evidence'
        return plan,evidence
    monkeypatch.setattr(notes,'gather_evidence',gather)
    def synth(topic,plan,evidence,template):
        return [{'coverage_id':plan[0]['id'],'claims':[{'text':'A derivative gives a local linear approximation.',
                 'support':[{'evidence_id':'E1','quote':'The derivative is the local linear approximation'}]}]}]
    monkeypatch.setattr(notes,'synthesize',synth)
    return vault,template,drafts


@pytest.mark.parametrize('prompt,topic',[
    ('Generate a draft note on the Jacobian Matrix using my indexed Academia sources','Jacobian Matrix'),
    ('Please write notes about eigenvectors from my sources','eigenvectors'),
    ('Create a detailed note on Bayes theorem','Bayes theorem'),
])
def test_generic_topic_normalization(prompt,topic):
    assert notes.normalize_topic(prompt)==topic


def test_external_draft_template_and_claim_provenance(tmp_path,monkeypatch):
    vault,template,drafts=fixture(tmp_path,monkeypatch)
    before=template.read_bytes()
    report=notes.compile_note('Jacobian matrix',dry_run=False,template_path=template,drafts=drafts,vault=vault)
    assert not Path(report['target']).is_relative_to(vault)
    text=Path(report['target']).read_text()
    assert 'active: false' in text and 'origin: AI-generated' in text and '[E1]' in text
    assert 'Insufficient indexed evidence' in text
    sidecar=json.loads(Path(report['provenance']).read_text())
    assert sidecar['sections'][0]['claims'][0]['support'][0]['evidence_id']=='E1'
    assert sidecar['template_hash']==report['template_hash']
    assert template.read_bytes()==before and list(vault.iterdir())==[template]
    template.write_text(TEMPLATE.replace('1. Orientation','1. Foundations'))
    second=notes.compile_note('Jacobian matrix',dry_run=False,template_path=template,drafts=drafts,vault=vault)
    assert second['template_hash']!=report['template_hash']
    assert '## 1. Foundations' in Path(second['target']).read_text()
    assert Path(report['target']).exists()


def test_dry_run_has_no_writes_or_generation(tmp_path,monkeypatch):
    vault,template,drafts=fixture(tmp_path,monkeypatch)
    def forbidden(*args):raise AssertionError('generation')
    monkeypatch.setattr(notes,'synthesize',forbidden)
    report=notes.compile_note('topic',dry_run=True,template_path=template,drafts=drafts,vault=vault)
    assert report['dry_run'] and not drafts.exists()
    with pytest.raises(ValueError,match='outside'):
        notes.compile_note('topic',dry_run=False,template_path=template,drafts=vault/'drafts',vault=vault)


def test_invalid_evidence_reference_or_quote_rejected_before_write(tmp_path,monkeypatch):
    vault,template,drafts=fixture(tmp_path,monkeypatch)
    def invalid(topic,plan,evidence,contract):
        return [{'coverage_id':plan[0]['id'],'claims':[{'text':'Claim','support':[{'evidence_id':'E99','quote':'fabricated supporting quote'}]}]}]
    monkeypatch.setattr(notes,'synthesize',invalid)
    with pytest.raises(ValueError,match='outside'):
        notes.compile_note('topic',dry_run=False,template_path=template,drafts=drafts,vault=vault)
    assert not drafts.exists()
    plan=[{'id':'S1','evidence_ids':['E1']}]
    data={'sections':[{'coverage_id':'S1','claims':[{'text':'Claim','support':[{'evidence_id':'E1','quote':'fabricated supporting quote'}]}]}]}
    with pytest.raises(ValueError,match='absent'):
        notes.validate_structure(data,plan,{'E1':{'content':'actual source passage'}})


def test_missing_evidence_never_calls_model(monkeypatch):
    from reverend import cli
    def forbidden(*args,**kwargs):raise AssertionError('model')
    monkeypatch.setattr(cli,'api',forbidden)
    plan=[{'id':'S1','evidence_ids':[]}]
    assert notes.synthesize('topic',plan,{},'template')==[{'coverage_id':'S1','claims':[]}]


def test_catalogue_metadata_and_generated_content_not_evidence():
    row=dict(source='/Source Library/Records/book.md',content='Topic material '*20,
             source_title='Topic',section='Details',trust_class='TRUSTED_PERSONAL')
    assert not notes.substantive(row,'Topic')
    row.update(source='/notes/topic.md',content='---\norigin: AI-generated\n---\n'+'Topic '*30)
    assert not notes.substantive(row,'Topic')
    row.update(content='Substantive discussion of a different subject '*5)
    assert not notes.substantive(row,'nonexistent concept')


def test_coverage_ids_have_no_gaps():
    headings,_=notes.template_contract(TEMPLATE)
    plan=notes.coverage_plan('topic',headings)
    assert [item['id'] for item in plan]==['S1','S2']


def test_synthesis_constrains_model_output_schema(monkeypatch):
    from reverend import cli
    def api(path,payload,**kwargs):
        schema=payload['format']
        assert list(schema['properties']['sections']['properties'])==['S1']
        support=schema['properties']['sections']['properties']['S1']['properties']['claims']['items']['properties']['support']
        assert support['items']['properties']['evidence_id']['enum']==['E1']
        return {'response':'{"sections":{"S1":{"claims":[]}}}'}
    monkeypatch.setattr(cli,'api',api)
    result=notes.synthesize('topic',[{'id':'S1','evidence_ids':['E1']}],
                            {'E1':{'source_title':'Title','section':'Section','content':'Source evidence'}},'template')
    assert result==[{'coverage_id':'S1','claims':[]}]
