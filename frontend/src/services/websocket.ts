import type { WsMessage } from '../types'

// Empty string → derive ws:// from current page origin (nginx proxy in Docker)
const BASE = import.meta.env.VITE_WS_URL ||
  `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}`

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
