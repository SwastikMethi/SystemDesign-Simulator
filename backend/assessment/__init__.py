"""Deterministic metrics and grading; no language-model inputs enter this module."""
from __future__ import annotations

import math
import operator
from collections import defaultdict

from backend.contracts import AssessmentResult, CaseResult, EvidenceItem, MetricValue, RequirementOutcome

COMPARATORS={'>=':operator.ge,'<=':operator.le,'==':operator.eq}


def metric(value,unit,samples,reason=None):
    return MetricValue(value=value,unit=unit,sample_count=samples,unavailable_reason=reason if value is None else None)


def percentile(values,q):
    if not values: return None
    values=sorted(values)
    return values[max(0,math.ceil(q*len(values))-1)]


def evaluate_requirement(requirement,measured,*,execution_status='completed'):
    if execution_status!='completed': return 'incomplete'
    if measured is None: return 'not_evaluated'
    if measured.sample_count<requirement.min_samples: return 'incomplete'
    if measured.value is None: return 'not_evaluated'
    return 'pass' if COMPARATORS[requirement.operator](measured.value,requirement.threshold) else 'fail'


def status_of(statuses):
    statuses=list(statuses)
    if 'fail' in statuses: return 'fail'
    if not statuses or 'incomplete' in statuses: return 'incomplete'
    if 'not_evaluated' in statuses: return 'not_evaluated'
    return 'pass'


