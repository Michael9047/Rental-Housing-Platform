/** 根据 filename 生成正确的图片 URL。
 *  - 如果 filename 已经是完整 URL（如 Unsplash），直接返回
 *  - 否则拼上 /api/v1/uploads/ 前缀作为本地静态文件路径
 */
export function getImageUrl(filename: string | undefined | null): string {
  if (!filename) return ''
  if (
    /^(https?:)?\/\//i.test(filename)
    || filename.startsWith('data:')
    || filename.startsWith('blob:')
    || filename.startsWith('/')
  ) {
    return filename
  }
  return `/api/v1/uploads/${filename}`
}
