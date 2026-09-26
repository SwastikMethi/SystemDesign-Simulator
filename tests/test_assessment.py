import pytest
from backend.assessment import evaluate_requirement, metric, percentile, assess_suite, compare_assessments
from backend.content import load_challenge, load_fixture
from backend.simulation import run_case
from test_simulation import case


@pytest.mark.parametrize('operator,threshold,values,statuses',[
    ('<=',1,[.999999,1,1.000001],['pass','pass','fail']),
    ('>=',1,[.999999,1,1.000001],['fail','pass','pass']),
    ('==',1,[.999999,1,1.000001],['fail','pass','fail'])])
def test_unrounded_boundaries(operator,threshold,values,statuses):
    req=load_challenge('team-notes').requirements[0].model_copy(update={'operator':operator,'threshold':threshold,'min_samples':1})
    assert [evaluate_requirement(req,metric(v,'fraction',1)) for v in values]==statuses
    assert evaluate_requirement(req,metric(1,'fraction',0))=='incomplete'
    assert evaluate_requirement(req,None)=='not_evaluated'
    assert evaluate_requirement(req,metric(1,'fraction',1),execution_status='canceled')=='incomplete'


def test_nearest_rank_and_missing_cases():
    assert percentile(list(range(1,101)),.95)==95
    assert percentile([],.95) is None
    c=load_challenge('team-notes')
    result=run_case(c,load_fixture(c.challenge_id,'initial'),case(c,[])).result
    assert assess_suite(c,[result]).status=='incomplete'
    assert assess_suite(c,[result],mode='preview').status=='incomplete'
    assert compare_assessments({'a':assess_suite(c,[result])})['a']['rank'] is None


def test_one_seed_fails_and_missing_requirements_cannot_pass():
    from backend.contracts import CaseResult, RequirementOutcome
    c=load_challenge('team-notes'); cases=[]
    for scenario in c.scenarios:
        if not scenario.required: continue
        for seed in c.workload.assessment_seeds:
            requirements=[RequirementOutcome(requirement_id=r.id,scenario_id=scenario.id,seed=seed,operation_id=op,
                status='pass',measured=metric(r.threshold,r.unit,max(100,r.min_samples)),evidence_ids=[]) for r in c.requirements for op in r.operation_ids or [None]]
            cases.append(CaseResult(case_id=f'{scenario.id}-{seed}',scenario_id=scenario.id,seed=seed,execution_status='completed',
                operation_metrics={},node_metrics={'__design__':{'cost_credits_per_hour':metric(25,'credits/hour',2)}},
                requirement_outcomes=requirements,evidence=[],trace_refs=[]))
    assert assess_suite(c,cases).status=='pass'
    assert assess_suite(c,cases,mode='experiment').status=='incomplete'
    ranked=compare_assessments({'a':assess_suite(c,cases),'b':assess_suite(c,cases)})
    assert ranked['a']['rank']==ranked['b']['rank']==1
    cases[-1].requirement_outcomes[0].status='fail'
    cases[-1].requirement_outcomes[1].status='incomplete'
    assert assess_suite(c,cases).status=='fail'
    cases[-1].execution_status='canceled'
    assert assess_suite(c,cases).status=='incomplete'
    cases[-1].execution_status='completed'
    cases[-1].requirement_outcomes.pop()
    assert assess_suite(c,cases).status=='incomplete'
