// 普通搜索导航工具：保留用户实际看到的搜索文字，并为每次提交生成独立事件。
let searchSequence = 0

export function normalSearchQuery(
  params: Record<string, string>,
  searchText: string,
): Record<string, string> {
  searchSequence += 1
  return {
    ...params,
    q: searchText,
    search_id: `${Date.now()}-${searchSequence}`,
  }
}
