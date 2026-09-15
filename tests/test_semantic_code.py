import subprocess
from types import SimpleNamespace

import pytest
from reverend.codeintel.semantic import build_index,augment

class Embeddings:
    def __init__(self):
        self.digest='v1'
        self.registry=SimpleNamespace(resolve=lambda role:SimpleNamespace(spec=SimpleNamespace(model='mock-embed'),digest=self.digest))
    def embed(self,texts):
        # Controlled synonym oracle tests fusion mechanics, not real model quality.
        return [[1.,0.] if any(word in text.lower() for word in ('orchard','pomology','apple')) else [0.,1.] for text in texts]

def git(repo,*args):
    return subprocess.run(['git','-C',str(repo),*args],check=True,capture_output=True,text=True).stdout.strip()

@pytest.fixture
def repo(tmp_path):
    root=tmp_path/'repo';root.mkdir();git(root,'init','-b','main')
    (root/'fruit.py').write_text('def pomology():\n    return "apple"\n')
    (root/'network.py').write_text('def connect():\n    return "socket"\n')
    git(root,'add','.');git(root,'-c','user.name=Test','-c','user.email=test@example.invalid','commit','-m','fixture')
    return root

def test_reconstructable_current_index_and_overlay(repo,tmp_path):
    db=tmp_path/'index.db';scheduler=Embeddings()
    before,_=augment(repo,'orchard',scheduler,db_path=db)
    result=build_index(repo,scheduler,db_path=db)
    assert result['collection']=='code_vectors_v1' and result['chunks']==2
    after,metadata=augment(repo,'orchard',scheduler,db_path=db)
    assert not before.hits and after.paths[0]=='fruit.py'
    assert 'current' in metadata['semantic_status']
    (repo/'fruit.py').write_text('def orchard():\n    return "changed"\n')
    current,metadata=augment(repo,'orchard',scheduler,db_path=db)
    hit=next(h for h in current.hits if h.path=='fruit.py')
    assert not any('semantic v1' in r for r in hit.reasons)
    assert '1 changed/deleted' in metadata['semantic_status']
    with pytest.raises(ValueError,match='clean commit'):build_index(repo,scheduler,db_path=db)
    git(repo,'add','.');git(repo,'-c','user.name=Test','-c','user.email=test@example.invalid','commit','-m','new')
    assert 'stale commit' in augment(repo,'orchard',scheduler,db_path=db)[1]['semantic_status']
    build_index(repo,scheduler,db_path=db)
    scheduler.digest='v2'
    assert 'stale embedding' in augment(repo,'orchard',scheduler,db_path=db)[1]['semantic_status']

def test_index_budget_and_atomic_publication(repo,tmp_path):
    db=tmp_path/'index.db';scheduler=Embeddings()
    with pytest.raises(ValueError,match='budget'):build_index(repo,scheduler,db_path=db,max_files=1)
    build_index(repo,scheduler,db_path=db,paths=['fruit.py'])
    assert augment(repo,'orchard',scheduler,db_path=db)[0].paths==('fruit.py',)
    scheduler.embed=lambda texts:[]
    with pytest.raises(ValueError,match='shape'):build_index(repo,scheduler,db_path=db)
    assert db.exists()

def test_worktrees_share_index_and_model_failure_falls_back(repo,tmp_path):
    db=tmp_path/'index.db';scheduler=Embeddings();build_index(repo,scheduler,db_path=db)
    worktree=tmp_path/'task';git(repo,'worktree','add','--detach',str(worktree))
    assert augment(worktree,'orchard',scheduler,db_path=db)[0].paths[0]=='fruit.py'
    scheduler.embed=lambda _: (_ for _ in ()).throw(RuntimeError('offline'))
    search,metadata=augment(worktree,'connect',scheduler,db_path=db)
    assert search.paths[0]=='network.py' and 'unavailable' in metadata['semantic_status']
