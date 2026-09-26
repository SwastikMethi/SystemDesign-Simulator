"""Numerical model checks; deterministic microsecond fixtures."""
from backend.content import load_challenge, load_fixture
from backend.workloads import Arrival, WorkloadCase
from backend.simulation import Engine, Scheduler, Pool, run_case


def case(challenge, arrivals, end=10_000_000):
    return WorkloadCase(challenge_id=challenge.challenge_id, challenge_version=challenge.version,
        scenario_id='steady', seed=101, mode='experiment', warmup_end_us=0,
        measurement_end_us=end, drain_end_us=end+3_000_000, initial_data_hash='test', arrivals=arrivals, faults=[])


def arrival(challenge, i, time=0, operation=0, deadline=2_000_000):
    op=challenge.operations[operation]
    return Arrival(request_id=str(i), operation_id=op.id, key=challenge.initial_data.namespace+':0',
        payload_id='payload:'+str(i), time_us=time, deadline_us=time+deadline,
        request_bytes=op.request_bytes, response_bytes=op.response_bytes, segment_id='test')


def test_priority_and_fifo_finite_pool():
    s=Scheduler(); order=[]
    for priority in (4,3,2,1,0,1):
        s.at(10, priority, lambda p=priority: order.append(p))
    s.run(10)
    assert order == [0,1,1,2,3,4]
    s=Scheduler(); p=Pool(s, 1, 1); finished=[]; rejected=[]
    def work(i):
        def start(release):
            s.after(10,1,lambda: (finished.append((i,s.now)),release()))
        p.acquire(start,lambda:rejected.append(i))
    for i in range(3): work(i)
    s.run(30)
    assert finished==[(0,10),(1,20)] and rejected==[2]
    assert p.busy==0 and p.busy_integral==20


def test_exact_roundtrip_and_deadline():
    c=load_challenge('team-notes'); d=load_fixture(c.challenge_id,'initial')
    a=arrival(c,0)
    e=Engine(c,d,case(c,[a]),constant_service=True,propagation_us=0,bandwidth_bytes_s=1_024_000)
    out=e.run().outcomes[0]
    # Two request + two response transfers, app local 2ms + SQL read 20ms.
    assert out.terminal_us==26_000 and out.status=='success'
    a=a.model_copy(update={'deadline_us':26_000})
    assert Engine(c,d,case(c,[a]),constant_service=True,propagation_us=0,bandwidth_bytes_s=1_024_000).run().outcomes[0].status=='success'


def test_timeout_does_not_cancel_commit_or_duplicate_terminal():
    c=load_challenge('team-notes'); d=load_fixture(c.challenge_id,'initial')
    a=arrival(c,0,operation=1,deadline=5_000)
    e=Engine(c,d,case(c,[a]),constant_service=True)
    art=e.run()
    assert len(art.outcomes)==1 and art.outcomes[0].status=='timeout'
    assert e.nodes['sql'].history[a.key][-1][1] == 1
    assert any(x.event=='write_committed' for t in art.traces for x in t.events)


def test_zero_arrivals_and_cap_never_pass():
    c=load_challenge('team-notes'); d=load_fixture(c.challenge_id,'initial')
    art=run_case(c,d,case(c,[]))
    assert art.result.operation_metrics['read_note']['response_p95_ms'].value is None
    art=Engine(c,d,case(c,[arrival(c,0)]),max_events=1).run()
    assert art.result.execution_status=='interrupted'
    assert all(r.status=='incomplete' for r in art.result.requirement_outcomes)


