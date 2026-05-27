import axios from 'axios'
import type { EngineStatus, HealthStatus, ModelInfo, Prediction } from '../types'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
  timeout: 10_000,
})

export const getHealth = () => api.get<HealthStatus>('/health')
export const getModelInfo = () => api.get<ModelInfo>('/model/info')
export const getEngines = () => api.get<{ engines: EngineStatus[]; total: number }>('/engines')
export const getEngine = (id: string) => api.get<EngineStatus>(`/engines/${id}`)
export const getAlerts = (minRisk = 'HIGH') =>
  api.get<{ alerts: Prediction[]; total: number }>('/alerts', { params: { min_risk_level: minRisk } })
export const predictEngine = (engineId: string) =>
  api.get<Prediction>(`/predict/engine/${engineId}`)
