import type { Outcome } from '../api/client'

export const outcomeKey = (outcome: Pick<Outcome, 'requirement_id' | 'operation_id'>) => `${outcome.requirement_id}/${outcome.operation_id || ''}`