def test_cache_expiry_lru_and_generation_fence():
    from backend.simulation import Context, Reply
    c=load_challenge('product-catalogue'); d=load_fixture(c.challenge_id,'reference')
    e=Engine(c,d,case(c,[]),constant_service=True)
    state=e.nodes['cache']; state.profile=state.profile.model_copy(update={'capacity':1})
    state.node.settings['ttl_seconds']=1
    # Isolate the cache lookup/fill contract with a deliberately slow old store response.
    replies=[]
    e.call_edge=lambda ctx,edge,done,attempt=0:e.s.after(100,1,lambda:done(Reply(key=ctx.arrival.key,version=0,size=1)))
    ctx=Context(arrival(c,0)); e.cache(ctx,state,0,0,replies.append,lambda:None)
    e.s.at(50,0,lambda:state.generations[0].__setitem__(ctx.arrival.key,1))
    e.s.run(100)
    assert ctx.arrival.key not in state.caches[0] and replies[0].version==0
    e.cache(Context(arrival(c,1)),state,0,0,replies.append,lambda:None); e.s.run(200)
    assert state.misses==2 and len(state.caches[0])==1
    expiry=state.caches[0][ctx.arrival.key][0]
    e.cache(Context(arrival(c,2)),state,0,0,replies.append,lambda:None)
    assert state.hits==1 and state.caches[0][ctx.arrival.key][0]==expiry
    second=arrival(c,3).model_copy(update={'key':'products:1'})
    e.cache(Context(second),state,0,0,replies.append,lambda:None); e.s.run(300)
    assert list(state.caches[0])==['products:1'] and state.evictions==1
    expiry=state.caches[0]['products:1'][0]
    e.s.at(expiry,3,lambda:e.cache(Context(second),state,0,0,replies.append,lambda:None)); e.s.run(expiry+100)
    assert state.misses==4


def test_invalidation_covers_all_instances_and_clear_fences_fill():
    from backend.simulation import Context, Reply
    from backend.workloads import ScheduledFault
    from backend.contracts import Fault
    c=load_challenge('product-catalogue'); d=load_fixture(c.challenge_id,'reference')
    d.nodes[2].instance_count=2
    e=Engine(c,d,case(c,[]),constant_service=True)
    state=e.nodes['cache']; a=arrival(c,0,operation=1); ctx=Context(a)
    for cache in state.caches: cache[a.key]=(999999,Reply(key=a.key,version=0),1)
    state.cache_bytes=[1,1]
    done=[]; e.invalidate(ctx,e.edges['app-invalidate'],lambda ok:done.append(e.s.now if ok else -1)); e.s.run(10_000)
    assert done==[5000] and all(not cache for cache in state.caches)
    assert [g[a.key] for g in state.generations]==[1,1]
    read=Context(arrival(c,1)); e.call_edge=lambda ctx,edge,done,attempt=0:e.s.after(100,1,lambda:done(Reply(key=ctx.arrival.key,version=0,size=1)))
    e.cache(read,state,0,0,lambda _:None,lambda:None)
    e.s.after(50,0,lambda:e.fault(ScheduledFault(time_us=e.s.now,fault=Fault(type='clear_cache',at_s=0))))
    e.s.run(e.s.now+100)
    assert not state.caches[0]


def test_overlapping_leases_dedup_and_separate_ack_deadline():
    c=load_challenge('notifications'); d=load_fixture(c.challenge_id,'initial')
    queue=next(n for n in d.nodes if n.type=='message_queue'); queue.settings['lease_seconds']=1
    worker=next(n for n in d.nodes if n.type=='worker')
    for dedup,duplicates in [(True,0),(False,1)]:
        worker.settings['deduplicate']=dedup
        e=Engine(c,d,case(c,[arrival(c,0)]),constant_service=True)
        e.nodes[worker.id].multiplier=30
        art=e.run(); job=art.jobs[0]
        assert art.outcomes[0].status=='success' and art.outcomes[0].terminal_us<20_000
        assert job.attempts==2 and job.duplicate_effect_count==duplicates
        assert job.first_effect_us>1_500_000
    # Enqueue-intent denominator includes rejected requests, and slow effects fail deadlines.
    e=Engine(c,d,case(c,[arrival(c,i) for i in range(10)]),constant_service=True)
    e.nodes[worker.id].multiplier=250
    art=e.run()
    assert art.result.operation_metrics['enqueue_notification']['job_deadline_completion_rate'].value==0
    assert len(art.jobs)==10


