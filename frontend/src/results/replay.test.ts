import { expect, it } from 'vitest'
import { createTimeline, playheadAt, recordedAt } from './replay'

it('slows short hops without changing recorded timestamps or adding case idle time', () => {
  const timeline = createTimeline([10_000_000, 10_000_000, 10_002_000, 10_003_000], true)
  expect(timeline).toEqual([
    { timeUs: 10_000_000, playMs: 0 },
    { timeUs: 10_002_000, playMs: 750 },
    { timeUs: 10_003_000, playMs: 1500 },
  ])
  expect(recordedAt(timeline, 375)).toBe(10_001_000)
  expect(playheadAt(timeline, 10_002_500)).toBe(1125)
  expect(recordedAt(timeline, 1600)).toBe(10_003_000)
})

it('keeps real-time and long waits accurate and handles empty or single-event recordings', () => {
  expect(createTimeline([0, 2000, 2_002_000], false).at(-1)?.playMs).toBe(2002)
  expect(createTimeline([0, 2000, 2_002_000], true).at(-1)?.playMs).toBe(2750)
  expect(recordedAt([], 100)).toBe(0)
  expect(recordedAt(createTimeline([50], true), 100)).toBe(50)
  expect(playheadAt(createTimeline([50], true), 30)).toBe(0)
})
