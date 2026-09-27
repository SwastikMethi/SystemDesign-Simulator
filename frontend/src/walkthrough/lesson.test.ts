import { expect, it } from 'vitest'
import type { Run } from '../api/client'
import type { Graph } from '../editor/graph'
import initial from '../../../content/fixtures/first-design/initial.json'
import { lessonStep, type LessonProgress } from './lesson'

const graph = initial as Graph
const progress: LessonProgress = { requirementsRead: true, flowRunId: 'run-1', evidenceRunId: 'run-1' }
const run = { run_id: 'run-1', revision_id: 'revision-1', mode: 'preview', execution_status: 'completed', assessment_status: 'incomplete' } as Run
const facts = { graph, progress, run, revisionId: 'revision-1', dirty: false }

it('requires real nodes and the correct operation routes, including after undo', () => {
  expect(lessonStep({ ...facts, graph: { nodes: [], edges: [] } })).toBe('client')
  expect(lessonStep({ ...facts, graph: { nodes: graph.nodes.slice(0, 1), edges: [] } })).toBe('app')
  expect(lessonStep({ ...facts, graph: { ...graph, edges: [] } })).toBe('client-route')
  expect(lessonStep({ ...facts, graph: { ...graph, edges: [{ ...graph.edges[0], operation_ids: [] }] } })).toBe('client-route')
  expect(lessonStep({ ...facts, graph: { ...graph, edges: graph.edges.slice(0, 1) } })).toBe('database-route')
})

it('keeps failed, canceled, stale and dirty runs from advancing the lesson', () => {
  for (const execution_status of ['failed', 'canceled', 'running'] as const) {
    expect(lessonStep({ ...facts, run: { ...run, execution_status } })).toBe('preview')
  }
  expect(lessonStep({ ...facts, revisionId: 'other-revision' })).toBe('preview')
  expect(lessonStep({ ...facts, dirty: true })).toBe('preview')
  expect(lessonStep({ ...facts, progress: { requirementsRead: true } })).toBe('flow')
  expect(lessonStep({ ...facts, progress: { requirementsRead: true, flowRunId: 'run-1' } })).toBe('evidence')
  expect(lessonStep(facts)).toBe('upgrade')
})

it('requires an assessment of the upgraded revision before completion', () => {
  const upgraded = { ...graph, nodes: graph.nodes.map(node => node.type === 'sql_database' ? { ...node, profile_id: 'sql.medium.v1' } : node) }
  expect(lessonStep({ ...facts, graph: upgraded, dirty: true })).toBe('assessment')
  const passed = { ...run, mode: 'assessment', assessment_status: 'pass' } as Run
  expect(lessonStep({ ...facts, graph: upgraded, run: passed })).toBe('complete')
  expect(lessonStep({ ...facts, graph: upgraded, run: passed, dirty: true })).toBe('assessment')
  expect(lessonStep({ ...facts, graph: upgraded, run: { ...passed, mode: 'preview' } })).not.toBe('complete')
})