def test_failure_at_completion_precedes_commit_and_recovery():
    from backend.workloads import ScheduledFault
    from backend.contracts import Fault
    c=load_challenge('team-notes'); d=load_fixture(c.challenge_id,'initial')
    w=case(c,[arrival(c,0),arrival(c,1,time=2_000_000)])
    # App finishes at 2001us (one byte-serialization microsecond plus local service). Crash wins the tie.
    w.faults=[ScheduledFault(time_us=2001,fault=Fault(type='app_instance_unavailable',at_s=0,end_s=1))]
    art=Engine(c,d,w,constant_service=True,propagation_us=0,bandwidth_bytes_s=10**15).run()
    assert art.outcomes[0].status=='dependency_error' and art.outcomes[1].status=='success'
    assert any(s.nodes['app']['unavailable_slots']>0 for s in art.snapshots) is False # outage is between 1s snapshots


def test_retry_safe_only_and_conservation_repeatability():
    c=load_challenge('team-notes'); d=load_fixture(c.challenge_id,'initial')
    app=next(n for n in d.nodes if n.type=='app_service'); app.settings.update(dependency_timeout_ms=1,max_retries=2)
    arrivals=[arrival(c,i,operation=i%2) for i in range(10)]
    e=Engine(c,d,case(c,arrivals),constant_service=True)
    art=e.run()
    assert all(e.contexts[str(i)].attempts==(3 if i%2==0 else 1) for i in range(10))
    assert len({o.request_id for o in art.outcomes})==len(arrivals)
    for n in d.nodes: n.label='renamed'; n.position.x+=17
    again=Engine(c,d,case(c,arrivals),constant_service=True).run()
    assert [o.model_dump() for o in art.outcomes]==[o.model_dump() for o in again.outcomes]
    assert all(0<=v['busy_slots']<=v['available_slots'] and v['queue_depth']>=0 for s in art.snapshots for v in s.nodes.values())


def test_cancel_before_arrival_has_no_negative_duration():
    c=load_challenge('team-notes'); d=load_fixture(c.challenge_id,'initial')
    art=run_case(c,d,case(c,[arrival(c,0,time=9_000_000)]),should_cancel=lambda:True)
    assert art.result.execution_status=='canceled'
    assert art.outcomes[0].status=='incomplete'
    assert art.outcomes[0].terminal_us>=art.outcomes[0].arrival_us
    assert all(r.status=='incomplete' for r in art.result.requirement_outcomes)


def test_fifo_network_serialization_and_reverse_independent():
    from backend.simulation import Context
    c=load_challenge('team-notes'); d=load_fixture(c.challenge_id,'initial')
    e=Engine(c,d,case(c,[]),propagation_us=7,bandwidth_bytes_s=1_000_000)
    edge=e.edges['client-app']; done=[]
    for i in range(2): e.transfer(Context(arrival(c,i)),edge,False,100,lambda i=i:done.append((i,e.s.now)))
    e.transfer(Context(arrival(c,2)),edge,True,100,lambda:done.append((2,e.s.now)))
    e.s.run(207)
    assert done==[(0,107),(2,107),(1,207)]
    assert e.link_wait[edge.id,False]==100


def test_mm1_mean_wait_matches_theory():
    import random
    rng=random.Random(946); s=Scheduler(); pool=Pool(s,1,100_000)
    waits=[]; now=0
    # M/M/1: lambda=.8, mu=1 => Wq=4 seconds; predeclared 15% tolerance.
    for i in range(30_000):
        now+=max(1,round(rng.expovariate(.8)*1_000_000))
        service=max(1,round(rng.expovariate(1)*1_000_000))
        def arrived(i=i,time=now,service=service):
            def start(release):
                if i>=1000: waits.append(s.now-time)
                s.after(service,1,release)
            pool.acquire(start,lambda:None)
        s.at(now,3,arrived)
    s.run(now+1_000_000_000)
    assert len(waits)==29_000
    assert abs(sum(waits)/len(waits)/1_000_000-4)<.6


