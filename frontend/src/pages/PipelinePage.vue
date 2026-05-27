<script setup lang="ts">
import DashboardLayout from '../layouts/DashboardLayout.vue'
import { useWebSockets } from '../composables/useWebSockets'
import { useEngineStore } from '../stores/engineStore'

useWebSockets()
const store = useEngineStore()

const services = [
  { name: 'FastAPI Inference',   port: 8000, path: '/health',           color: 'text-cyan-400' },
  { name: 'Redis Feature Store', port: 6379, path: null,                color: 'text-green-400' },
  { name: 'Solace PubSub+',      port: 8080, path: '/SEMP/v2/config',   color: 'text-yellow-400' },
  { name: 'Flink JobManager',    port: 8082, path: '/overview',         color: 'text-orange-400' },
  { name: 'Prometheus',          port: 9090, path: '/-/healthy',        color: 'text-purple-400' },
  { name: 'Grafana',             port: 3000, path: '/api/health',       color: 'text-pink-400' },
]

const pipeline = [
  { label: 'Telemetry Producer', desc: 'Streams FD001 rows → Redis Stream / Solace', icon: '📡' },
  { label: 'Normalization',      desc: 'MinMax scaler applied per event (stateless)', icon: '⚖️' },
  { label: 'Rolling Window',     desc: '30-cycle per-engine keyed buffer',            icon: '🔄' },
  { label: 'Redis Sink',         desc: 'Feature tensors written to engine:{id}:features', icon: '💾' },
  { label: 'S3 Parquet Sink',    desc: 'Offline archive flushed every 500 vectors',   icon: '☁️' },
  { label: 'FastAPI Inference',  desc: 'Reads Redis → GRU → RUL prediction',          icon: '🧠' },
]
</script>

<template>
  <DashboardLayout>
    <div class="p-6 space-y-6">
      <div>
        <h1 class="text-lg font-semibold text-white">Streaming Pipeline Monitor</h1>
        <p class="text-xs text-gray-500 mt-0.5">Solace → Flink/Consumer → Redis → FastAPI</p>
      </div>

      <!-- Live counters -->
      <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div class="bg-card border border-border rounded-lg p-4">
          <p class="text-xs text-gray-500 uppercase tracking-widest mb-1">Active Engines</p>
          <p class="text-2xl font-semibold text-white">{{ store.predictions.size }}</p>
        </div>
        <div class="bg-card border border-border rounded-lg p-4">
          <p class="text-xs text-gray-500 uppercase tracking-widest mb-1">WS Status</p>
          <p :class="store.wsConnected ? 'text-green-400' : 'text-red-400'" class="text-2xl font-semibold">
            {{ store.wsConnected ? 'Live' : 'Down' }}
          </p>
        </div>
        <div class="bg-card border border-border rounded-lg p-4">
          <p class="text-xs text-gray-500 uppercase tracking-widest mb-1">Last Update</p>
          <p class="text-sm font-mono text-white mt-2">{{ store.lastUpdated || '—' }}</p>
        </div>
        <div class="bg-card border border-border rounded-lg p-4">
          <p class="text-xs text-gray-500 uppercase tracking-widest mb-1">Critical</p>
          <p :class="store.criticalCount > 0 ? 'text-red-400' : 'text-white'" class="text-2xl font-semibold">
            {{ store.criticalCount }}
          </p>
        </div>
      </div>

      <!-- Pipeline flow -->
      <div class="bg-card border border-border rounded-lg p-4">
        <h3 class="text-sm font-semibold text-gray-300 mb-4">Pipeline Topology</h3>
        <div class="flex flex-col md:flex-row items-start md:items-center gap-2 flex-wrap">
          <div v-for="(step, i) in pipeline" :key="step.label" class="flex items-center gap-2">
            <div class="bg-bg border border-border rounded-lg px-3 py-2 min-w-36">
              <p class="text-xs text-white font-semibold">{{ step.icon }} {{ step.label }}</p>
              <p class="text-xs text-gray-600 mt-0.5">{{ step.desc }}</p>
            </div>
            <span v-if="i < pipeline.length - 1" class="text-accent text-lg hidden md:block">→</span>
          </div>
        </div>
      </div>

      <!-- Service status -->
      <div class="bg-card border border-border rounded-lg p-4">
        <h3 class="text-sm font-semibold text-gray-300 mb-3">Services</h3>
        <div class="grid grid-cols-2 md:grid-cols-3 gap-3">
          <div v-for="svc in services" :key="svc.name"
            class="bg-bg border border-border rounded-lg p-3 flex items-center justify-between">
            <div>
              <p :class="`text-xs font-semibold ${svc.color}`">{{ svc.name }}</p>
              <p class="text-xs text-gray-600 mt-0.5">:{{ svc.port }}</p>
            </div>
            <a v-if="svc.path" :href="`http://localhost:${svc.port}${svc.path}`" target="_blank"
              class="text-xs text-gray-600 hover:text-accent">↗</a>
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
