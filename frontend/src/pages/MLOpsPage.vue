<script setup lang="ts">
import { onMounted, ref } from 'vue'
import DashboardLayout from '../layouts/DashboardLayout.vue'
import { useEngineStore } from '../stores/engineStore'
import { getModelEvaluation } from '../services/api'

const store = useEngineStore()

interface Metric {
  label: string
  value: string
  target: string
  ok: boolean
}

const metrics = ref<Metric[]>([])

onMounted(async () => {
  store.fetchModelInfo()
  try {
    const { data: e } = await getModelEvaluation()
    metrics.value = [
      { label: 'Test RMSE',         value: `${Number(e.rmse).toFixed(2)} cy`,                        target: '< 20',   ok: e.rmse < 20 },
      { label: 'NASA Score',        value: `${Number(e.nasa_score).toFixed(1)}`,                     target: '< 2000', ok: e.nasa_score < 2000 },
      { label: 'Precision (Crit.)', value: `${(Number(e.precision_critical) * 100).toFixed(1)}%`,   target: '> 80%',  ok: e.precision_critical > 0.8 },
      { label: 'Recall (Crit.)',    value: `${(Number(e.recall_critical) * 100).toFixed(1)}%`,      target: '> 75%',  ok: e.recall_critical > 0.75 },
      { label: 'F1 (Crit.)',        value: `${Number(e.f1_critical).toFixed(3)}`,                   target: '> 0.80', ok: e.f1_critical > 0.8 },
      { label: 'Accuracy',          value: `${(Number(e.accuracy) * 100).toFixed(1)}%`,             target: '> 80%',  ok: e.accuracy > 0.8 },
      { label: 'F1 (Weighted)',     value: `${Number(e.f1_weighted).toFixed(3)}`,                   target: '> 0.80', ok: e.f1_weighted > 0.8 },
    ]
  } catch { /* backend not ready */ }
})

const modelReady = () =>
  !!(store.modelInfo && store.modelInfo.sensors && store.modelInfo.sensors.length > 0)
</script>

