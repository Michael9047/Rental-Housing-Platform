// 户型提交载荷的必填字段与库存约束。
export function validateUnitTypePayload(input: {
  property_type?: string
  total_count: number
  available_count: number
}): string | null {
  if (!input.property_type) return '请选择户型类型'
  if (input.available_count < 0 || input.total_count < 0 || input.available_count > input.total_count) {
    return '可租套数必须在 0 到总套数之间'
  }
  return null
}
