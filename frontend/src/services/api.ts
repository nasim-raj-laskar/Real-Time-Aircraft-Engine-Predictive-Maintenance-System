import axios from 'axios'
import type { EngineStatus, HealthStatus, ModelInfo, Prediction } from '../types'

// Empty string = relative URLs (nginx proxy in Docker). Fallback for local dev.
const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '',
  timeout: 10_000,
})

export const getHealth = () => api.get<HealthStatus>('/health')
export const getModelInfo = () => api.get<ModelInfo>('/model/info')
export const getModelEvaluation = () => api.get<{
  rmse: number
  nasa_score: number
  precision_critical: number
  recall_critical: number
  f1_critical: number
  accuracy: number
  f1_weighted: number
}>('/model/evaluation')
export const getEngines = () => api.get<{ engines: EngineStatus[]; total: number }>('/engines')
export const getEngine = (id: string) => api.get<EngineStatus>(`/engines/${id}`)
export const getAlerts = (minRisk = 'HIGH') =>
  api.get<{ alerts: Prediction[]; total: number }>('/alerts', { params: { min_risk_level: minRisk } })
export const predictEngine = (engineId: string) =>
  api.get<Prediction>(`/predict/engine/${engineId}`)
export const getDriftReports = () =>
  api.get<{ reports: { filename: string; size_kb: number }[] }>('/drift/reports')
export const triggerPipeline = () => api.post<{ status: string; message: string }>('/pipeline/run')
export const getPipelineStatus = () => api.get<{
  status: 'idle' | 'running' | 'success' | 'failed'
  started_at: string | null
  log_file: string | null
  exit_code: number | null
}>('/pipeline/status')
