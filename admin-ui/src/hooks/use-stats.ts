import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { getByCredential, getByModel, getOverview, getTimeSeries } from '@/api/stats'
import type { StatsRange } from '@/types/api'

/**
 * 统计接口共用配置
 *
 * - `staleTime: 25_000`：30s 自动刷新前不再触发后台 refetch（防止跨 Tab 切换抖动）
 * - `placeholderData: keepPreviousData`：切换 range 或 tab 期间保留上次数据，
 *   chart 组件输入引用稳定 → 不会卸载重挂
 * - `refetchOnWindowFocus: false`：Admin 面板长时间挂着时减少瞬时压力
 */
const COMMON = {
  refetchInterval: 30_000,
  staleTime: 25_000,
  placeholderData: keepPreviousData,
  refetchOnWindowFocus: false,
} as const

export function useOverview() {
  return useQuery({
    queryKey: ['stats', 'overview'],
    queryFn: getOverview,
    ...COMMON,
  })
}

export function useTimeSeries(range: StatsRange) {
  return useQuery({
    queryKey: ['stats', 'timeseries', range],
    queryFn: () => getTimeSeries(range),
    ...COMMON,
  })
}

export function useByModel(range: StatsRange) {
  return useQuery({
    queryKey: ['stats', 'by-model', range],
    queryFn: () => getByModel(range),
    ...COMMON,
  })
}

export function useByCredential(range: StatsRange) {
  return useQuery({
    queryKey: ['stats', 'by-credential', range],
    queryFn: () => getByCredential(range),
    ...COMMON,
  })
}
