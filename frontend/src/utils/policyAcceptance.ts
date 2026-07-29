/** 政策同意状态检查工具。 */

/** 检查所有必选政策是否均已同意。 */
export function areAllPoliciesAccepted(
  policyKeys: string[],
  accepted: Record<string, boolean>,
): boolean {
  return policyKeys.every((key) => accepted[key] === true)
}
