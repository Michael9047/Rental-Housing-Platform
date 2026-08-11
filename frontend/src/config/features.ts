/** 前端功能开关：仅控制用户可见入口，不替代后端权限校验。 */
export const contractTemplateManagementEnabled =
  import.meta.env.VITE_CONTRACT_TEMPLATE_MANAGEMENT_ENABLED === 'true'
