/** 根据 filename 生成正确的图片 URL。
 *  - 如果 filename 已经是完整 URL（如 Unsplash），直接返回
 *  - 否则拼上 /api/v1/uploads/ 前缀作为本地静态文件路径
 */
export function getImageUrl(filename: string | undefined | null): string {
  if (!filename) return ''
  return filename.startsWith('http') ? filename : `/api/v1/uploads/${filename}`
}