def test_first_job_failure_trace_survives_hundred_trace_limit():
    c=load_challenge('notifications'); d=load_fixture(c.challenge_id,'initial')
    # First 100 warm successes, then enough synchronous arrivals to miss job deadlines.
    arrivals=[arrival(c,i,time=i*100_000) for i in range(101)]
    arrivals += [arrival(c,101+i,time=11_000_000) for i in range(1000)]
    e=Engine(c,d,case(c,arrivals,end=30_000_000),constant_service=True)
    art=e.run()
    assert len(art.traces)<=100
    failed=next(r for r in art.result.requirement_outcomes if r.requirement_id=='R03')
    assert failed.status=='fail'
    references={t.trace_id for t in art.traces}
    assert any(x.type=='first_violation' and x.artifact_ref in references for x in art.result.evidence)


def test_load_balancer_health_checks_are_delayed_and_per_instance():
    from backend.contracts import DesignRevision, Fault
    from backend.workloads import ScheduledFault
    c=load_challenge('team-notes'); data=load_fixture(c.challenge_id,'initial').model_dump(mode='json')
    lb=dict(data['nodes'][1],id='lb',type='load_balancer',profile_id='lb.small.v1',settings={})
    data['nodes'].append(lb); data['nodes'][1]['instance_count']=2
    data['edges'][0]['target']='lb'
    data['edges'].append(dict(data['edges'][0],id='lb-app',source='lb',target='app'))
    d=DesignRevision.model_validate(data)
    # Request 0 targets failed instance before the first check; later ones skip it.
    arrivals=[arrival(c,i,time=t) for i,t in enumerate([200_000,1_100_000,1_200_000,2_100_000,2_200_000,3_100_000,3_200_000])]
    w=case(c,arrivals); w.faults=[ScheduledFault(time_us=100_000,fault=Fault(type='app_instance_unavailable',at_s=0,end_s=2,target_instance_id='app-0'))]
    e=Engine(c,d,w,constant_service=True); art=e.run()
    assert art.outcomes[0].status=='dependency_error'
    assert all(o.status=='success' for o in art.outcomes[1:])
    traces={t.request_id:t for t in art.traces}
    def instances(i): return [x.details['instance'] for x in traces[str(i)].events if x.event=='service_started' and x.node_id=='app']
    assert instances(3)==instances(4)==[1] # only one successful health check after recovery
    assert set(instances(5)+instances(6))=={0,1}
    assert any(x.event=='fault_ended' for x in traces['0'].events)


def test_object_capacity_rejects_without_successful_overcommit():
    c=load_challenge('photo-delivery'); d=load_fixture(c.challenge_id,'initial')
    a=arrival(c,0,operation=1).model_copy(update={'key':'photos:new:0'})
    b=arrival(c,1,time=100_000,operation=1).model_copy(update={'key':'photos:new:1'})
    e=Engine(c,d,case(c,[a,b]),constant_service=True)
    state=e.nodes['object']; initial=state.stored_bytes
    state.profile=state.profile.model_copy(update={'capacity':initial+a.request_bytes})
    art=e.run()
    assert [o.status for o in art.outcomes]==['success','rejected']
    assert state.stored_bytes==initial+a.request_bytes and state.capacity_violations==1
    assert art.result.operation_metrics['put_photo']['success_rate'].value==.5


