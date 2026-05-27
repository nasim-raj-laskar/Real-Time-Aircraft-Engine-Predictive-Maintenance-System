import type { WsMessage } from '../types'

const BASE = (import.meta.env.VITE_WS_URL || 'ws://localhost:8000')

export function createWs(
  path: string,
  onMessage: (msg: WsMessage) => void,
  onError?: () => void,
): WebSocket {
  const ws = new WebSocket(`${BASE}${path}`)
  ws.onmessage = (e) => {
    try { onMessage(JSON.parse(e.data)) } catch { /* ignore malformed */ }
  }
  ws.onerror = () => onError?.()
  return ws
}
