import type { components } from './schema'

type S = components['schemas']
export type Challenge = S['Challenge']
export type ChallengeSummary = S['ChallengeSummary']
export type Catalogue = S['Catalogue']
export type Design = S['DesignRevision']
export type DesignNode = Design['nodes'][number]
export type DesignEdge = S['Edge']
export type Validation = S['ValidationResult']
export type Run = S['RunManifest']
export type Results = S['RunResults']
export type Case = S['CaseResult']
export type Outcome = S['RequirementOutcome']
export type Metric = S['MetricValue']
export type SnapshotPage = S['SnapshotPage']
export type Snapshot = S['Snapshot']
export type Trace = S['Trace']
export type Profile = S['Profile']
export type Review = S['ReviewRecord']
export type Comparison = S['ComparisonRecord']
export type CollectionItem = S['CollectionItem']
export type SavedSnapshot = S['SavedSnapshot']
export type Guidance = S['GuidanceRecord']
export type ReferenceAnswer = S['ReferenceAnswer']

const base = '/api/v1'

export async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(base + path, { ...init, headers: { ...(typeof init.body === 'string' ? { 'Content-Type': 'application/json' } : {}), ...init.headers } })
  if (!response.ok) {
    const error = await response.json().catch(() => null)
    throw new Error(error?.detail?.message || error?.message || `${response.status} ${response.statusText}`)
  }
  return response.json() as Promise<T>
}

export const json = (value: unknown): RequestInit => ({ method: 'POST', body: JSON.stringify(value) })
export const api = {
  health: () => request<S['Health']>('/health'),
  catalogue: () => request<Catalogue>('/catalogue'),
  challenges: () => request<S['ChallengeList']>('/challenges'),
  challenge: (id: string) => request<Challenge>(`/challenges/${encodeURIComponent(id)}`),
  fixture: (id: string, name: 'initial' | 'reference') => request<Design>(`/challenges/${encodeURIComponent(id)}/fixtures/${name}`),
  reference: (id: string) => request<ReferenceAnswer>(`/challenges/${encodeURIComponent(id)}/reference`),
  validate: (challenge: Challenge, nodes: DesignNode[], edges: DesignEdge[]) => request<Validation>('/designs/validate', json({ challenge_id: challenge.challenge_id, challenge_version: challenge.version, nodes, edges })),
  createDesign: (challenge: Challenge, nodes: DesignNode[], edges: DesignEdge[]) => request<S['DesignCreated']>('/designs', json({ challenge_id: challenge.challenge_id, challenge_version: challenge.version, nodes, edges })),
  createRevision: (designId: string, parentId: string, nodes: DesignNode[], edges: DesignEdge[]) => request<S['DesignCreated']>(`/designs/${encodeURIComponent(designId)}/revisions`, json({ parent_revision_id: parentId, nodes, edges })),
  revision: (designId: string, revisionId: string) => request<Design>(`/designs/${encodeURIComponent(designId)}/revisions/${encodeURIComponent(revisionId)}`),
  design: (designId: string) => request<S['DesignMetadata']>(`/designs/${encodeURIComponent(designId)}`),
  startRun: (body: S['RunInput']) => request<S['RunAccepted']>('/runs', { ...json(body), headers: { 'Idempotency-Key': crypto.randomUUID().replaceAll('-', '') } }),
  run: (id: string) => request<Run>(`/runs/${encodeURIComponent(id)}`),
  results: (id: string) => request<Results>(`/runs/${encodeURIComponent(id)}/results`),
  cancel: (id: string) => request<Run>(`/runs/${encodeURIComponent(id)}/cancel`, { method: 'POST' }),
  snapshots: (runId: string, caseId: string) => request<SnapshotPage>(`/runs/${encodeURIComponent(runId)}/cases/${encodeURIComponent(caseId)}/snapshots`),
  trace: (runId: string, caseId: string, traceId: string) => request<Trace>(`/runs/${encodeURIComponent(runId)}/cases/${encodeURIComponent(caseId)}/traces/${encodeURIComponent(traceId)}`),
  outcomes: (runId: string, caseId: string) => request<S['OutcomePage']>(`/runs/${encodeURIComponent(runId)}/cases/${encodeURIComponent(caseId)}/outcomes`),
  collection: () => request<S['Collection']>('/collection'),
  deleteDesign: (id: string) => request<S['DeleteResult']>(`/designs/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  deleteRun: (id: string) => request<S['DeleteResult']>(`/runs/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  deleteComparison: (id: string) => request<S['DeleteResult']>(`/comparisons/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  saveSnapshot: (id: string, body: S['SaveSnapshotInput']) => request<S['SavedSnapshot']>(`/runs/${encodeURIComponent(id)}/snapshots`, json(body)),
  savedSnapshots: () => request<S['SnapshotList']>('/snapshots'),
  deleteSnapshot: (id: string) => request<S['DeleteResult']>(`/snapshots/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  startReview: (id: string, comparisonId?: string) => request<S['ReviewAccepted']>(`/runs/${encodeURIComponent(id)}/reviews`, json({ consent: true, comparison_id: comparisonId })),
  review: (runId: string, reviewId: string) => request<Review>(`/runs/${encodeURIComponent(runId)}/reviews/${encodeURIComponent(reviewId)}`),
  compare: (body: S['ComparisonInput']) => request<S['ComparisonAccepted']>('/comparisons', json(body)),
  comparison: (id: string) => request<Comparison>(`/comparisons/${encodeURIComponent(id)}`),
  export: (body: S['ExportInput']) => request<S['ExportToken']>('/exports', json(body)),
  import: async (file: File) => {
    const form = new FormData(); form.append('file', file)
    return request<S['ImportResult']>('/imports', { method: 'POST', body: form })
  },
  startGuidance: (designId: string, body: S['GuidanceRequest']) => request<S['GuidanceAccepted']>(`/designs/${encodeURIComponent(designId)}/guidance`, json(body)),
  guidance: (designId: string, guidanceId: string) => request<Guidance>(`/designs/${encodeURIComponent(designId)}/guidance/${encodeURIComponent(guidanceId)}`),
}

export function subscribeRun(id: string, onEvent: (event: Record<string, unknown>) => void): EventSource {
  const source = new EventSource(`${base}/runs/${encodeURIComponent(id)}/events`)
  source.onmessage = message => {
    try { onEvent(JSON.parse(message.data)) } catch { /* reconnect will fetch manifest */ }
  }
  return source
}
