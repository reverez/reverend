import pytest
from reverend.engineering_memory import EngineeringMemory


def test_selective_provenance_and_lifecycle(tmp_path):
    memory=EngineeringMemory(tmp_path/'memory.db')
    identity=memory.add('DECISION','Use SQLite for job persistence','p','user','review:42',related_commit='abc')
    memory.add('FACT','SQLite is also used elsewhere','other','test','artifact:42')
    memory.add('FAILURE','SQLite expired assumption','p','test','artifact:43',expires_at='2000-01-01 00:00:00')
    result=memory.search('p','SQLite')
    assert len(result)==1 and result[0]['related_commit']=='abc' and result[0]['evidence']=='review:42'
    assert len(memory.context('p','SQLite',max_chars=1000))<=1000
    assert memory.search('p','SQLite',kinds=['FACT'])==[]
    memory.archive(identity)
    assert memory.search('p','SQLite')==[]
    assert len(memory.search('p','SQLite',include_archived=True))==2


def test_facts_require_evidence_and_queries_are_data(tmp_path):
    memory=EngineeringMemory(tmp_path/'memory.db')
    with pytest.raises(ValueError):memory.add('FACT','A guess','p','model','')
    with pytest.raises(ValueError):memory.add('THOUGHT','A guess','p','model','text')
    memory.add('USER_CONSTRAINT','Use local models only','p','user','request:1')
    assert memory.search('p','" OR local * ; DROP TABLE x')
    with pytest.raises(ValueError):memory.search('p','local',max_chars=100000)