def test_gamma_seed_repeatability_and_unrelated_topology_randomness():
    from backend.contracts import DesignRevision
    c=load_challenge('team-notes'); d=load_fixture(c.challenge_id,'initial')
    w=case(c,[arrival(c,i,time=i*5000) for i in range(30)])
    a=run_case(c,d,w)
    data=d.model_dump(mode='json')
    data['nodes'].append(dict(data['nodes'][1],id='unused',label='unrelated'))
    for node in data['nodes']: node['label']='changed'; node['position']['x']+=100
    b=run_case(c,DesignRevision.model_validate(data),w)
    assert a.outcomes==b.outcomes
    assert a.traces==b.traces
    assert a.result.node_metrics['__design__']['cost_credits_per_hour'].value+5==b.result.node_metrics['__design__']['cost_credits_per_hour'].value


def test_service_multiplier_is_interval_scoped():
    from backend.workloads import ScheduledFault
    from backend.contracts import Fault
    c=load_challenge('team-notes'); d=load_fixture(c.challenge_id,'initial')
    w=case(c,[arrival(c,0),arrival(c,1,time=1_100_000)])
    w.faults=[ScheduledFault(time_us=0,fault=Fault(type='service_multiplier',at_s=0,end_s=1,target_node_id='sql',multiplier=2))]
    art=Engine(c,d,w,constant_service=True).run()
    assert [o.terminal_us-o.arrival_us for o in art.outcomes]==[50_040,30_040]


def test_sql_capacity_does_not_scale_with_app_instances():
    c=load_challenge('team-notes'); d=load_fixture(c.challenge_id,'initial')
    d.nodes[1].instance_count=32
    w=case(c,[arrival(c,i) for i in range(20)])
    e=Engine(c,d,w,constant_service=True,propagation_us=0,bandwidth_bytes_s=10**15)
    art=e.run()
    assert e.nodes['sql'].pools[0].slots==2
    # Store needs ten 20ms waves even though all app handlers fit.
    assert max(o.terminal_us for o in art.outcomes)>=202_000
    assert art.result.node_metrics['sql']['queue_depth_max'].value==18


def test_overlapping_faults_recover_only_their_own_capacity():
    from backend.workloads import ScheduledFault
    from backend.contracts import Fault
    c=load_challenge('team-notes'); d=load_fixture(c.challenge_id,'initial'); d.nodes[1].instance_count=2
    e=Engine(c,d,case(c,[]),constant_service=True)
    faults=[
        ScheduledFault(time_us=0,fault=Fault(type='app_instance_unavailable',at_s=0,end_s=1,target_instance_id='app-0')),
        ScheduledFault(time_us=0,fault=Fault(type='app_instance_unavailable',at_s=0,end_s=2,target_instance_id='app-1')),
        ScheduledFault(time_us=0,fault=Fault(type='service_multiplier',at_s=0,end_s=1,target_node_id='sql',multiplier=2)),
        ScheduledFault(time_us=0,fault=Fault(type='service_multiplier',at_s=0,end_s=2,target_node_id='sql',multiplier=3))]
    for f in faults: e.fault(f)
    assert e.nodes['sql'].multiplier==6
    e.s.run(1_000_000)
    assert [p.available for p in e.nodes['app'].pools]==[4,0]
    assert e.nodes['sql'].multiplier==3
    e.s.run(2_000_000)
    assert [p.available for p in e.nodes['app'].pools]==[4,4]
    assert e.nodes['sql'].multiplier==1


def test_accepted_pending_job_distinct_from_rejected_enqueue():
    c=load_challenge('notifications'); d=load_fixture(c.challenge_id,'initial')
    e=Engine(c,d,case(c,[arrival(c,i) for i in range(3)],end=100_000),constant_service=True)
    e.nodes['queue'].profile=e.nodes['queue'].profile.model_copy(update={'capacity':1})
    for pool in e.nodes['worker'].pools: pool.set_available(0)
    art=e.run()
    accepted=[j for j in art.jobs if j.accepted_us is not None]
    rejected=[j for j in art.jobs if j.accepted_us is None]
    assert len(accepted)==1 and accepted[0].terminal_state=='pending'
    assert accepted[0].attempts==0 and accepted[0].acknowledged_us is None
    assert len(rejected)==2 and all(j.terminal_state=='failed' for j in rejected)


