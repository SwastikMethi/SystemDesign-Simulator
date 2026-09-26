"""Integer-time discrete event model. SimPy owns the stable priority event heap."""
from __future__ import annotations

import hashlib
import math
import random
from collections import OrderedDict, defaultdict, deque
from dataclasses import dataclass, field
from typing import Any

import simpy
from pydantic import Field

from backend.contracts import (CaseResult, Challenge, DesignRevision, JobOutcome, RequestOutcome,
                               Strict, compile_design, profile_for)
from backend.workloads import Arrival, WorkloadCase, generate_case

FAULT, COMPLETE, DEADLINE, DISPATCH, SNAPSHOT = range(5)
MAX_EVENTS = 2_000_000
MAX_ARRIVALS = 100_000
MAX_DURATION_US = 3_600_000_000


class TraceEvent(Strict):
    time_us: int
    event: str
    node_id: str | None = None
    edge_id: str | None = None
    request_id: str | None = None
    attempt_id: str | None = None
    job_id: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class Trace(Strict):
    trace_id: str
    request_id: str
    operation_id: str
    events: list[TraceEvent]


class Snapshot(Strict):
    time_us: int
    nodes: dict[str, dict[str, float | int]]


class CaseArtifacts(Strict):
    result: CaseResult
    outcomes: list[RequestOutcome]
    jobs: list[JobOutcome]
    snapshots: list[Snapshot]
    traces: list[Trace]


class Scheduler:
    """All domain state changes use explicit priorities, including completion callbacks."""
    def __init__(self):
        self.env = simpy.Environment()
        self.events = 0

    @property
    def now(self):
        return int(self.env.now)

    def at(self, when, priority, callback):
        if when < self.now:
            raise ValueError('cannot schedule into the past')
        event = simpy.Event(self.env)
        event._ok, event._value = True, None
        event.callbacks.append(lambda _: callback())
        self.env.schedule(event, priority=priority, delay=int(when)-self.now)

    def after(self, delay, priority, callback):
        self.at(self.now + int(delay), priority, callback)

    def run(self, until, *, max_events=MAX_EVENTS, should_cancel=None):
        while self.env.peek() <= until:
            if self.events >= max_events:
                return 'event cap exceeded'
            if self.events % 1024 == 0 and should_cancel and should_cancel():
                return 'canceled'
            self.env.step()
            self.events += 1
        return None


class Pool:
    """Finite FIFO waiting room; handlers can retain a slot during dependencies."""
    def __init__(self, scheduler, slots, queue_limit):
        self.s = scheduler
        self.slots = slots
        self.available = slots
        self.queue_limit = queue_limit
        self.waiting = deque()
        self.active = {}
        self.busy = 0
        self.last_time = 0
        self.busy_integral = self.available_integral = self.queue_integral = 0
        self.wait_total = self.serviced = self.rejections = 0
        self.max_queue = 0
        self.serial = 0

    def integrate(self):
        dt = self.s.now-self.last_time
        self.busy_integral += dt*self.busy
        self.available_integral += dt*self.available
        self.queue_integral += dt*len(self.waiting)
        self.last_time = self.s.now

    def acquire(self, start, reject, abort=None):
        self.integrate()
        if not self.available:
            self.rejections += 1
            reject()
        elif self.busy < self.available:
            self._start(start, reject, abort, self.s.now)
        elif len(self.waiting) < self.queue_limit:
            self.waiting.append((start, reject, abort, self.s.now))
            self.max_queue = max(self.max_queue,len(self.waiting))
        else:
            self.rejections += 1
            reject()

    def _start(self, start, reject, abort, arrived):
        self.serial += 1
        token = self.serial
        self.busy += 1
        self.serviced += 1
        self.wait_total += self.s.now-arrived
        def release():
            if token not in self.active:
                return
            self.integrate()
            del self.active[token]
            self.busy -= 1
            if self.waiting and self.busy < self.available:
                self._start(*self.waiting.popleft())
        self.active[token] = abort or reject
        start(release)

    def set_available(self, available):
        self.integrate()
        if not available:
            self.available = 0
            callbacks = list(self.active.values()) + [item[2] or item[1] for item in self.waiting]
            self.active.clear()
            self.waiting.clear()
            self.busy = 0
            for callback in callbacks:
                callback()
        else:
            self.available = available


@dataclass(slots=True)
class Reply:
    status: str = 'success'
    key: str | None = None
    payload: str | None = None
    version: int | None = None
    commit_us: int | None = None
    size: int = 0
    store_id: str | None = None


