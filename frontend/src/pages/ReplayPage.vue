<script setup lang="ts">
import { ref, computed, onUnmounted } from 'vue'
import DashboardLayout from '../layouts/DashboardLayout.vue'
import StatCard from '../components/cards/StatCard.vue'
import type { Prediction } from '../types'

// ── State ─────────────────────────────────────────────────────────────────────
const running   = ref(false)
const speed     = ref(1)
const engineId  = ref('ENG-SIM-1')
const injection = ref<'none' | 'overheat' | 'pressure' | 'vibration'>('none')

const predictions  = ref<Prediction[]>([])
const cycleCount   = ref(0)
const wsConnected  = ref(false)
const wsError      = ref('')

// ── Polling (predict/stream endpoint reads from push buffer) ─────────────────
let pollTimer: ReturnType<typeof setInterval> | null = null

async function pollPrediction() {
  try {
    const base = import.meta.env.VITE_API_URL || ''
    const res = await fetch(`${base}/predict/stream/${encodeURIComponent(engineId.value)}`)
    if (!res.ok) return   // buffer not full yet — silently skip
    const p: Prediction = await res.json()
    wsConnected.value = true
    wsError.value = ''
    predictions.value.unshift(p)
    if (predictions.value.length > 50) predictions.value.pop()
  } catch {
    wsConnected.value = false
  }
}

function startPolling() {
  wsConnected.value = false
  // poll every 2 s regardless of push speed — predictions stabilise quickly
  pollTimer = setInterval(pollPrediction, 2000)
}

function stopPolling() {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
  wsConnected.value = false
}

// ── Sensor simulation ─────────────────────────────────────────────────────────
// Baseline normalized sensor values for 11 sensors (s2..s21)
const BASELINE = [0.52, 0.61, 0.73, 0.45, 0.68, 0.71, 0.55, 0.62, 0.48, 0.59, 0.64]
const SENSORS  = ['s2','s3','s4','s7','s9','s11','s12','s14','s17','s20','s21']

function buildReading(): Record<string, number> {
  const noise = () => (Math.random() - 0.5) * 0.04
  const vals  = BASELINE.map(v => Math.max(0, Math.min(1, v + noise())))

  if (injection.value === 'overheat') {
    // s3 (temp), s4 (temp) spike upward
    vals[1] = Math.min(1, vals[1] + 0.25 + Math.random() * 0.1)
    vals[2] = Math.min(1, vals[2] + 0.20 + Math.random() * 0.1)
  } else if (injection.value === 'pressure') {
    // s9 (pressure), s11 (pressure) drop
    vals[4] = Math.max(0, vals[4] - 0.30 - Math.random() * 0.1)
    vals[5] = Math.max(0, vals[5] - 0.25 - Math.random() * 0.1)
  } else if (injection.value === 'vibration') {
    // s14, s17 spike with high variance
    vals[7] = Math.min(1, vals[7] + 0.35 + Math.random() * 0.15)
    vals[8] = Math.min(1, vals[8] + 0.30 + Math.random() * 0.15)
  }

  return Object.fromEntries(SENSORS.map((s, i) => [s, parseFloat(vals[i].toFixed(4))]))
}

// ── Push loop ─────────────────────────────────────────────────────────────────
let timer: ReturnType<typeof setInterval> | null = null

async function pushReading() {
  try {
    const reading = buildReading()
    await fetch('/push', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ engine_id: engineId.value, reading }),
    })
    cycleCount.value++
  } catch { /* API offline */ }
}

function start() {
  if (running.value) return
  running.value = true
  predictions.value = []
  cycleCount.value  = 0
  startPolling()
  const intervalMs = Math.round(1000 / speed.value)
  timer = setInterval(pushReading, intervalMs)
}

function stop() {
  running.value = false
  if (timer) { clearInterval(timer); timer = null }
  stopPolling()
}

function reset() {
  stop()
  predictions.value = []
  cycleCount.value  = 0
  injection.value   = 'none'
}

onUnmounted(stop)

// ── Derived ───────────────────────────────────────────────────────────────────
const latest      = computed(() => predictions.value[0] ?? null)
const riskColor   = computed(() => ({
  CRITICAL: 'text-red-400', HIGH: 'text-orange-400',
  MEDIUM: 'text-yellow-400', LOW: 'text-green-400',
}[latest.value?.risk_level ?? 'LOW']))

