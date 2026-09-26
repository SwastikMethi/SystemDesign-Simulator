import type { Catalogue, Challenge, DesignEdge, DesignNode } from '../api/client'

export type Graph = { nodes: DesignNode[]; edges: DesignEdge[] }
export const emptyGraph = (): Graph => ({ nodes: [], edges: [] })
export const graphFrom = (graph: Graph): Graph => ({ nodes: graph.nodes.map(n => ({ ...n, position: { ...n.position }, settings: { ...n.settings } } as DesignNode)), edges: graph.edges.map(e => ({ ...e, operation_ids: [...e.operation_ids] })) })

export function addNode(graph: Graph, type: DesignNode['type'], catalogue: Catalogue, position = { x: 120 + graph.nodes.length * 32, y: 120 + graph.nodes.length * 48 }): Graph {
  if (graph.nodes.length >= 25) throw new Error('A design can contain at most 25 components.')
  if (type === 'client' && graph.nodes.some(n => n.type === 'client')) throw new Error('The design already has a client.')
  const component = catalogue.component_types.find(c => c.type === type)
  if (!component) throw new Error('Component unavailable.')
  const node = { id: crypto.randomUUID(), type, label: component.label, profile_id: component.profiles[0], instance_count: 1, settings: {}, position } as DesignNode
  return { ...graph, nodes: [...graph.nodes, node] }
}

export function duplicateNode(graph: Graph, id: string): Graph {
  const node = graph.nodes.find(n => n.id === id)
  if (!node) return graph
  if (node.type === 'client') throw new Error('The design can have one client.')
  if (graph.nodes.length >= 25) throw new Error('A design can contain at most 25 components.')
  return { ...graph, nodes: [...graph.nodes, { ...node, id: crypto.randomUUID(), label: `${node.label} copy`, position: { x: node.position.x + 32, y: node.position.y + 64 } }] }
}

export function removeNode(graph: Graph, id: string): Graph {
  return { nodes: graph.nodes.filter(n => n.id !== id), edges: graph.edges.filter(e => e.source !== id && e.target !== id) }
}

export function addEdge(graph: Graph, source: string, target: string, kind: DesignEdge['kind'], operationIds: string[], challenge: Challenge): Graph {
  if (graph.edges.length >= 60) throw new Error('A design can contain at most 60 connections.')
  if (source === target) throw new Error('Connect two different components.')
  if (!graph.nodes.some(n => n.id === source) || !graph.nodes.some(n => n.id === target)) throw new Error('Choose existing components.')
  if (!operationIds.length || operationIds.some(id => !challenge.operations.some(o => o.id === id))) throw new Error('Choose at least one valid operation.')
  if (graph.edges.some(e => e.source === source && e.target === target && e.kind === kind && operationIds.some(id => e.operation_ids.includes(id)))) throw new Error('That operation already has this connection.')
  return { ...graph, edges: [...graph.edges, { id: crypto.randomUUID(), source, target, kind, operation_ids: operationIds }] }
}

export function updateNode(graph: Graph, id: string, change: Partial<DesignNode> | { settings: Record<string, unknown> }): Graph {
  return { ...graph, nodes: graph.nodes.map(n => n.id === id ? { ...n, ...change } as DesignNode : n) }
}
export function updateEdge(graph: Graph, id: string, change: Partial<DesignEdge>): Graph {
  return { ...graph, edges: graph.edges.map(e => e.id === id ? { ...e, ...change } : e) }
}