@dataclass(slots=True)
class Context:
    arrival: Arrival
    events: list = field(default_factory=list)
    terminal: RequestOutcome | None = None
    attempts: int = 1
    retained: bool = False


@dataclass(slots=True)
class Job:
    ctx: Context
    queue_id: str
    accepted_us: int = 0
    attempts: int = 0
    first_effect: int | None = None
    ack: int | None = None
    effects: int = 0
    state: str = 'pending'
    outstanding: bool = True
    active_attempts: int = 0


class NodeState:
    def __init__(self, engine, node):
        self.node, self.profile = node, profile_for(node)
        self.pools = [Pool(engine.s,self.profile.slots,self.profile.queue_limit) for _ in range(node.instance_count)]
        self.rr = self.route_rr = 0
        self.multiplier = 1.0
        self.multipliers = {}
        self.failures = [0 for _ in self.pools]
        self.caches = [OrderedDict() for _ in self.pools]
        self.generations = [defaultdict(int) for _ in self.pools]
        self.clear_generation = [0 for _ in self.pools]
        self.cache_bytes = [0 for _ in self.pools]
        self.hits = self.misses = self.evictions = 0
        self.max_queue = 0
        self.history = {}
        self.records = engine.challenge.initial_data.record_count
        self.stored_bytes = self.records*(engine.challenge.initial_data.object_bytes or 0)
        self.capacity_violations = 0
        self.pending = deque()
        self.buffer_count = 0
        self.tokens = float(node.settings.get('bucket_size', node.settings.get('rate_limit_rps', 1)))
        self.token_time = 0


