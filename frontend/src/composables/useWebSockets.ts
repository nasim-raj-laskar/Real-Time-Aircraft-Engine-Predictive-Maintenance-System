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
      if (msg.type === 'predictions') engineStore.applyPredictions(msg.predictions)
      if (msg.type === 'telemetry')   engineStore.applyTelemetry(msg.engines)
      if (msg.type === 'alerts')      alertStore.applyAlerts(msg.alerts)
    }
    const onErr = () => { engineStore.wsConnected = false }

    sockets.push(
      createWs('/ws/predictions', onMsg, onErr),
      createWs('/ws/telemetry',   onMsg, onErr),
      createWs('/ws/alerts',      onMsg, onErr),
    )

    sockets.forEach(ws => {
      ws.onopen = () => { engineStore.wsConnected = true }
    })
  }

  function disconnect() {
    sockets.forEach(ws => ws.close())
    sockets.length = 0
  }

  onMounted(connect)
  onUnmounted(disconnect)

  return { connect, disconnect }
}