def evaluate_case(engine,jobs,traces,execution_status,reason=None):
    w=engine.workload; challenge=engine.challenge
    case_id=f'{w.scenario_id}-{w.seed}'
    cohort=[o for o in engine.outcomes if w.warmup_end_us<=o.arrival_us<w.measurement_end_us]
    by_op=defaultdict(list)
    for out in cohort: by_op[out.operation_id].append(out)
    job_by_id={job.request_id:job for job in jobs}
    op_metrics={}; node_metrics={}; evidence=[]; outcomes=[]
    seconds=(w.measurement_end_us-w.warmup_end_us)/1_000_000
    for op in challenge.operations:
        rows=by_op[op.id]; success=[o for o in rows if o.status=='success']
        latencies=[(o.terminal_us-o.arrival_us)/1000 for o in success]
        n=len(rows); count=len(success)
        fresh=[o for o in success if o.fresh is not None]
        metrics={
            'success_rate':metric(count/n if n else None,'fraction',n,'no original arrivals'),
            'failure_rate':metric((n-count)/n if n else None,'fraction',n,'no original arrivals'),
            'goodput_rps':metric(sum(o.correct is True and o.terminal_us<=o.deadline_us for o in success)/seconds,'requests/second',n),
            'retry_amplification':metric(sum(engine.contexts[o.request_id].attempts for o in rows)/n if n else None,'ratio',n,'no original arrivals'),
        }
        for q in (50,95,99): metrics[f'response_p{q}_ms']=metric(percentile(latencies,q/100),'ms',count,'no successful responses')
        if op.kind in {'read_key','get_object'}:
            name='invalid_read_count' if op.kind=='read_key' else 'object_invalid_count'
            metrics[name]=metric(sum(o.status=='invalid_result' or o.correct is False for o in rows),'count',n)
        if op.kind=='read_key':
            metrics['freshness_violation_rate']=metric(sum(o.fresh is False for o in fresh)/len(fresh) if fresh else None,'fraction',len(fresh),'no eligible successful reads')
        if op.kind in {'write_key','put_object'}:
            metrics['acknowledged_write_missing_count']=metric(sum(o.acknowledged_commit_us is None or o.acknowledged_commit_us>o.terminal_us for o in success),'count',count)
        if op.kind=='put_object':
            # Capacity refusals are failures in success_rate; none can become a successful over-capacity write.
            metrics['object_capacity_violation_count']=metric(0,'count',count)
        if op.kind=='enqueue_job':
            selected=[job_by_id[o.request_id] for o in rows]
            on_time=sum(job_by_id[o.request_id].first_effect_us is not None and job_by_id[o.request_id].first_effect_us<=o.arrival_us+op.job_deadline_ms*1000 for o in rows)
            metrics['job_deadline_completion_rate']=metric(on_time/n if n else None,'fraction',n,'no enqueue intents')
            metrics['duplicate_effect_count']=metric(sum(j.duplicate_effect_count for j in selected),'count',n)
            job_latencies=[(job_by_id[o.request_id].first_effect_us-o.arrival_us)/1000 for o in rows if job_by_id[o.request_id].first_effect_us is not None]
            metrics['job_completion_p95_ms']=metric(percentile(job_latencies,.95),'ms',len(job_latencies),'no effects')
            metrics['job_retry_amplification']=metric(sum(j.attempts for j in selected)/n if n else None,'ratio',n,'no enqueue intents')
        op_metrics[op.id]=metrics
    for node_id,state in engine.nodes.items():
        pools=state.pools; available=sum(p.available_integral for p in pools); serviced=sum(p.serviced for p in pools)
        node_metrics[node_id]={
            'busy_slot_occupancy':metric(sum(p.busy_integral for p in pools)/available if available else None,'fraction',serviced,'no available slot time'),
            'queue_wait_ms':metric(sum(p.wait_total for p in pools)/serviced/1000 if serviced else None,'ms',serviced,'no serviced work'),
            'queue_depth_max':metric(state.max_queue,'count',serviced),
            'queue_depth_mean':metric(sum(p.queue_integral for p in pools)/engine.s.now if engine.s.now else 0,'count',serviced),
            'unfinished_work_count':metric(sum(p.busy+len(p.waiting) for p in pools),'count',serviced),
            'unavailable_slot_seconds':metric(sum(p.slots*engine.s.now-p.available_integral for p in pools)/1_000_000,'slot-seconds',len(pools)),
            'cost_credits_per_hour':metric(state.profile.credits_per_hour*state.node.instance_count,'credits/hour',state.node.instance_count),
        }
        if state.node.type in {'cache','cdn'}:
            n=state.hits+state.misses
            node_metrics[node_id]['cache_hit_rate']=metric(state.hits/n if n else None,'fraction',n,'no cache lookups')
        if state.node.type=='object_storage':
            node_metrics[node_id]['stored_bytes']=metric(state.stored_bytes,'bytes',state.records)
            node_metrics[node_id]['capacity_rejections']=metric(state.capacity_violations,'count',state.records)
    cost=metric(engine.compiled.cost_credits_per_hour,'credits/hour',len(engine.nodes))
    node_metrics['__design__']={'cost_credits_per_hour':cost,
        'recovery_time_ms':metric(recovery_time(engine,cohort),'ms',len(engine.fault_ends),'recovery not established' if engine.fault_ends else 'no interval fault')}
    for req in challenge.requirements:
        if w.scenario_id not in req.scenario_ids: continue
        for op_id in req.operation_ids or [None]:
            value=cost if req.metric=='cost_credits_per_hour' else op_metrics.get(op_id,{}).get(req.metric)
            status=evaluate_requirement(req,value,execution_status=execution_status)
            eid=f'{case_id}:{req.id}:{op_id or "design"}'
            # Aggregate evidence always references the real calculation interval.
            scope=f'{w.scenario_id}/seed={w.seed}/{op_id or "design"}/[{w.warmup_end_us},{w.measurement_end_us})us'
            evidence.append(EvidenceItem(evidence_id=eid,type=req.metric,unit=value.unit if value else req.unit,value=value.value if value else None,
                scope=scope,sample_count=value.sample_count if value else 0,artifact_ref=f'case:{case_id}:window:{w.warmup_end_us}:{w.measurement_end_us}'))
            ids=[eid]
            if status=='fail' and req.metric in {'freshness_violation_rate','invalid_read_count','object_invalid_count','job_deadline_completion_rate','duplicate_effect_count'}:
                category={'freshness_violation_rate':'freshness','job_deadline_completion_rate':'job_deadline','duplicate_effect_count':'duplicate_effect'}.get(req.metric,'invalid_result')
                request_id=engine.first_failures.get((op_id,category))
                if request_id:
                    trace_id='trace:'+request_id; fid=eid+':first'
                    evidence.append(EvidenceItem(evidence_id=fid,type='first_violation',unit='request',value=request_id,scope=scope,sample_count=1,artifact_ref=trace_id)); ids.append(fid)
            outcomes.append(RequirementOutcome(requirement_id=req.id,scenario_id=w.scenario_id,seed=w.seed,operation_id=op_id,status=status,measured=value,evidence_ids=ids))
    if reason or engine.diagnostics:
        evidence.append(EvidenceItem(evidence_id=case_id+':termination',type='termination',unit='reason',value=reason or '; '.join(engine.diagnostics),scope=case_id,sample_count=engine.s.events,artifact_ref=None))
    return CaseResult(case_id=case_id,scenario_id=w.scenario_id,seed=w.seed,execution_status=execution_status,
        operation_metrics=op_metrics,node_metrics=node_metrics,requirement_outcomes=outcomes,evidence=evidence,trace_refs=[t.trace_id for t in traces])