class Engine:
    def __init__(self, challenge, design, workload, *, on_progress=None, should_cancel=None,
                 constant_service=False, propagation_us=2000, bandwidth_bytes_s=100*(1<<20), max_events=MAX_EVENTS):
        self.challenge, self.design, self.workload = challenge, design, workload
        self.compiled = compile_design(design, challenge)
        if (workload.challenge_id, workload.challenge_version) != (challenge.challenge_id, challenge.version):
            raise ValueError('workload/challenge mismatch')
        if len(workload.arrivals)>MAX_ARRIVALS or workload.drain_end_us>MAX_DURATION_US:
            raise ValueError('case resource cap exceeded')
        if not 0<=workload.warmup_end_us<workload.measurement_end_us<workload.drain_end_us:
            raise ValueError('invalid workload intervals')
        ids={a.request_id for a in workload.arrivals}
        allowed_ops={op.id for op in challenge.operations}
        if len(ids)!=len(workload.arrivals) or any(a.operation_id not in allowed_ops or a.deadline_us<=a.time_us or min(a.request_bytes,a.response_bytes)<0 for a in workload.arrivals):
            raise ValueError('invalid original arrival identity or payload')
        self.s = Scheduler()
        self.on_progress, self.should_cancel = on_progress, should_cancel
        self.constant_service, self.propagation_us = constant_service, propagation_us
        self.bandwidth, self.max_events = bandwidth_bytes_s, max_events
        self.nodes = {n.id:NodeState(self,n) for n in sorted(design.nodes,key=lambda n:n.id)}
        self.operations = {op.id:op for op in challenge.operations}
        self.edges = {e.id:e for e in design.edges}
        self.outgoing = defaultdict(list)
        for edge in sorted(design.edges,key=lambda e:e.id):
            for op in edge.operation_ids:
                self.outgoing[edge.source,op,edge.kind].append(edge)
        self.link_free = defaultdict(int)
        self.link_wait = defaultdict(int)
        self.contexts = {}
        self.outcomes = []
        self.jobs = {}
        self.snapshots = []
        self.traces = OrderedDict()
        self.first_failures = {}
        self.health = {}
        self.health_successes = defaultdict(int)
        self.fault_ends = []
        self.diagnostics = []

    def emit(self, ctx, event, node_id=None, edge_id=None, attempt=0, job_id=None, **details):
        # Each request's trace is also bounded, including attempts and late work.
        job=self.jobs.get(ctx.arrival.request_id)
        if (ctx.terminal is None or ctx.retained or (job and (job.outstanding or job.active_attempts))) and len(ctx.events)<200:
            ctx.events.append((self.s.now,event,node_id,edge_id,attempt,job_id,details))

    def rng(self, ctx, node_id, attempt, purpose):
        key=f'{self.workload.seed}|{ctx.arrival.request_id}|{node_id}|{attempt}|{ctx.arrival.operation_id}|{purpose}'
        return random.Random(int.from_bytes(hashlib.blake2b(key.encode(),digest_size=8).digest(),'big'))

    def duration(self, ctx, state, attempt=0):
        op=self.operations[ctx.arrival.operation_id]
        mean=state.profile.write_service_ms if op.kind in {'write_key','put_object'} and state.profile.write_service_ms else state.profile.service_ms
        mean *= 1000*state.multiplier
        cv=0 if self.constant_service else state.profile.coefficient_of_variation
        value=mean if not cv else self.rng(ctx,state.node.id,attempt,'service').gammavariate(1/(cv*cv),mean*cv*cv)
        return max(1,round(value))

    def transfer(self, ctx, edge, reverse, size, done, attempt=0):
        key=(edge.id,reverse)
        start=max(self.s.now,self.link_free[key])
        delay=math.ceil(size*1_000_000/self.bandwidth)
        self.link_wait[key]+=start-self.s.now
        self.link_free[key]=start+delay
        self.emit(ctx,'response_sent' if reverse else 'downstream_started',edge_id=edge.id,attempt=attempt,
                  bytes=size,queue_wait_us=start-self.s.now,transfer_us=delay,propagation_us=self.propagation_us)
        self.s.at(start+delay+self.propagation_us,COMPLETE,done)

    def call_edge(self, ctx, edge, done, attempt=0, target_instance=None):
        def arrived():
            self.enter(ctx,edge.target,lambda reply:self.transfer(ctx,edge,True,ctx.arrival.response_bytes if reply.status=='success' else 0,
                lambda:done(reply),attempt),attempt,target_instance)
        self.transfer(ctx,edge,False,ctx.arrival.request_bytes,arrived,attempt)

    def enter(self, ctx, node_id, done, attempt=0, target_instance=None):
        state=self.nodes[node_id]; node=state.node; op=self.operations[ctx.arrival.operation_id]
        instance=state.rr % len(state.pools) if target_instance is None else target_instance
        state.rr+=1
        pool=state.pools[instance]
        self.emit(ctx,'arrived',node_id,attempt=attempt,instance=instance)
        finished=False
        release=None
        def finish(reply):
            nonlocal finished
            if finished: return
            finished=True
            if release: release()
            done(reply)
        def abort():
            self.emit(ctx,'rejected',node_id,attempt=attempt,reason='instance unavailable')
            finish(Reply(status='dependency_error'))
        def reject():
            self.emit(ctx,'rejected',node_id,attempt=attempt,reason='finite queue full' if pool.available else 'instance unavailable')
            finish(Reply(status='rejected' if pool.available else 'dependency_error'))
        def start(slot_release):
            nonlocal release
            release=slot_release
            service_us=self.duration(ctx,state,attempt)
            self.emit(ctx,'service_started',node_id,attempt=attempt,instance=instance,service_us=service_us)
            def local_done():
                if finished: return
                self.emit(ctx,'service_finished',node_id,attempt=attempt,instance=instance)
                if node.type in {'sql_database','object_storage'}:
                    finish(self.store(ctx,state))
                elif node.type in {'cache','cdn'}:
                    self.cache(ctx,state,instance,attempt,finish,release)
                elif node.type=='message_queue':
                    if state.buffer_count>=state.profile.capacity:
                        finish(Reply(status='rejected'))
                    else:
                        job=Job(ctx,node_id,accepted_us=self.s.now); self.jobs[ctx.arrival.request_id]=job
                        state.buffer_count+=1; state.pending.append(job)
                        self.emit(ctx,'enqueue_accepted',node_id,job_id=ctx.arrival.request_id)
                        finish(Reply(key=ctx.arrival.key,payload=ctx.arrival.payload_id))
                        self.dispatch_jobs(state)
                else:
                    if node.type=='api_gateway' and 'rate_limit_rps' in node.settings:
                        rate=node.settings['rate_limit_rps']; capacity=node.settings.get('bucket_size',rate)
                        state.tokens=min(capacity,state.tokens+(self.s.now-state.token_time)*rate/1_000_000)
                        state.token_time=self.s.now
                        if state.tokens<1:
                            self.emit(ctx,'rejected',node_id,reason='rate limited')
                            finish(Reply(status='rejected')); return
                        state.tokens-=1
                    routes=self.outgoing[node_id,op.id,'request']
                    if node.type=='load_balancer':
                        targets=[(e,i) for e in routes for i in range(len(self.nodes[e.target].pools)) if self.health.get((node_id,e.target,i),True)]
                        if not targets:
                            finish(Reply(status='dependency_error')); return
                        edge,target_instance=targets[state.route_rr % len(targets)]; state.route_rr+=1
                        self.call_edge(ctx,edge,finish,attempt,target_instance); return
                    if not routes:
                        finish(Reply(status='dependency_error')); return
                    edge=routes[state.route_rr % len(routes)]; state.route_rr+=1
                    if node.type=='app_service':
                        self.dependency(ctx,state,edge,attempt,finish,lambda:not finished)
                    else:
                        self.call_edge(ctx,edge,finish,attempt)
            self.s.after(service_us,COMPLETE,local_done)
        if pool.busy>=pool.available:
            self.emit(ctx,'queued',node_id,attempt=attempt,instance=instance)
        pool.acquire(start,reject,abort)
        state.max_queue=max(state.max_queue,sum(len(p.waiting) for p in state.pools))

    def dependency(self, ctx, state, edge, parent_attempt, finish, is_active):
        op=self.operations[ctx.arrival.operation_id]
        max_retries=state.node.settings.get('max_retries',0) if op.retry_safe and op.kind not in {'write_key','put_object','enqueue_job'} else 0
        def launch(index):
            if self.s.now>=ctx.arrival.deadline_us:
                finish(Reply(status='timeout')); return
            if index: ctx.attempts+=1
            attempt=parent_attempt+index
            settled=False
            def settle(reply):
                nonlocal settled
                if settled or not is_active(): return
                settled=True
                if reply.status!='success' and index<max_retries and self.s.now<ctx.arrival.deadline_us:
                    delay=round(self.rng(ctx,state.node.id,attempt,'retry').random()*100_000*(2**index))
                    self.emit(ctx,'retry_scheduled',state.node.id,attempt=attempt,delay_us=delay)
                    self.s.after(delay,DISPATCH,lambda:launch(index+1))
                elif reply.status=='success' and op.kind=='write_key' and state.node.settings.get('invalidation')=='synchronous':
                    edges=self.outgoing[state.node.id,op.id,'invalidate']
                    if not edges: finish(reply); return
                    remaining=len(edges)
                    invalidation_ok=True
                    def invalidated(ok):
                        nonlocal remaining, invalidation_ok
                        invalidation_ok &= ok
                        remaining-=1
                        if not remaining: finish(reply if invalidation_ok else Reply(status='dependency_error'))
                    for inv in edges: self.invalidate(ctx,inv,invalidated)
                else: finish(reply)
            limit=min(ctx.arrival.deadline_us,self.s.now+state.node.settings.get('dependency_timeout_ms',2000)*1000)
            self.s.at(limit,DEADLINE,lambda:settle(Reply(status='dependency_error')))
            self.call_edge(ctx,edge,settle,attempt)
        launch(0)

    def initial(self,key):
        prefix=self.challenge.initial_data.namespace+':'
        suffix=key[len(prefix):] if key.startswith(prefix) else ''
        return suffix.isdigit() and int(suffix)<self.challenge.initial_data.record_count

    def history(self,state,key):
        if key not in state.history:
            state.history[key]=[(0,self.challenge.initial_data.initial_version,'initial:'+key,self.challenge.initial_data.object_bytes or 0)] if self.initial(key) else []
        return state.history[key]

    def store(self,ctx,state):
        a=ctx.arrival; op=self.operations[a.operation_id]; history=self.history(state,a.key)
        if op.kind in {'write_key','put_object'}:
            new=not history
            if (state.node.type=='sql_database' and new and state.records>=state.profile.capacity) or (state.node.type=='object_storage' and state.stored_bytes+a.request_bytes-(history[-1][3] if history else 0)>state.profile.capacity):
                state.capacity_violations+=1
                self.emit(ctx,'rejected',state.node.id,reason='storage capacity')
                return Reply(status='rejected')
            version=history[-1][1]+1 if history else 1
            if new: state.records+=1
            if state.node.type=='object_storage': state.stored_bytes+=a.request_bytes-(history[-1][3] if history else 0)
            history.append((self.s.now,version,a.payload_id,a.request_bytes))
            self.emit(ctx,'write_committed',state.node.id,version=version,key=a.key)
        if not history: return Reply(status='invalid_result')
        commit,version,payload,size=history[-1]
        return Reply(key=a.key,payload=payload,version=version,commit_us=commit,size=size,store_id=state.node.id)

    def cache(self,ctx,state,instance,attempt,finish,release):
        key=ctx.arrival.key; entries=state.caches[instance]
        entry=entries.get(key)
        if entry and entry[0]>self.s.now:
            state.hits+=1; entries.move_to_end(key)
            self.emit(ctx,'cache_hit',state.node.id,attempt=attempt,version=entry[1].version)
            finish(entry[1]); return
        if entry:
            state.cache_bytes[instance]-=entries.pop(key)[2]
        state.misses+=1
        self.emit(ctx,'cache_miss',state.node.id,attempt=attempt)
        generation=(state.clear_generation[instance],state.generations[instance][key])
        # Cache lookup slots release before fetching; concurrent misses remain independent.
        release()
        edge=self.outgoing[state.node.id,ctx.arrival.operation_id,'cache_miss'][0]
        def fetched(reply):
            if reply.status=='success' and generation==(state.clear_generation[instance],state.generations[instance][key]):
                size=reply.size if state.node.type=='cdn' else 1
                if size<=state.profile.capacity:
                    if key in entries: state.cache_bytes[instance]-=entries.pop(key)[2]
                    while entries and state.cache_bytes[instance]+size>state.profile.capacity:
                        evicted,old=entries.popitem(last=False); state.cache_bytes[instance]-=old[2]
                        state.evictions+=1
                        self.emit(ctx,'cache_evicted',state.node.id,key=evicted)
                    entries[key]=(self.s.now+state.node.settings.get('ttl_seconds',60)*1_000_000,reply,size)
                    state.cache_bytes[instance]+=size
            finish(reply)
        self.call_edge(ctx,edge,fetched,attempt)

    def invalidate(self,ctx,edge,done):
        state=self.nodes[edge.target]
        def arrived():
            remaining=len(state.pools)
            accepted=True
            def acknowledged(ok=True):
                nonlocal remaining, accepted
                accepted &= ok
                remaining-=1
                if not remaining: self.transfer(ctx,edge,True,0,lambda:done(accepted))
            for i,pool in enumerate(state.pools):
                def start(release,i=i):
                    def complete():
                        key=ctx.arrival.key
                        state.generations[i][key]+=1
                        entry=state.caches[i].pop(key,None)
                        if entry: state.cache_bytes[i]-=entry[2]
                        self.emit(ctx,'cache_invalidated',edge.target,edge.id,instance=i,key=key)
                        release(); acknowledged()
                    self.s.after(self.duration(ctx,state),COMPLETE,complete)
                # Invalidations share finite cache capacity; a full queue must fail the write acknowledgement.
                pool.acquire(start,lambda: self.invalidate_failed(ctx,edge,acknowledged))
                state.max_queue=max(state.max_queue,sum(len(p.waiting) for p in state.pools))
        self.transfer(ctx,edge,False,0,arrived)

    def invalidate_failed(self,ctx,edge,done):
        # No successful acknowledgement may claim invalidation that was rejected.
        self.emit(ctx,'rejected',edge.target,edge.id,reason='invalidation queue full')
        done(False)

    def dispatch_jobs(self,state):
        if not state.pending: return
        while state.pending:
            if not state.pending[0].outstanding:
                state.pending.popleft(); continue
            edges=self.outgoing[state.node.id,state.pending[0].ctx.arrival.operation_id,'consume']
            choices=[(edge,i,p) for edge in edges for i,p in enumerate(self.nodes[edge.target].pools)]
            selected=None
            for _ in choices:
                edge,i,pool=choices[state.route_rr % len(choices)]; state.route_rr+=1
                if pool.busy<pool.available:
                    selected=(edge,i,pool); break
            if selected is None: return
            edge,i,pool=selected
            job=state.pending.popleft()
            worker=self.nodes[edge.target]
            job.attempts+=1; job.active_attempts+=1; attempt=job.attempts
            ctx=job.ctx; job_id=ctx.arrival.request_id
            self.emit(ctx,'job_leased',state.node.id,edge.id,attempt=attempt,job_id=job_id)
            lease=state.node.settings.get('lease_seconds',5)*1_000_000
            max_attempts=state.node.settings.get('max_attempts',3)
            def expired(job=job,state=state,attempt=attempt,max_attempts=max_attempts):
                if not job.outstanding or job.attempts!=attempt: return
                self.emit(job.ctx,'job_released',state.node.id,attempt=attempt,job_id=job.ctx.arrival.request_id)
                if job.attempts<max_attempts:
                    state.pending.append(job); self.dispatch_jobs(state)
                else:
                    job.state='failed'; job.outstanding=False; state.buffer_count-=1
            self.s.after(lease,DEADLINE,expired)
            def start(release,job=job,worker=worker,edge=edge,attempt=attempt,state=state):
                def delivered():
                    self.emit(job.ctx,'service_started',worker.node.id,attempt=attempt,job_id=job.ctx.arrival.request_id)
                    def effect():
                        dedup=worker.node.settings.get('deduplicate',True)
                        if not dedup or job.effects==0:
                            job.effects+=1
                            if job.effects>1: self.retain_failure(job.ctx,'duplicate_effect')
                            if job.first_effect is None: job.first_effect=self.s.now
                            self.emit(job.ctx,'job_effect',worker.node.id,attempt=attempt,job_id=job.ctx.arrival.request_id,duplicate=job.effects>1)
                        job.active_attempts-=1
                        release()
                        def ack():
                            if job.ack is None: job.ack=self.s.now
                            job.state='delivered'
                            if job.outstanding: job.outstanding=False; state.buffer_count-=1
                            self.emit(job.ctx,'job_acknowledged',state.node.id,attempt=attempt,job_id=job.ctx.arrival.request_id)
                            self.dispatch_jobs(state)
                            if not job.active_attempts and not job.ctx.retained: job.ctx.events.clear()
                        self.transfer(job.ctx,edge,True,0,ack,attempt)
                        self.dispatch_jobs(state)
                    self.s.after(self.duration(job.ctx,worker,attempt),COMPLETE,effect)
                self.transfer(job.ctx,edge,False,job.ctx.arrival.request_bytes,delivered,attempt)
            pool.acquire(start,lambda:None)

    def retain_failure(self,ctx,category):
        a=ctx.arrival
        if not self.workload.warmup_end_us<=a.time_us<self.workload.measurement_end_us: return
        key=(a.operation_id,category)
        if key in self.first_failures: return
        self.first_failures[key]=a.request_id
        if a.request_id in self.traces: return
        if len(self.traces)>=100:
            pinned=set(self.first_failures.values())
            victim=next((k for k in reversed(self.traces) if k not in pinned),None)
            if victim is not None:
                old=self.traces.pop(victim); old.retained=False
        if len(self.traces)<100:
            self.traces[a.request_id]=ctx; ctx.retained=True

    def terminal(self,ctx,reply):
        if ctx.terminal is not None: return
        a=ctx.arrival; op=self.operations[a.operation_id]
        correct=fresh=None
        if reply.status=='success':
            if op.kind=='enqueue_job': correct=a.request_id in self.jobs
            elif reply.store_id:
                hist=self.history(self.nodes[reply.store_id],a.key)
                correct=reply.key==a.key and any(v==reply.version and p==reply.payload and t<=self.s.now for t,v,p,_ in hist)
                if op.kind=='get_object': correct=correct and reply.size==a.response_bytes
                if op.kind=='read_key' and correct and op.freshness_allowance_ms is not None:
                    cutoff=self.s.now-op.freshness_allowance_ms*1000
                    required=next((v for t,v,_,_ in reversed(hist) if t<=cutoff),self.challenge.initial_data.initial_version)
                    fresh=reply.version>=required
            else: correct=False
            if not correct: reply.status='invalid_result'
        out=RequestOutcome(request_id=a.request_id,operation_id=a.operation_id,key=a.key,arrival_us=a.time_us,
            deadline_us=a.deadline_us,terminal_us=max(self.s.now,a.time_us),status=reply.status,returned_payload_id=reply.payload,
            returned_version=reply.version,correct=correct,fresh=fresh,
            acknowledged_commit_us=reply.commit_us if op.kind in {'write_key','put_object'} and reply.status=='success' else None)
        self.emit(ctx,'terminal_outcome',status=out.status,correct=correct,fresh=fresh)
        ctx.terminal=out; self.outcomes.append(out)
        failure=out.status if out.status!='success' else ('freshness' if fresh is False else None)
        cohort=self.workload.warmup_end_us<=a.time_us<self.workload.measurement_end_us
        failure_key=(a.operation_id,failure)
        important=cohort and failure and failure_key not in self.first_failures
        if important: self.first_failures[failure_key]=a.request_id
        if important or (cohort and len(self.traces)<100):
            if len(self.traces)>=100:
                pinned=set(self.first_failures.values())
                victim=next((k for k in reversed(self.traces) if k not in pinned),None)
                if victim is not None: del self.traces[victim]
            if len(self.traces)<100: self.traces[a.request_id]=ctx; ctx.retained=True
        if not ctx.retained and op.kind!='enqueue_job': ctx.events.clear()

    def arrive(self,a):
        ctx=Context(a); self.contexts[a.request_id]=ctx
        self.emit(ctx,'arrived',self.compiled.routes[a.operation_id].entry_node_id)
        def timeout():
            if ctx.terminal is None:
                self.emit(ctx,'timed_out')
                self.terminal(ctx,Reply(status='timeout'))
        self.s.at(a.deadline_us,DEADLINE,timeout)
        op=self.operations[a.operation_id]
        if op.kind=='enqueue_job':
            def job_deadline():
                job=self.jobs.get(a.request_id)
                if job is None or job.first_effect is None:
                    self.retain_failure(ctx,'job_deadline')
                    self.emit(ctx,'job_deadline_missed',job_id=a.request_id)
                if not ctx.retained and (job is None or not job.active_attempts and not job.outstanding): ctx.events.clear()
            self.s.at(a.time_us+op.job_deadline_ms*1000,DEADLINE,job_deadline)
        edge=self.outgoing[self.compiled.routes[a.operation_id].entry_node_id,a.operation_id,'request'][0]
        self.call_edge(ctx,edge,lambda reply:self.terminal(ctx,reply))

    def fault(self,scheduled):
        fault=scheduled.fault
        targets=[state for state in self.nodes.values() if (fault.target_node_id==state.node.id if fault.target_node_id else state.node.type==(fault.target_component_type or ('cdn' if fault.type=='clear_cdn' else 'cache' if fault.type=='clear_cache' else 'app_service')))]
        if not targets:
            if fault.type not in {'clear_cache','clear_cdn'}: self.diagnostics.append('fault target missing')
            return
        if fault.type=='app_instance_unavailable': targets=targets[:1]
        for state in targets:
            for ctx in self.contexts.values():
                if ctx.terminal is None or ctx.retained:
                    self.emit(ctx,'fault_started',state.node.id,fault_type=fault.type)
            if fault.type in {'clear_cache','clear_cdn'}:
                for i in range(len(state.pools)):
                    state.caches[i].clear(); state.cache_bytes[i]=0; state.clear_generation[i]+=1
            elif fault.type=='service_multiplier':
                state.multipliers[id(scheduled)]=fault.multiplier or 1
                state.multiplier=math.prod(state.multipliers.values())
            else:
                raw=(fault.target_instance_id or '0').split('-')[-1]
                instance=int(raw) if raw.isdigit() else -1
                if not 0<=instance<len(state.pools): self.diagnostics.append('fault instance missing'); continue
                state.failures[instance]+=1
                state.pools[instance].set_available(0)
            if fault.end_s is not None:
                end=self.workload.warmup_end_us+fault.end_s*1_000_000
                self.fault_ends.append(end)
                def recover(state=state,fault=fault,instance=instance if fault.type=='app_instance_unavailable' else None):
                    for ctx in self.contexts.values():
                        if ctx.terminal is None or ctx.retained:
                            self.emit(ctx,'fault_ended',state.node.id,fault_type=fault.type)
                    if fault.type=='service_multiplier':
                        state.multipliers.pop(id(scheduled),None)
                        state.multiplier=math.prod(state.multipliers.values())
                    elif fault.type=='app_instance_unavailable':
                        state.failures[instance]-=1
                        if not state.failures[instance]:
                            pool=state.pools[instance]; pool.set_available(pool.slots)
                self.s.at(end,FAULT,recover)

    def health_check(self):
        for state in self.nodes.values():
            if state.node.type!='load_balancer': continue
            targets={e.target for e in self.design.edges if e.source==state.node.id and e.kind=='request'}
            for target in sorted(targets):
                for i,pool in enumerate(self.nodes[target].pools):
                    key=(state.node.id,target,i)
                    if not pool.available: self.health[key]=False; self.health_successes[key]=0
                    else:
                        self.health_successes[key]+=1
                        if self.health_successes[key]>=2: self.health[key]=True
        if self.s.now+1_000_000<=self.workload.drain_end_us:
            self.s.after(1_000_000,FAULT,self.health_check)

    def snapshot(self):
        nodes={}
        for node_id,state in self.nodes.items():
            for pool in state.pools: pool.integrate()
            data={'busy_slots':sum(p.busy for p in state.pools),'available_slots':sum(p.available for p in state.pools),
                  'queue_depth':sum(len(p.waiting) for p in state.pools),'service_multiplier':state.multiplier,'unavailable_slots':sum(p.slots-p.available for p in state.pools)}
            if state.node.type in {'cache','cdn'}: data.update(cache_hits=state.hits,cache_misses=state.misses)
            if state.node.type=='message_queue': data.update(backlog=sum(j.outstanding for j in state.pending),accepted_pending=state.buffer_count)
            nodes[node_id]=data
        snap=Snapshot(time_us=self.s.now,nodes=nodes); self.snapshots.append(snap)
        if self.on_progress: self.on_progress({'time_us':self.s.now,'snapshot':snap.model_dump(mode='json')})
        if self.s.now+1_000_000<=self.workload.drain_end_us:
            self.s.after(1_000_000,SNAPSHOT,self.snapshot)

    def run(self):
        for a in self.workload.arrivals:
            if a.time_us>=self.workload.measurement_end_us: continue
            self.s.at(a.time_us,DISPATCH,lambda a=a:self.arrive(a))
        for fault in self.workload.faults: self.s.at(fault.time_us,FAULT,lambda fault=fault:self.fault(fault))
        self.s.at(0,SNAPSHOT,self.snapshot)
        self.s.at(self.workload.drain_end_us,SNAPSHOT+1,lambda:None)
        if any(s.node.type=='load_balancer' for s in self.nodes.values()): self.s.at(1_000_000,FAULT,self.health_check)
        reason=self.s.run(self.workload.drain_end_us,max_events=self.max_events,should_cancel=self.should_cancel)
        for a in self.workload.arrivals:
            if a.time_us>=self.workload.measurement_end_us: continue
            ctx=self.contexts.get(a.request_id)
            if ctx is None: ctx=Context(a); self.contexts[a.request_id]=ctx
            if ctx.terminal is None: self.terminal(ctx,Reply(status='incomplete'))
        for state in self.nodes.values():
            for pool in state.pools: pool.integrate()
        traces=[Trace(trace_id='trace:'+ctx.arrival.request_id,request_id=ctx.arrival.request_id,operation_id=ctx.arrival.operation_id,
            events=[TraceEvent(time_us=t,event=ev,node_id=node,edge_id=edge,request_id=ctx.arrival.request_id,
                  attempt_id=f'{ctx.arrival.request_id}:{attempt}',job_id=job,details=details) for t,ev,node,edge,attempt,job,details in ctx.events]) for ctx in self.traces.values()]
        jobs=[]
        for a in self.workload.arrivals:
            if self.operations[a.operation_id].kind!='enqueue_job' or a.time_us>=self.workload.measurement_end_us: continue
            job=self.jobs.get(a.request_id)
            jobs.append(JobOutcome(job_id=a.request_id,request_id=a.request_id,accepted_us=job.accepted_us if job else None,attempts=job.attempts if job else 0,
                acknowledged_us=job.ack if job else None,first_effect_us=job.first_effect if job else None,
                terminal_state=('delivered' if job.first_effect is not None else 'failed' if job.state=='failed' else 'expired' if self.s.now>=a.time_us+self.operations[a.operation_id].job_deadline_ms*1000 else 'pending') if job else 'failed',
                duplicate_effect_count=max(0,job.effects-1) if job else 0))
        from backend.assessment import evaluate_case
        result=evaluate_case(self,jobs,traces,'canceled' if reason=='canceled' else 'interrupted' if reason or self.diagnostics else 'completed',reason)
        return CaseArtifacts(result=result,outcomes=sorted(self.outcomes,key=lambda o:(o.arrival_us,o.request_id)),jobs=jobs,snapshots=self.snapshots,traces=traces)


def run_case(challenge: Challenge, design: DesignRevision, workload: WorkloadCase, *, on_progress=None, should_cancel=None) -> CaseArtifacts:
    return Engine(challenge,design,workload,on_progress=on_progress,should_cancel=should_cancel).run()


def run_suite(challenge,design,*,mode='assessment',on_progress=None,should_cancel=None):
    from backend.assessment import assess_suite
    artifacts=[]
    scenarios=[s for s in challenge.scenarios if s.required]
    for scenario in scenarios[:1] if mode=='preview' else scenarios:
        for seed in [101] if mode=='preview' else challenge.workload.assessment_seeds:
            art=run_case(challenge,design,generate_case(challenge,scenario.id,seed,mode),on_progress=on_progress,should_cancel=should_cancel)
            artifacts.append(art)
            if art.result.execution_status!='completed':
                return assess_suite(challenge,[a.result for a in artifacts],mode=mode),artifacts
    return assess_suite(challenge,[a.result for a in artifacts],mode=mode),artifacts
