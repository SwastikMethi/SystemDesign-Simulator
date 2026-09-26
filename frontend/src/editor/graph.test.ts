import { describe, expect, it, vi } from 'vitest'
import type { Catalogue, Challenge } from '../api/client'
import { addEdge, addNode, duplicateNode, removeNode, updateNode, type Graph } from './graph'

vi.stubGlobal('crypto', { randomUUID: (() => { let id = 0; return () => `id-${++id}` })() })

const catalogue = { component_types: [
  { type: 'client', label: 'Client', purpose: 'Source', profiles: ['client.v1'], settings: {}, support_label: 'Simulated' },
  { type: 'app_service', label: 'App service', purpose: 'Handle', profiles: ['app.small.v1'], settings: {}, support_label: 'Simulated' },
], profiles: [] } as Catalogue
const challenge = { operations: [{ id: 'read', kind: 'read_key' }] } as Challenge

describe('editable architecture', () => {
  it('keeps connections valid when duplicating and removing components', () => {
    let graph: Graph = { nodes: [], edges: [] }
    graph = addNode(graph, 'client', catalogue)
    graph = addNode(graph, 'app_service', catalogue)
    const [client, app] = graph.nodes
    graph = addEdge(graph, client.id, app.id, 'request', ['read'], challenge)
    expect(() => addEdge(graph, client.id, app.id, 'request', ['read'], challenge)).toThrow(/already/)
    graph = duplicateNode(graph, app.id)
    expect(graph.nodes).toHaveLength(3)
    expect(graph.edges).toHaveLength(1)
    graph = removeNode(graph, app.id)
    expect(graph.edges).toHaveLength(0)
    expect(graph.nodes).toHaveLength(2)
  })

  it('rejects a second client and updates without mutating the saved graph', () => {
    const original = addNode({ nodes: [], edges: [] }, 'client', catalogue)
    expect(() => addNode(original, 'client', catalogue)).toThrow(/already/)
    const changed = updateNode(original, original.nodes[0].id, { label: 'Learner client' })
    expect(original.nodes[0].label).toBe('Client')
    expect(changed.nodes[0].label).toBe('Learner client')
  })
})