def recovery_time(engine,cohort):
    if not engine.fault_ends: return None
    fault_end=max(engine.fault_ends); consecutive=0
    grouped=defaultdict(list)
    for row in cohort:
        if row.arrival_us>=fault_end:
            grouped[(row.arrival_us-fault_end)//10_000_000,row.operation_id].append(row)
    for window in range((engine.workload.measurement_end_us-fault_end)//10_000_000):
        passed=True
        for op in engine.challenge.operations:
            rows=grouped[window,op.id]; successful=[r for r in rows if r.status=='success']
            for req in engine.challenge.requirements:
                if op.id not in req.operation_ids or engine.workload.scenario_id not in req.scenario_ids: continue
                if req.metric=='success_rate': value=len(successful)/len(rows) if rows else None
                elif req.metric.startswith('response_p'):
                    value=percentile([(r.terminal_us-r.arrival_us)/1000 for r in successful],.99 if '99' in req.metric else .95)
                elif req.metric=='freshness_violation_rate':
                    eligible=[r for r in successful if r.fresh is not None]
                    value=sum(r.fresh is False for r in eligible)/len(eligible) if eligible else None
                elif req.metric in {'invalid_read_count','object_invalid_count'}: value=sum(r.correct is False for r in rows)
                elif req.metric=='acknowledged_write_missing_count': value=sum(r.acknowledged_commit_us is None for r in successful)
                elif req.metric=='job_deadline_completion_rate':
                    delivered=sum((job:=engine.jobs.get(r.request_id)) is not None and job.first_effect is not None and job.first_effect<=r.arrival_us+op.job_deadline_ms*1000 for r in rows)
                    value=delivered/len(rows) if rows else None
                elif req.metric=='duplicate_effect_count': value=sum(max(0,job.effects-1) for r in rows if (job:=engine.jobs.get(r.request_id)) is not None)
                elif req.metric=='object_capacity_violation_count': value=0
                else: continue
                if value is None or not COMPARATORS[req.operator](value,req.threshold): passed=False
        consecutive=consecutive+1 if passed else 0
        if consecutive==3: return (window+1)*10_000
    return None


def assess_suite(challenge,case_results,*,mode='assessment'):
    required={(s.id,seed) for s in challenge.scenarios if s.required for seed in challenge.workload.assessment_seeds}
    cases={(case.scenario_id,case.seed):case for case in case_results}
    outcomes=[r for case in case_results for r in case.requirement_outcomes]
    complete=mode=='assessment' and set(cases)==required and len(cases)==len(case_results) and all(c.execution_status=='completed' for c in case_results)
    # Missing requirement rows cannot be silently treated as a pass.
    for key in required:
        case=cases.get(key)
        if case is None: continue
        expected={(r.id,op) for r in challenge.requirements if key[0] in r.scenario_ids for op in r.operation_ids or [None]}
        actual={(r.requirement_id,r.operation_id) for r in case.requirement_outcomes}
        complete &= expected==actual and len(actual)==len(case.requirement_outcomes)
    status=status_of(r.status for r in outcomes) if complete else 'incomplete'
    return AssessmentResult(status=status,case_results=case_results,requirement_outcomes=outcomes)


def compare_assessments(assessments):
    """Rank feasible candidates only; equal-cost candidates share a rank."""
    passing=[]
    for design_id,result in assessments.items():
        if result.status=='pass':
            costs=[c.node_metrics['__design__']['cost_credits_per_hour'].value for c in result.case_results]
            passing.append((max(costs),design_id))
    costs=sorted({cost for cost,_ in passing})
    return {key:{'feasible':value.status=='pass','rank':next((costs.index(cost)+1 for cost,d in passing if d==key),None),
                 'status':value.status} for key,value in assessments.items()}