const speedOptions = [
  { label: '×1  (1/s)',   value: 1  },
  { label: '×5  (5/s)',   value: 5  },
  { label: '×10 (10/s)',  value: 10 },
  { label: '×20 (20/s)',  value: 20 },
]

const injectionOptions = [
  { label: 'None',              value: 'none'     },
  { label: '🔥 Overheating',    value: 'overheat' },
  { label: '📉 Pressure Drop',  value: 'pressure' },
  { label: '📳 Vibration Spike',value: 'vibration'},
]
</script>

<template>
  <DashboardLayout>
    <div class="p-6 space-y-6">

      <!-- Header -->
      <div class="flex items-center justify-between">
        <div>
          <h1 class="text-lg font-semibold text-white">Replay &amp; Simulation Lab</h1>
          <p class="text-xs text-gray-500 mt-0.5">Push synthetic telemetry and observe live RUL predictions</p>
        </div>
        <div class="flex items-center gap-2 text-xs">
          <span :class="wsConnected ? 'bg-green-400' : 'bg-gray-600'" class="w-2 h-2 rounded-full"></span>
          <span class="text-gray-500">{{ wsConnected ? 'API live' : running ? 'Waiting…' : 'Idle' }}</span>
        </div>
      </div>

      <!-- Stat cards -->
      <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard label="Cycles Pushed"  :value="cycleCount" />
        <StatCard label="Current RUL"
          :value="latest ? `${latest.remaining_cycles} cy` : '—'"
          :color="riskColor" />
        <StatCard label="Failure Risk"
          :value="latest ? `${(latest.failure_risk * 100).toFixed(1)}%` : '—'"
          :color="riskColor" />
        <StatCard label="Risk Level"
          :value="latest?.risk_level ?? '—'"
          :color="riskColor" />
      </div>

      <!-- Controls + Injection -->
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">

        <!-- Replay controls -->
        <div class="bg-card border border-border rounded-lg p-4 space-y-4">
          <h3 class="text-sm font-semibold text-gray-300">Replay Controls</h3>

          <div class="space-y-3">
            <div>
              <label class="text-xs text-gray-500 block mb-1">Engine ID</label>
              <input v-model="engineId" :disabled="running"
                class="w-full bg-bg border border-border rounded px-3 py-1.5 text-xs text-white font-mono
                       focus:outline-none focus:border-accent disabled:opacity-50" />
            </div>

            <div>
              <label class="text-xs text-gray-500 block mb-1">Speed</label>
              <select v-model="speed" :disabled="running"
                class="w-full bg-bg border border-border rounded px-3 py-1.5 text-xs text-white
                       focus:outline-none focus:border-accent disabled:opacity-50">
                <option v-for="o in speedOptions" :key="o.value" :value="o.value">{{ o.label }}</option>
              </select>
            </div>
          </div>

          <div class="flex gap-2 pt-1">
            <button @click="start" :disabled="running"
              class="flex-1 py-2 rounded text-xs font-semibold bg-accent text-bg
                     hover:opacity-90 disabled:opacity-40 disabled:cursor-not-allowed transition-opacity">
              ▶ Start
            </button>
            <button @click="stop" :disabled="!running"
              class="flex-1 py-2 rounded text-xs font-semibold bg-card border border-border text-white
                     hover:border-accent disabled:opacity-40 disabled:cursor-not-allowed transition-colors">
              ■ Stop
            </button>
            <button @click="reset"
              class="px-4 py-2 rounded text-xs font-semibold bg-card border border-border text-gray-400
                     hover:text-white hover:border-accent transition-colors">
              ↺
            </button>
          </div>
        </div>

        <!-- Failure injection -->
        <div class="bg-card border border-border rounded-lg p-4 space-y-4">
          <h3 class="text-sm font-semibold text-gray-300">Failure Injection</h3>
          <p class="text-xs text-gray-600">Inject anomalies into the sensor stream to observe risk escalation in real time.</p>

          <div class="grid grid-cols-2 gap-2">
            <button v-for="opt in injectionOptions" :key="opt.value"
              @click="injection = opt.value as typeof injection"
              :class="[
                'py-3 px-3 rounded-lg border text-xs font-semibold text-left transition-colors',
                injection === opt.value
                  ? 'border-accent bg-accent/10 text-accent'
                  : 'border-border bg-bg text-gray-400 hover:border-gray-500 hover:text-white'
              ]">
              {{ opt.label }}
            </button>
          </div>

          <div v-if="injection !== 'none'"
            class="text-xs rounded p-2 border"
            :class="{
              'border-red-500/40 bg-red-500/10 text-red-400':    injection === 'overheat',
              'border-blue-500/40 bg-blue-500/10 text-blue-400': injection === 'pressure',
              'border-yellow-500/40 bg-yellow-500/10 text-yellow-400': injection === 'vibration',
            }">
            <span v-if="injection === 'overheat'">⚠ Injecting +25% on temperature sensors s3, s4</span>
            <span v-if="injection === 'pressure'">⚠ Injecting −30% on pressure sensors s9, s11</span>
            <span v-if="injection === 'vibration'">⚠ Injecting +35% high-variance on sensors s14, s17</span>
          </div>
        </div>
      </div>

      <!-- Live prediction feed -->
      <div class="bg-card border border-border rounded-lg p-4">
        <div class="flex items-center justify-between mb-3">
          <h3 class="text-sm font-semibold text-gray-300">Live Prediction Feed</h3>
          <span class="text-xs text-gray-600">{{ predictions.length }} readings (last 50)</span>
        </div>

        <div v-if="!predictions.length" class="text-xs text-gray-600 py-6 text-center">
          {{ running ? 'Waiting for first prediction window (30 cycles)…' : 'Start the replay to see live predictions.' }}
        </div>

        <div v-else class="overflow-auto max-h-72">
          <table class="w-full text-xs">
            <thead>
              <tr class="text-gray-500 border-b border-border">
                <th class="text-left py-2 pr-4">Time</th>
                <th class="text-right pr-4">RUL (cy)</th>
                <th class="text-right pr-4">Risk</th>
                <th class="text-right pr-4">Level</th>
                <th class="text-right">Injection</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(p, i) in predictions" :key="p.timestamp + i"
                class="border-b border-border/40 transition-colors"
                :class="{ 'bg-red-500/5': p.risk_level === 'CRITICAL', 'bg-orange-500/5': p.risk_level === 'HIGH' }">
                <td class="py-1.5 pr-4 text-gray-500 font-mono">
                  {{ new Date(p.timestamp).toLocaleTimeString() }}
                </td>
                <td class="text-right pr-4 font-mono"
                  :class="{
                    'text-red-400':    p.risk_level === 'CRITICAL',
                    'text-orange-400': p.risk_level === 'HIGH',
                    'text-yellow-400': p.risk_level === 'MEDIUM',
                    'text-green-400':  p.risk_level === 'LOW',
                  }">
                  {{ p.remaining_cycles }}
                </td>
                <td class="text-right pr-4 font-mono text-gray-300">
                  {{ (p.failure_risk * 100).toFixed(1) }}%
                </td>
                <td class="text-right pr-4">
                  <span class="px-1.5 py-0.5 rounded text-xs font-semibold"
                    :class="{
                      'bg-red-500/20 text-red-400':    p.risk_level === 'CRITICAL',
                      'bg-orange-500/20 text-orange-400': p.risk_level === 'HIGH',
                      'bg-yellow-500/20 text-yellow-400': p.risk_level === 'MEDIUM',
                      'bg-green-500/20 text-green-400':   p.risk_level === 'LOW',
                    }">
                    {{ p.risk_level }}
                  </span>
                </td>
                <td class="text-right text-gray-600">
                  {{ i === 0 && injection !== 'none' ? injection : '—' }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- How it works -->
      <div class="bg-card border border-border rounded-lg p-4">
        <h3 class="text-sm font-semibold text-gray-300 mb-3">How It Works</h3>
        <div class="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs text-gray-500">
          <div class="bg-bg rounded p-3">
            <p class="text-white font-semibold mb-1">1. Push readings</p>
            <p>Each tick sends a synthetic sensor reading to <span class="font-mono text-accent">POST /push</span>, filling the engine's rolling buffer.</p>
          </div>
          <div class="bg-bg rounded p-3">
            <p class="text-white font-semibold mb-1">2. Buffer fills</p>
            <p>After 30 cycles the buffer is full. The page polls <span class="font-mono text-accent">GET /predict/stream/{id}</span> every 2 s and starts showing live RUL predictions.</p>
          </div>
          <div class="bg-bg rounded p-3">
            <p class="text-white font-semibold mb-1">3. Inject failures</p>
            <p>Failure injection shifts sensor values outside the training distribution, causing the GRU to predict higher risk and lower RUL.</p>
          </div>
        </div>
      </div>

    </div>
  </DashboardLayout>
</template>
