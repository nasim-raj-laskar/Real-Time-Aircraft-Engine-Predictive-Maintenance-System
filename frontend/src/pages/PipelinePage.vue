<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import DashboardLayout from '../layouts/DashboardLayout.vue'
import { useEngineStore } from '../stores/engineStore'
import { getHealth } from '../services/api'

const store = useEngineStore()

// ── Service health checks ─────────────────────────────────────────────────────
interface ServiceStatus {
  name: string
  port: number
  url: string
  color: string
  status: 'up' | 'down' | 'checking'
}

const services = ref<ServiceStatus[]>([
  { name: 'FastAPI Inference',   port: 8000, url: 'http://localhost:8000/health',         color: 'text-cyan-400',   status: 'checking' },
  { name: 'Redis Feature Store', port: 6379, url: '',                                     color: 'text-green-400',  status: 'checking' },
  { name: 'Solace PubSub+',      port: 8080, url: 'http://localhost:8080/SEMP/v2/config', color: 'text-yellow-400', status: 'checking' },
  { name: 'Flink JobManager',    port: 8082, url: 'http://localhost:8082/overview',       color: 'text-orange-400', status: 'checking' },
  { name: 'Prometheus',          port: 9090, url: 'http://localhost:9090/-/healthy',      color: 'text-purple-400', status: 'checking' },
  { name: 'Grafana',             port: 3000, url: 'http://localhost:3000/api/health',     color: 'text-pink-400',   status: 'checking' },
])

async function checkServices() {
  // FastAPI — use our own API so it works through nginx proxy too
  try {
    await getHealth()
    services.value[0].status = 'up'
  } catch {
    services.value[0].status = 'down'
  }
  // Redis — infer from WS connection (if WS is live, Redis is up)
  services.value[1].status = store.wsConnected ? 'up' : 'down'
  // External services — best-effort fetch with no-cors
  for (const svc of services.value.slice(2)) {
    if (!svc.url) continue
    try {
      await fetch(svc.url, { mode: 'no-cors', signal: AbortSignal.timeout(2000) })
      svc.status = 'up'
    } catch {
      svc.status = 'down'
    }
  }
}

onMounted(() => {
  checkServices()
  setInterval(checkServices, 30_000)
})

// ── Live counters from WS streams ─────────────────────────────────────────────
const activeEngines  = computed(() => store.predictions.size)
const telemetryCount = computed(() => store.telemetry.size)
const criticalCount  = computed(() => store.criticalCount)
const avgCycle = computed(() => {
  const metas = [...store.telemetry.values()]
  if (!metas.length) return 0
  return Math.round(metas.reduce((s, m) => s + m.cycle, 0) / metas.length)
})

// ── Pipeline topology ─────────────────────────────────────────────────────────
const pipeline = [
  { label: 'Telemetry Producer', desc: 'Streams FD001 rows → Redis Stream / Solace', icon: '📡', color: 'border-cyan-500/40' },
  { label: 'Normalization',      desc: 'MinMax scaler per event (stateless)',         icon: '⚖️', color: 'border-blue-500/40' },
  { label: 'Rolling Window',     desc: '30-cycle per-engine keyed buffer',            icon: '🔄', color: 'border-indigo-500/40' },
  { label: 'Redis Sink',         desc: 'Feature tensors → engine:{id}:features',     icon: '💾', color: 'border-green-500/40' },
  { label: 'S3 Parquet Sink',    desc: 'Offline archive, flush every 500 vectors',   icon: '☁️', color: 'border-yellow-500/40' },
  { label: 'FastAPI Inference',  desc: 'Reads Redis → GRU → RUL prediction',         icon: '🧠', color: 'border-purple-500/40' },
]
</script>

