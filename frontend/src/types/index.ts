export type RiskLevel = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'

export interface Prediction {
  engine_id: string
  remaining_cycles: number
  failure_risk: number
  risk_level: RiskLevel
  confidence: number
  timestamp: string
  model_version: string
}

export interface EngineStatus {
  engine_id: string
  source: 'redis_stream' | 'push_buffer'
  ready: boolean
  last_prediction: Prediction | null
}

export interface EngineMeta {
  engine_id: string
  cycle: number
  event_time_ms: number
  window_size: number
}

export interface ModelInfo {
  model_type: string
  input_shape: number[]
  window_size: number
  sensors: string[]
  rul_clip: number
  model_version: string
  trained_on: string
}

export interface HealthStatus {
  status: 'healthy' | 'unhealthy'
  model_loaded: boolean
  model_version: string
  uptime_seconds: number
}

// WebSocket message types
export interface WsTelemetryMsg {
  type: 'telemetry'
  timestamp: string
  engines: EngineMeta[]
  total: number
}

export interface WsPredictionsMsg {
  type: 'predictions'
  timestamp: string
  predictions: Prediction[]
  total: number
}

export interface WsAlertsMsg {
  type: 'alerts'
  timestamp: string
  alerts: Prediction[]
  total: number
  min_risk_level: RiskLevel
}

export interface WsErrorMsg {
  type: 'error'
  detail: string
}

export type WsMessage = WsTelemetryMsg | WsPredictionsMsg | WsAlertsMsg | WsErrorMsg
