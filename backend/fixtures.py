"""Run authored numerical fixtures, preserving measured per-case verdicts as JSON."""
from __future__ import annotations
import argparse
import gc
import json
import resource
import sys
import time
from pathlib import Path

from backend.assessment import assess_suite
from backend.content import load_challenge, load_fixture
from backend.simulation import Engine
from backend.workloads import generate_case

CHALLENGES=['team-notes','url-shortener','product-catalogue','photo-delivery','notifications']


def run_fixture(challenge_id,fixture):
    challenge=load_challenge(challenge_id); design=load_fixture(challenge_id,fixture)
    start=time.perf_counter(); results=[]; cases=[]
    for scenario in challenge.scenarios:
        if not scenario.required: continue
        for seed in challenge.workload.assessment_seeds:
            case_start=time.perf_counter()
            engine=Engine(challenge,design,generate_case(challenge,scenario.id,seed))
            artifact=engine.run()
            results.append(artifact.result)
            cases.append({'scenario_id':scenario.id,'seed':seed,'seconds':round(time.perf_counter()-case_start,3),
                'requests':len(artifact.outcomes),'executed_events':engine.s.events,'trace_count':len(artifact.traces),
                'execution_status':artifact.result.execution_status,
                'requirements':[r.model_dump(mode='json') for r in artifact.result.requirement_outcomes]})
            del artifact, engine
    verdict=assess_suite(challenge,results)
    return {'challenge_id':challenge_id,'fixture':fixture,'status':verdict.status,
            'seconds':round(time.perf_counter()-start,3),'cases':cases}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--challenge',choices=CHALLENGES)
    parser.add_argument('--fixture',choices=['initial','reference','failure','budget'])
    parser.add_argument('--output',type=Path,default=Path('.implementation/fixture-results.json'))
    args=parser.parse_args()
    baseline=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    report={'measurement':{'clock':'time.perf_counter wall seconds','memory':'resource.getrusage(RUSAGE_SELF).ru_maxrss peak RSS; bytes on macOS',
             'platform':sys.platform,'baseline_rss':baseline},'fixtures':[]}
    start=time.perf_counter()
    for challenge in [args.challenge] if args.challenge else CHALLENGES:
        for fixture in [args.fixture] if args.fixture else ['initial','reference','failure','budget']:
            result=run_fixture(challenge,fixture); report['fixtures'].append(result)
            print(f'{challenge}/{fixture}: {result["status"]}, {result["seconds"]}s',flush=True)
            gc.collect()
            report['measurement'].update(total_seconds=round(time.perf_counter()-start,3),peak_rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                additional_peak_rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss-baseline)
            args.output.parent.mkdir(parents=True,exist_ok=True)
            args.output.write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__': main()
