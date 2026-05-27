import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { Prediction } from '../types'

export interface Alert {
  id: string
  engine_id: string
  risk_level: string
  failure_risk: number
  remaining_cycles: number
  timestamp: string
  acknowledged: boolean
}

export const useAlertStore = defineStore('alert', () => {
  const alerts = ref<Alert[]>([])

  function applyAlerts(preds: Prediction[]) {
    preds.forEach(p => {
      const exists = alerts.value.find(a => a.engine_id === p.engine_id && !a.acknowledged)
      if (!exists) {
        alerts.value.unshift({
          id: `${p.engine_id}-${p.timestamp}`,
          engine_id: p.engine_id,
          risk_level: p.risk_level,
          failure_risk: p.failure_risk,
          remaining_cycles: p.remaining_cycles,
          timestamp: p.timestamp,
          acknowledged: false,
        })
      }
    })
    // keep last 50
    if (alerts.value.length > 50) alerts.value = alerts.value.slice(0, 50)
  }

  function acknowledge(id: string) {
    const a = alerts.value.find(a => a.id === id)
    if (a) a.acknowledged = true
  }

  const unacknowledged = () => alerts.value.filter(a => !a.acknowledged)

  return { alerts, applyAlerts, acknowledge, unacknowledged }
})
