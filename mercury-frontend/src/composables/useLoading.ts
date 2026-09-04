import { ref } from 'vue'

/**
 * Wraps an async function to prevent concurrent executions (double-click protection).
 * Returns [wrappedFn, loadingRef].
 */
export function useLoading<T extends (...args: any[]) => Promise<any>>(fn: T) {
  const loading = ref(false)
  const wrapped = async (...args: Parameters<T>) => {
    if (loading.value) return
    loading.value = true
    try {
      return await fn(...args)
    } finally {
      loading.value = false
    }
  }
  return [wrapped as (...args: Parameters<T>) => Promise<ReturnType<T>>, loading] as const
}
