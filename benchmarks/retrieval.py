"""Run with the project venv; labels must be reviewed before running."""
from __future__ import annotations
import argparse
import json
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path

from reverend.cli import embed
from reverend.config import COLLECTION, close_qdrant, qdrant_client
from reverend.retrieve import fuse_rrf, retrieve_dense, retrieve_lexical

ROOT = Path(__file__).resolve().parent


def source_key(source):
    return source.split('shared-notes/')[-1]


def metrics(rows, relevant):
    keys = [source_key(row['source']) for row in rows[:10]]
    expected = set(relevant)
    return {
        'recall_at_5': len(set(keys[:5]) & expected) / len(expected),
        'recall_at_10': len(set(keys) & expected) / len(expected),
        'mrr_at_10': next((1/rank for rank, key in enumerate(keys,1) if key in expected),0),
    }


def run(output, cache_path=None):
    labels = json.loads((ROOT/'retrieval-queries.json').read_text())['queries']
    start = time.monotonic()
    store = qdrant_client()
    cold = time.monotonic() - start
    start = time.monotonic()
    vectors = embed([item['query'] for item in labels])
    embedding_seconds = time.monotonic()-start
    if len(vectors) != len(labels):
        raise RuntimeError('Embedding batch count mismatch')
    report = {'created_at':datetime.now(timezone.utc).isoformat(), 'queries':len(labels),
              'collection':COLLECTION,'qdrant_points':store.count(COLLECTION,exact=True).count,
              'cold_qdrant_seconds':cold, 'embedding_batch_seconds':embedding_seconds,
              'methodology':'Sparse document Recall@k over top-k chunks; MRR@10. Same batched query vectors and candidates used for dense and hybrid. Latency includes amortized batch embedding, excludes cold collection startup. Labels are incomplete and favour known-title academic queries.',
              'candidates':50,'rrf_k':60,'per_query':[]}
    cache=[]
    for item, vector in zip(labels,vectors):
        start=time.monotonic()
        dense=retrieve_dense(item['query'],50,corpus='obsidian',store=store,query_vector=vector)
        dense_seconds=time.monotonic()-start
        start=time.monotonic()
        lexical=retrieve_lexical(item['query'],50,corpus='obsidian')
        lexical_seconds=time.monotonic()-start
        start=time.monotonic()
        hybrid=fuse_rrf(dense,lexical,10)
        fusion_seconds=time.monotonic()-start
        entry={'query':item['query']}
        for mode,rows,seconds in [('dense',dense,dense_seconds+embedding_seconds/len(labels)),
                                   ('lexical',lexical,lexical_seconds),
                                   ('hybrid',hybrid,dense_seconds+lexical_seconds+fusion_seconds+embedding_seconds/len(labels))]:
            entry[mode]={**metrics(rows,item['relevant_sources']),'seconds':seconds,
                         'top10':[{'chunk_id':r['chunk_id'],'source':source_key(r['source']),
                                   'section':r['section']} for r in rows[:10]]}
        report['per_query'].append(entry)
        cache.append({'label':item,'dense':dense,'lexical':lexical})
        print(f"evaluated {len(cache)}/{len(labels)}",flush=True)
    report['summary']={mode:{key:statistics.mean(r[mode][key] for r in report['per_query'])
                            for key in ['recall_at_5','recall_at_10','mrr_at_10','seconds']}
                       for mode in ['dense','lexical','hybrid']}
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
    if cache_path:
        cache_path.write_text(json.dumps(cache,ensure_ascii=False))
    print(json.dumps({k:v for k,v in report.items() if k != 'per_query'},indent=2))
    close_qdrant()
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,default=ROOT/'results/v2-retrieval.json')
    parser.add_argument('--cache',type=Path)
    args=parser.parse_args()
    run(args.output,args.cache)