def test_recovery_requires_three_full_windows_and_job_targets():
    from backend.workloads import ScheduledFault
    from backend.contracts import Fault
    c=load_challenge('notifications'); d=load_fixture(c.challenge_id,'initial')
    arrivals=[arrival(c,i,time=1_100_000+i*1_000_000) for i in range(39)]
    w=case(c,arrivals,end=41_000_000)
    w.faults=[ScheduledFault(time_us=0,fault=Fault(type='service_multiplier',at_s=0,end_s=1,target_node_id='app',multiplier=2))]
    e=Engine(c,d,w,constant_service=True)
    assert e.run().result.node_metrics['__design__']['recovery_time_ms'].value==30_000
    e=Engine(c,d,w,constant_service=True); e.nodes['worker'].multiplier=1000
    assert e.run().result.node_metrics['__design__']['recovery_time_ms'].value is None


def test_required_fault_stays_on_participating_role_after_topology_addition():
    from backend.contracts import DesignRevision, Fault
    from backend.workloads import ScheduledFault
    c=load_challenge('team-notes'); d=load_fixture(c.challenge_id,'initial')
    w=case(c,[arrival(c,0,time=200_000)])
    w.faults=[ScheduledFault(time_us=100_000,fault=Fault(type='app_instance_unavailable',at_s=0,end_s=1))]
    baseline=Engine(c,d,w,constant_service=True).run()
    data=d.model_dump(mode='json'); data['nodes'].append(dict(data['nodes'][1],id='aaa-unused'))
    candidate=Engine(c,DesignRevision.model_validate(data),w,constant_service=True).run()
    assert baseline.outcomes[0].status=='dependency_error'
    assert candidate.outcomes==baseline.outcomes
    from backend.simulation import fault_bindings
    assert fault_bindings(c,d,w)==fault_bindings(c,DesignRevision.model_validate(data),w)
    w.faults[0].fault.target_node_id='aaa-unused'
    assert Engine(c,DesignRevision.model_validate(data),w,constant_service=True).run().result.execution_status=='interrupted'


def shared_worker_design():
    from backend.contracts import DesignRevision
    c=load_challenge('notifications'); data=load_fixture(c.challenge_id,'initial').model_dump(mode='json')
    app=next(n for n in data['nodes'] if n['type']=='app_service')
    queue=next(n for n in data['nodes'] if n['type']=='message_queue')
    data['nodes'] += [dict(app,id='app-b'),dict(queue,id='queue-b'),dict(app,id='lb',type='load_balancer',profile_id='lb.small.v1',settings={})]
    entry=next(e for e in data['edges'] if e['source']=='client'); entry['target']='lb'
    op=[c.operations[0].id]
    data['edges'] += [dict(id='lb-app',source='lb',target='app',kind='request',operation_ids=op),
        dict(id='lb-app-b',source='lb',target='app-b',kind='request',operation_ids=op),
        dict(id='app-b-queue-b',source='app-b',target='queue-b',kind='request',operation_ids=op),
        dict(id='queue-b-worker',source='queue-b',target='worker',kind='consume',operation_ids=op)]
    return c,DesignRevision.model_validate(data)


def test_shared_worker_release_wakes_other_queue_without_previous_lease():
    c,d=shared_worker_design()
    # The first queue consumes both slots, before the second queue's first admission.
    e=Engine(c,d,case(c,[arrival(c,i,time=i*1000) for i in range(4)]),constant_service=True)
    e.nodes['queue-b'].multiplier=10
    art=e.run()
    assert len(art.jobs)==4 and all(j.accepted_us is not None for j in art.jobs)
    assert all(j.attempts==1 and j.terminal_state=='delivered' for j in art.jobs)
    assert all(j.first_effect_us<200_000 for j in art.jobs)