<template>
  <DashboardLayout>
    <div class="p-6 space-y-6">
      <div class="flex items-center justify-between">
        <div>
          <h1 class="text-lg font-semibold text-white">Streaming Pipeline Monitor</h1>
          <p class="text-xs text-gray-500 mt-0.5">Solace → Consumer → Redis → FastAPI</p>
        </div>
        <div class="flex items-center gap-2 text-xs">
          <span :class="store.wsConnected ? 'bg-green-400' : 'bg-red-500'" class="w-2 h-2 rounded-full animate-pulse"></span>
          <span class="text-gray-500">{{ store.wsConnected ? 'Live stream' : 'Connecting…' }}</span>
        </div>
      </div>

      <!-- Live counters -->
      <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div class="bg-card border border-border rounded-lg p-4">
          <p class="text-xs text-gray-500 uppercase tracking-widest mb-1">Active Engines</p>
          <p class="text-2xl font-semibold text-white">{{ activeEngines }}</p>
          <p class="text-xs text-gray-600 mt-1">with predictions</p>
        </div>
        <div class="bg-card border border-border rounded-lg p-4">
          <p class="text-xs text-gray-500 uppercase tracking-widest mb-1">Telemetry Engines</p>
          <p class="text-2xl font-semibold text-cyan-400">{{ telemetryCount }}</p>
          <p class="text-xs text-gray-600 mt-1">in Redis feature store</p>
        </div>
        <div class="bg-card border border-border rounded-lg p-4">
          <p class="text-xs text-gray-500 uppercase tracking-widest mb-1">Avg Cycle</p>
          <p class="text-2xl font-semibold text-white">{{ avgCycle || '—' }}</p>
          <p class="text-xs text-gray-600 mt-1">across fleet</p>
        </div>
        <div class="bg-card border border-border rounded-lg p-4">
          <p class="text-xs text-gray-500 uppercase tracking-widest mb-1">Critical</p>
          <p :class="criticalCount > 0 ? 'text-red-400' : 'text-white'" class="text-2xl font-semibold">
            {{ criticalCount }}
          </p>
          <p class="text-xs text-gray-600 mt-1">engines at risk</p>
        </div>
      </div>

      <!-- Pipeline topology -->
      <div class="bg-card border border-border rounded-lg p-4">
        <h3 class="text-sm font-semibold text-gray-300 mb-4">Pipeline Topology</h3>
        <div class="flex flex-col md:flex-row items-stretch gap-2">
          <div v-for="(step, i) in pipeline" :key="step.label" class="flex items-center gap-2 flex-1">
            <div :class="`bg-bg border ${step.color} rounded-lg px-3 py-3 flex-1`">
              <p class="text-xs text-white font-semibold">{{ step.icon }} {{ step.label }}</p>
              <p class="text-xs text-gray-600 mt-1 leading-relaxed">{{ step.desc }}</p>
            </div>
            <span v-if="i < pipeline.length - 1" class="text-accent text-lg hidden md:block shrink-0">→</span>
          </div>
        </div>
      </div>

      <!-- Live telemetry table -->
      <div class="bg-card border border-border rounded-lg p-4">
        <div class="flex items-center justify-between mb-3">
          <h3 class="text-sm font-semibold text-gray-300">Live Telemetry Feed</h3>
          <span class="text-xs text-gray-600">{{ store.lastUpdated ? `Updated ${store.lastUpdated}` : 'Waiting for stream…' }}</span>
        </div>
        <div v-if="!telemetryCount" class="text-xs text-gray-600 py-4 text-center">
          No telemetry yet — start the producer and consumer.
        </div>
        <div v-else class="overflow-auto max-h-52">
          <table class="w-full text-xs">
            <thead>
              <tr class="text-gray-500 border-b border-border">
                <th class="text-left py-2 pr-4">Engine</th>
                <th class="text-right pr-4">Cycle</th>
                <th class="text-right pr-4">Window</th>
                <th class="text-right">Last Event</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="[id, meta] in [...store.telemetry.entries()].slice(0, 20)"
                :key="id" class="border-b border-border/40">
                <td class="py-1.5 pr-4 font-mono text-cyan-400">{{ id }}</td>
                <td class="text-right pr-4 text-white font-mono">{{ meta.cycle }}</td>
                <td class="text-right pr-4 text-gray-400">{{ meta.window_size }}</td>
                <td class="text-right text-gray-600 font-mono">
                  {{ meta.event_time_ms ? new Date(meta.event_time_ms).toLocaleTimeString() : '—' }}
                </td>
              </tr>
            </tbody>
          </table>
          <p v-if="telemetryCount > 20" class="text-xs text-gray-600 mt-2 text-center">
            Showing 20 of {{ telemetryCount }} engines
          </p>
        </div>
      </div>

      <!-- Service status -->
      <div class="bg-card border border-border rounded-lg p-4">
        <h3 class="text-sm font-semibold text-gray-300 mb-3">Service Health</h3>
        <div class="grid grid-cols-2 md:grid-cols-3 gap-3">
          <div v-for="svc in services" :key="svc.name"
            class="bg-bg border border-border rounded-lg p-3 flex items-center justify-between">
            <div>
              <p :class="`text-xs font-semibold ${svc.color}`">{{ svc.name }}</p>
              <p class="text-xs text-gray-600 mt-0.5">:{{ svc.port }}</p>
            </div>
            <div class="flex items-center gap-2">
              <span v-if="svc.status === 'checking'" class="w-2 h-2 rounded-full bg-gray-500 animate-pulse"></span>
              <span v-else-if="svc.status === 'up'"  class="w-2 h-2 rounded-full bg-green-400"></span>
              <span v-else                            class="w-2 h-2 rounded-full bg-red-500"></span>
              <a v-if="svc.url" :href="svc.url" target="_blank"
                class="text-xs text-gray-600 hover:text-accent">↗</a>
            </div>
          </div>
        </div>
      </div>

      <!-- Quick commands -->
      <div class="bg-card border border-border rounded-lg p-4">
        <h3 class="text-sm font-semibold text-gray-300 mb-3">Quick Start</h3>
        <div class="space-y-2 text-xs font-mono">
          <div class="bg-bg rounded p-2 text-gray-400">$ docker compose up -d</div>
          <div class="bg-bg rounded p-2 text-gray-400">$ python -m streaming.producer.telemetry_producer --throttle 50</div>
          <div class="bg-bg rounded p-2 text-gray-400">$ python -m streaming.pipeline.standalone_consumer</div>
        </div>
      </div>
    </div>
  </DashboardLayout>
</template>