<template>
  <DashboardLayout>
    <div class="p-6 space-y-6">
      <div>
        <h1 class="text-lg font-semibold text-white">ML Observability</h1>
        <p class="text-xs text-gray-500 mt-0.5">Model registry, performance metrics, drift monitoring</p>
      </div>

      <!-- Model info + Architecture -->
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">

        <!-- Active Model -->
        <div class="bg-card border border-border rounded-lg p-4">
          <h3 class="text-sm font-semibold text-gray-300 mb-3">Active Model</h3>
          <template v-if="modelReady()">
            <div class="space-y-2 text-xs">
              <div class="flex justify-between">
                <span class="text-gray-500">Type</span>
                <span class="text-white font-mono">{{ store.modelInfo!.model_type ?? '-' }}</span>
              </div>
              <div class="flex justify-between">
                <span class="text-gray-500">Version</span>
                <span class="text-cyan-400 font-mono">{{ store.modelInfo!.model_version ?? '-' }}</span>
              </div>
              <div class="flex justify-between">
                <span class="text-gray-500">Input Shape</span>
                <span class="text-white font-mono">{{ (store.modelInfo!.input_shape ?? []).join(' x ') }}</span>
              </div>
              <div class="flex justify-between">
                <span class="text-gray-500">RUL Clip</span>
                <span class="text-white font-mono">{{ store.modelInfo!.rul_clip ?? '-' }} cycles</span>
              </div>
              <div class="flex justify-between">
                <span class="text-gray-500">Sensors</span>
                <span class="text-white font-mono">{{ (store.modelInfo!.sensors ?? []).length }}</span>
              </div>
              <div class="flex justify-between">
                <span class="text-gray-500">Trained On</span>
                <span class="text-white font-mono text-right">
                  {{ store.modelInfo!.trained_on ? new Date(store.modelInfo!.trained_on).toLocaleDateString() : '-' }}
                </span>
              </div>
            </div>
            <!-- Sensor tags -->
            <div class="flex flex-wrap gap-1 mt-3">
              <span v-for="s in (store.modelInfo!.sensors ?? [])" :key="s"
                class="text-xs font-mono bg-bg border border-border px-2 py-0.5 rounded text-cyan-400">
                {{ s }}
              </span>
            </div>
          </template>
          <div v-else class="flex items-center gap-2 text-xs text-gray-600 py-4">
            <span class="animate-pulse">Loading model info...</span>
          </div>
        </div>

        <!-- Architecture -->
        <div class="bg-card border border-border rounded-lg p-4">
          <h3 class="text-sm font-semibold text-gray-300 mb-3">Architecture</h3>
          <div class="space-y-1 text-xs font-mono">
            <div class="bg-bg rounded px-2 py-1 text-cyan-400">Input (batch, 30, 11)</div>
            <div class="bg-bg rounded px-2 py-1 text-white">GRU 128 units, return_seq=True</div>
            <div class="bg-bg rounded px-2 py-1 text-gray-500 pl-4">Dropout 0.2</div>
            <div class="bg-bg rounded px-2 py-1 text-white">GRU 64 units, return_seq=True</div>
            <div class="bg-bg rounded px-2 py-1 text-gray-500 pl-4">Dropout 0.2</div>
            <div class="bg-bg rounded px-2 py-1 text-white">GRU 32 units</div>
            <div class="bg-bg rounded px-2 py-1 text-gray-500 pl-4">Dropout 0.15</div>
            <div class="bg-bg rounded px-2 py-1 text-white">Dense 32 (ReLU + L2)</div>
            <div class="bg-bg rounded px-2 py-1 text-white">Dense 16 (ReLU + L2)</div>
            <div class="bg-bg rounded px-2 py-1 text-green-400">Output 1 (Sigmoid) -&gt; RUL in [0,1]</div>
          </div>
        </div>
      </div>

      <!-- Performance metrics -->
      <div class="bg-card border border-border rounded-lg p-4">
        <h3 class="text-sm font-semibold text-gray-300 mb-3">Performance Metrics</h3>
        <div v-if="metrics.length" class="overflow-auto">
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
                <td class="text-right pr-6 font-mono" :class="m.ok ? 'text-green-400' : 'text-red-400'">{{ m.value }}</td>
                <td class="text-right pr-6 text-gray-500">{{ m.target }}</td>
                <td class="text-right">
                  <span :class="m.ok ? 'text-green-400' : 'text-red-400'">{{ m.ok ? 'PASS' : 'FAIL' }}</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <p v-else class="text-xs text-gray-600 animate-pulse">Loading metrics...</p>
      </div>

      <!-- Drift monitoring links -->
      <div class="bg-card border border-border rounded-lg p-4">
        <h3 class="text-sm font-semibold text-gray-300 mb-3">Drift Monitoring</h3>
        <div class="grid grid-cols-2 md:grid-cols-3 gap-3 text-xs">
          <a href="http://localhost:9090" target="_blank"
            class="bg-bg border border-border rounded-lg p-3 hover:border-accent transition-colors">
            <p class="text-purple-400 font-semibold">Prometheus</p>
            <p class="text-gray-600 mt-1">Metrics &amp; alerting</p>
          </a>
          <a href="http://localhost:3000" target="_blank"
            class="bg-bg border border-border rounded-lg p-3 hover:border-accent transition-colors">
            <p class="text-pink-400 font-semibold">Grafana</p>
            <p class="text-gray-600 mt-1">Dashboards</p>
          </a>
          <a href="http://localhost:8000/model/evaluation" target="_blank"
            class="bg-bg border border-border rounded-lg p-3 hover:border-accent transition-colors">
            <p class="text-cyan-400 font-semibold">Evaluation API</p>
            <p class="text-gray-600 mt-1">Raw metrics JSON</p>
          </a>
        </div>
      </div>
    </div>
  </DashboardLayout>
</template>
