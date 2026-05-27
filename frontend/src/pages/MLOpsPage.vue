<script setup lang="ts">
import { onMounted } from 'vue'
import DashboardLayout from '../layouts/DashboardLayout.vue'
import { useEngineStore } from '../stores/engineStore'

const store = useEngineStore()
onMounted(() => { store.fetchModelInfo() })

const metrics = [
  { label: 'Test RMSE',          value: '26.15 cy', target: '< 20',   ok: false },
  { label: 'NASA Score',         value: '2181.2',   target: '< 2000', ok: false },
  { label: 'Precision (Crit.)',  value: '0.0%',     target: '> 80%',  ok: false },
  { label: 'Recall (Crit.)',     value: '0.0%',     target: '> 75%',  ok: false },
  { label: 'F1-Score',           value: '0.643',    target: '> 0.80', ok: false },
]
</script>

<template>
  <DashboardLayout>
    <div class="p-6 space-y-6">
      <div>
        <h1 class="text-lg font-semibold text-white">ML Observability</h1>
        <p class="text-xs text-gray-500 mt-0.5">Model registry, performance metrics, drift monitoring</p>
      </div>

      <!-- Model info -->
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div class="bg-card border border-border rounded-lg p-4">
          <h3 class="text-sm font-semibold text-gray-300 mb-3">Active Model</h3>
          <template v-if="store.modelInfo">
            <div class="space-y-2 text-xs">
              <div class="flex justify-between">
                <span class="text-gray-500">Type</span>
                <span class="text-white font-mono">{{ store.modelInfo.model_type }}</span>
              </div>
              <div class="flex justify-between">
                <span class="text-gray-500">Version</span>
                <span class="text-cyan-400 font-mono">{{ store.modelInfo.model_version }}</span>
              </div>
              <div class="flex justify-between">
                <span class="text-gray-500">Input Shape</span>
                <span class="text-white font-mono">{{ store.modelInfo.input_shape.join(' x ') }}</span>
              </div>
              <div class="flex justify-between">
                <span class="text-gray-500">RUL Clip</span>
                <span class="text-white font-mono">{{ store.modelInfo.rul_clip }} cycles</span>
              </div>
              <div class="flex justify-between">
                <span class="text-gray-500">Sensors</span>
                <span class="text-white font-mono">{{ store.modelInfo.sensors.length }}</span>
              </div>
            </div>
          </template>
          <p v-else class="text-xs text-gray-600">Loading model info…</p>
        </div>

        <!-- Architecture -->
        <div class="bg-card border border-border rounded-lg p-4">
          <h3 class="text-sm font-semibold text-gray-300 mb-3">Architecture</h3>
          <div class="space-y-1 text-xs font-mono">
            <div class="bg-bg rounded px-2 py-1 text-cyan-400">Input (batch, 30, 11)</div>
            <div class="bg-bg rounded px-2 py-1 text-white">GRU 128 -&gt; Dropout 0.2</div>
            <div class="bg-bg rounded px-2 py-1 text-white">GRU 64  -&gt; Dropout 0.2</div>
            <div class="bg-bg rounded px-2 py-1 text-white">GRU 32  -&gt; Dropout 0.15</div>
            <div class="bg-bg rounded px-2 py-1 text-white">Dense 32 (ReLU + L2)</div>
            <div class="bg-bg rounded px-2 py-1 text-white">Dense 16 (ReLU + L2)</div>
            <div class="bg-bg rounded px-2 py-1 text-green-400">Output 1 (Sigmoid) -&gt; RUL in [0,1]</div>
          </div>
        </div>
      </div>

      <!-- Performance metrics -->
      <div class="bg-card border border-border rounded-lg p-4">
        <h3 class="text-sm font-semibold text-gray-300 mb-3">Performance Metrics</h3>
        <div class="overflow-auto">
          <table class="w-full text-xs">
            <thead>
              <tr class="text-gray-500 border-b border-border">
                <th class="text-left py-2 pr-6">Metric</th>
                <th class="text-right pr-6">Value</th>
                <th class="text-right pr-6">Target</th>
                <th class="text-right">Status</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="m in metrics" :key="m.label" class="border-b border-border/50">
                <td class="py-2 pr-6 text-gray-300">{{ m.label }}</td>
                <td class="text-right pr-6 text-white font-mono">{{ m.value }}</td>
                <td class="text-right pr-6 text-gray-500">{{ m.target }}</td>
                <td class="text-right">
                  <span :class="m.ok ? 'text-green-400' : 'text-red-400'">{{ m.ok ? 'OK' : 'FAIL' }}</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Drift monitoring links -->
      <div class="bg-card border border-border rounded-lg p-4">
        <h3 class="text-sm font-semibold text-gray-300 mb-3">Drift Monitoring</h3>
        <div class="grid grid-cols-2 md:grid-cols-3 gap-3 text-xs">
          <a href="http://localhost:9090" target="_blank"
            class="bg-bg border border-border rounded-lg p-3 hover:border-accent transition-colors">
            <p class="text-purple-400 font-semibold">Prometheus</p>
            <p class="text-gray-600 mt-1">Metrics & alerting</p>
          </a>
          <a href="http://localhost:3000" target="_blank"
            class="bg-bg border border-border rounded-lg p-3 hover:border-accent transition-colors">
            <p class="text-pink-400 font-semibold">Grafana</p>
            <p class="text-gray-600 mt-1">Dashboards</p>
          </a>
          <a href="http://localhost:8000/metrics" target="_blank"
            class="bg-bg border border-border rounded-lg p-3 hover:border-accent transition-colors">
            <p class="text-cyan-400 font-semibold">API Metrics</p>
            <p class="text-gray-600 mt-1">Prometheus endpoint</p>
          </a>
        </div>
      </div>
    </div>
  </DashboardLayout>
</template>
