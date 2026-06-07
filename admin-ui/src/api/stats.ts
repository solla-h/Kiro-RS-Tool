import axios from 'axios'
import { storage } from '@/lib/storage'
import type {
  CredentialDistribution,
  ModelDistribution,
  OverviewStats,
  StatsRange,
  TimeSeriesPoint,
} from '@/types/api'

const api = axios.create({
  baseURL: '/api/admin',
  timeout: 15000,
  headers: { 'Content-Type': 'application/json' },
})

api.interceptors.request.use((config) => {
  const apiKey = storage.getApiKey()
  if (apiKey) config.headers['x-api-key'] = apiKey
  return config
})

export async function getOverview(): Promise<OverviewStats> {
  const { data } = await api.get<OverviewStats>('/stats/overview')
  return data
}

export async function getTimeSeries(range: StatsRange): Promise<TimeSeriesPoint[]> {
  const { data } = await api.get<TimeSeriesPoint[]>('/stats/timeseries', { params: { range } })
  return data
}

export async function getByModel(range: StatsRange): Promise<ModelDistribution[]> {
  const { data } = await api.get<ModelDistribution[]>('/stats/by-model', { params: { range } })
  return data
}

export async function getByCredential(range: StatsRange): Promise<CredentialDistribution[]> {
  const { data } = await api.get<CredentialDistribution[]>('/stats/by-credential', { params: { range } })
  return data
}