def test_pool_completion_reserves_fifo_slot_but_dispatch_waits_for_deadlines():
    from backend.simulation import COMPLETE, DEADLINE, DISPATCH
    s=Scheduler(); p=Pool(s,1,2); order=[]
    def work(label):
        def start(release):
            order.append((label,s.now))
            s.after(10,COMPLETE,release)
        p.acquire(start,lambda:order.append(('rejected',s.now)))
    work('first'); work('queued')
    s.at(10,DEADLINE,lambda:order.append(('deadline',s.now)))
    s.at(10,DISPATCH,lambda:work('new'))
    s.run(40)
    assert order==[('first',0),('deadline',10),('queued',10),('new',20)]


def test_worker_release_dispatch_runs_after_same_time_deadline():
    from backend.simulation import DEADLINE
    c=load_challenge('notifications'); d=load_fixture(c.challenge_id,'initial')
    e=Engine(c,d,case(c,[arrival(c,i) for i in range(3)]),constant_service=True)
    # First worker effects occur at 59,015us with default transfer/service times.
    observed=[]
    e.s.at(59_015,DEADLINE,lambda:observed.append(sum(j.attempts for j in e.jobs.values())))
    e.run()
    assert observed==[2] # the queued third job cannot lease until DISPATCH priority


def test_appended_parallel_route_keeps_existing_fault_role():
    from backend.contracts import DesignRevision, Fault
    from backend.workloads import ScheduledFault
    c,d=shared_worker_design()
    # The first compiled app role is 'app'; appended 'aaa' sorts earlier by ID.
    data=d.model_dump(mode='json')
    app=next(n for n in data['nodes'] if n['id']=='app')
    data['nodes'].append(dict(app,id='aaa'))
    data['edges'] += [dict(id='new-lb-aaa',source='lb',target='aaa',kind='request',operation_ids=[c.operations[0].id]),
        dict(id='aaa-queue',source='aaa',target='queue',kind='request',operation_ids=[c.operations[0].id])]
    w=case(c,[]); scheduled=ScheduledFault(time_us=0,fault=Fault(type='app_instance_unavailable',at_s=0,end_s=1))
    baseline=Engine(c,d,w); candidate=Engine(c,DesignRevision.model_validate(data),w)
    baseline.fault(scheduled); candidate.fault(scheduled)
    assert baseline.nodes['app'].pools[0].available==candidate.nodes['app'].pools[0].available==0
    assert candidate.nodes['aaa'].pools[0].available==4


def test_reducing_instances_cannot_remove_frozen_outage_target():
    import pytest
    from backend.contracts import Fault
    from backend.workloads import ScheduledFault
    from backend.simulation import fault_bindings
    c=load_challenge('team-notes'); baseline=load_fixture(c.challenge_id,'initial')
    baseline.nodes[1].instance_count=2
    candidate=baseline.model_copy(deep=True); candidate.nodes[1].instance_count=1
    w=case(c,[arrival(c,0,time=200_000)])
    w.faults=[ScheduledFault(time_us=100_000,fault=Fault(type='app_instance_unavailable',at_s=0,end_s=1,target_node_id='app',target_instance_id='app-1'))]
    assert fault_bindings(c,baseline,w)==[(0,'app_instance_unavailable',('app',),'app-1')]
    with pytest.raises(ValueError,match='fault instance missing'):
        fault_bindings(c,candidate,w)
    e=Engine(c,candidate,w,constant_service=True); artifact=e.run()
    assert artifact.result.execution_status=='interrupted'
    assert all(r.status=='incomplete' for r in artifact.result.requirement_outcomes)
    assert any(item.type=='termination' and 'fault instance missing' in item.value for item in artifact.result.evidence)
    assert not e.fault_ends # Invalid target never installs an unsafe recovery callback.
