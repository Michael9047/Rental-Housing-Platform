// Node 22 暴露了一个未配置文件时不可用的实验性 localStorage。
// 使用隔离的内存实现，避免它遮蔽 jsdom 的同名 API。
const values = new Map<string, string>()
const testStorage: Storage = {
  get length() { return values.size },
  clear() { values.clear() },
  getItem(key) { return values.get(String(key)) ?? null },
  key(index) { return [...values.keys()][index] ?? null },
  removeItem(key) { values.delete(String(key)) },
  setItem(key, value) { values.set(String(key), String(value)) },
}

Object.defineProperty(globalThis, 'localStorage', {
  configurable: true,
  value: testStorage,
})
Object.defineProperty(window, 'localStorage', {
  configurable: true,
  value: testStorage,
})
