import { describe, expect, it } from 'vitest'
import type { AgentRecommendation } from '@/types/agent'
import {
  AGENT_RECOMMENDATION_DISPLAY_LIMIT,
  normalizeRecommendationLabel,
  uniqueAgentRecommendations,
  visibleAgentRecommendations,
} from '@/utils/agentRecommendations'

function recommendation(
  propertyId: number | string,
  instituteId: number,
  unitTypeName: string,
): AgentRecommendation {
  return {
    property_id: propertyId as number,
    match_reason: '符合条件',
    pros: [],
    cons: [],
    property: {
      id: Number(propertyId),
      institute_id: instituteId,
      institute_name: `Institute ${instituteId}`,
      name: unitTypeName,
      title: unitTypeName,
    } as AgentRecommendation['property'],
  }
}

describe('uniqueAgentRecommendations', () => {
  it('treats property_id as the global UnitType identity and keeps its first card', () => {
    const first = recommendation(101, 10, 'Studio')
    const duplicateUnitTypeId = recommendation('101', 20, 'Ensuite')

    expect(uniqueAgentRecommendations([first, duplicateUnitTypeId])).toEqual([first])
  })

  it('deduplicates normalized unit-type names only inside the same Institute', () => {
    const first = recommendation(201, 10, 'Studio')
    const sameInstituteAndName = recommendation(202, 10, '  STU-DIO  ')
    const sameNameAtAnotherInstitute = recommendation(203, 11, 'studio')

    expect(uniqueAgentRecommendations([
      first,
      sameInstituteAndName,
      sameNameAtAnotherInstitute,
    ]).map((item) => item.property_id)).toEqual([201, 203])
  })

  it('uses Institute name as the boundary when an Institute id is absent', () => {
    const first = recommendation(301, 10, '1 Bed')
    const sameInstitute = recommendation(302, 10, '1-bed')
    const anotherInstitute = recommendation(303, 11, '1 bed')
    delete (first.property as { institute_id?: number }).institute_id
    delete (sameInstitute.property as { institute_id?: number }).institute_id
    delete (anotherInstitute.property as { institute_id?: number }).institute_id
    ;(first.property as { institute_name?: string }).institute_name = 'Maple House'
    ;(sameInstitute.property as { institute_name?: string }).institute_name = ' maple-house '
    ;(anotherInstitute.property as { institute_name?: string }).institute_name = 'Oak House'

    expect(uniqueAgentRecommendations([
      first,
      sameInstitute,
      anotherInstitute,
    ]).map((item) => item.property_id)).toEqual([301, 303])
  })

  it('rejects missing properties and invalid UnitType ids instead of treating them as Building ids', () => {
    const valid = recommendation(401, 10, 'Studio')
    const invalid = [
      { ...recommendation(0, 10, 'Zero'), property_id: 0 },
      { ...recommendation(-1, 10, 'Negative'), property_id: -1 },
      { ...recommendation(1.5, 10, 'Fraction'), property_id: 1.5 },
      { ...recommendation(402, 10, 'Missing'), property: null },
    ] as unknown as AgentRecommendation[]

    expect(uniqueAgentRecommendations([...invalid, valid])).toEqual([valid])
  })

  it('normalizes Unicode width, casing, whitespace and common separators consistently', () => {
    expect(normalizeRecommendationLabel('  ＳＴＵＤＩＯ · A_B—C  ')).toBe('studioabc')
  })

  it('renders at most twenty cards while leaving total counting to metadata', () => {
    const recommendations = Array.from({ length: 111 }, (_, index) => (
      recommendation(index + 1, index + 1, `Unit ${index + 1}`)
    ))

    expect(visibleAgentRecommendations(recommendations)).toHaveLength(
      AGENT_RECOMMENDATION_DISPLAY_LIMIT,
    )
    expect(recommendations).toHaveLength(111)
  })
})
