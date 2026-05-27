import { onMounted, onUnmounted } from 'vue'
import { createWs } from '../services/websocket'
import { useEngineStore } from '../stores/engineStore'
import { useAlertStore } from '../stores/alertStore'
import type { WsMessage } from '../types'

export function useWebSockets() {
  const engineStore = useEngineStore()
  const alertStore = useAlertStore()
  const sockets: WebSocket[] = []

  function connect() {
    const onMsg = (msg: WsMessage) => {
      try {
        if (msg.type === 'predictions') engineStore.applyPredictions(msg.predictions)
        if (msg.type === 'telemetry')   engineStore.applyTelemetry(msg.engines)
        if (msg.type === 'alerts')      alertStore.applyAlerts(msg.alerts)
      } catch { /* ignore store errors */ }
    }

    const paths = ['/ws/predictions', '/ws/telemetry', '/ws/alerts']
    paths.forEach(path => {
      try {
        const ws = createWs(path, onMsg)
        ws.onopen  = () => { engineStore.wsConnected = true }
        ws.onclose = () => { engineStore.wsConnected = false }
        ws.onerror = () => { /* swallow — onclose fires next */ }
        sockets.push(ws)
      } catch { /* ignore connection errors */ }
    })
  }

  function disconnect() {
    sockets.forEach(ws => { try { ws.close() } catch { /* ignore */ } })
    sockets.length = 0
  }

  onMounted(connect)
  onUnmounted(disconnect)
}
