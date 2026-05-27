import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { Prediction, EngineMeta, EngineStatus, HealthStatus, ModelInfo } from '../types'
import { getHealth, getModelInfo, getEngines } from '../services/api'

export const useEngineStore = defineStore('engine', () => {
  const predictions = ref<Map<string, Prediction>>(new Map())
  const telemetry = ref<Map<string, EngineMeta>>(new Map())
  const engines = ref<EngineStatus[]>([])
  const health = ref<HealthStatus | null>(null)
  const modelInfo = ref<ModelInfo | null>(null)
  const lastUpdated = ref<string>('')
  const wsConnected = ref(false)

  const sortedPredictions = computed(() =>
    [...predictions.value.values()].sort((a, b) => b.failure_risk - a.failure_risk)
  )

  const criticalCount = computed(() =>
    [...predictions.value.values()].filter(p => p.risk_level === 'CRITICAL').length
  )

  const highCount = computed(() =>
    [...predictions.value.values()].filter(p => p.risk_level === 'HIGH').length
  )

  const avgRul = computed(() => {
    const vals = [...predictions.value.values()]
    if (!vals.length) return 0
    return Math.round(vals.reduce((s, p) => s + p.remaining_cycles, 0) / vals.length)
  })

  function applyPredictions(preds: Prediction[]) {
    preds.forEach(p => predictions.value.set(p.engine_id, p))
    lastUpdated.value = new Date().toLocaleTimeString()
  }

  function applyTelemetry(metas: EngineMeta[]) {
    metas.forEach(m => telemetry.value.set(m.engine_id, m))
  }

  async function fetchHealth() {
    try { health.value = (await getHealth()).data } catch { /* offline */ }
  }

  async function fetchModelInfo() {
    try { modelInfo.value = (await getModelInfo()).data } catch { /* offline */ }
  }

  async function fetchEngines() {
    try { engines.value = (await getEngines()).data.engines } catch { /* offline */ }
  }

  return {
    predictions, telemetry, engines, health, modelInfo,
    lastUpdated, wsConnected,
    sortedPredictions, criticalCount, highCount, avgRul,
    applyPredictions, applyTelemetry, fetchHealth, fetchModelInfo, fetchEngines,
  }
})
