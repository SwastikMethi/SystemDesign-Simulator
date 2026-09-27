import type { Run } from '../api/client'
import type { Graph } from '../editor/graph'

export type LessonProgress = { requirementsRead: boolean; flowRunId?: string; evidenceRunId?: string }
export type LessonStep = 'client' | 'app' | 'database' | 'client-route' | 'database-route' | 'requirements' | 'preview' | 'flow' | 'evidence' | 'upgrade' | 'assessment' | 'complete'

export function lessonStep({ graph, progress, run, revisionId, dirty }: { graph: Graph; progress: LessonProgress; run: Run | null; revisionId?: string; dirty: boolean }): LessonStep {
  const client = graph.nodes.find(node => node.type === 'client')
  const app = graph.nodes.find(node => node.type === 'app_service')
  const database = graph.nodes.find(node => node.type === 'sql_database')
  if (!client) return 'client'
  if (!app) return 'app'
  if (!database) return 'database'
  const connects = (source: string, target: string) => graph.edges.some(edge => edge.source === source && edge.target === target && edge.kind === 'request' && edge.operation_ids.includes('read_note'))
  if (!connects(client.id, app.id)) return 'client-route'
  if (!connects(app.id, database.id)) return 'database-route'
  const current = run?.execution_status === 'completed' && !dirty && run.revision_id === revisionId
  if (current && run.mode === 'assessment' && run.assessment_status === 'pass') return 'complete'
  if (!progress.requirementsRead) return 'requirements'
  if (database.profile_id === 'sql.medium.v1' && (!current || run.mode !== 'assessment')) return 'assessment'
  if (!current) return 'preview'
  if (progress.flowRunId !== run.run_id) return 'flow'
  if (progress.evidenceRunId !== run.run_id) return 'evidence'
  return database.profile_id === 'sql.medium.v1' ? 'assessment' : 'upgrade'
}
