<script setup lang="ts">
import { onMounted, onUnmounted, ref, computed } from 'vue'
import DashboardLayout from '../layouts/DashboardLayout.vue'
import ModelArchDiagram from '../components/ModelArchDiagram.vue'
import { useEngineStore } from '../stores/engineStore'
import { getModelEvaluation, getDriftReports, triggerPipeline, getPipelineStatus } from '../services/api'

const store = useEngineStore()

interface Metric { label: string; value: string; target: string; ok: boolean }

const metrics      = ref<Metric[]>([])
const reports      = ref<{ filename: string; size_kb: number }[]>([])
const activeReport = ref<string | null>(null)
const showIframe   = ref(false)

// ── Pipeline retraining ───────────────────────────────────────────────────────
type PipelineStatus = 'idle' | 'running' | 'success' | 'failed'
const pipelineStatus  = ref<PipelineStatus>('idle')
const pipelineStarted = ref<string | null>(null)
const logLines        = ref<string[]>([])
const showLogs        = ref(false)
const logContainer    = ref<HTMLElement | null>(null)

let statusTimer: ReturnType<typeof setInterval> | null = null
let logEs: EventSource | null = null

const statusColor = computed(() => ({
  idle:    'text-gray-400',
  running: 'text-yellow-400',
  success: 'text-green-400',
  failed:  'text-red-400',
}[pipelineStatus.value]))

const statusLabel = computed(() => ({
  idle:    'Idle',
  running: '⟳ Running…',
  success: '✓ Completed',
  failed:  '✗ Failed',
}[pipelineStatus.value]))

async function fetchStatus() {
  try {
    const { data } = await getPipelineStatus()
    pipelineStatus.value  = data.status
    pipelineStarted.value = data.started_at
  } catch { /* offline */ }
}

function startLogStream() {
  logEs?.close()
  logLines.value = []
  showLogs.value = true
  const base = import.meta.env.VITE_API_URL || ''
  logEs = new EventSource(`${base}/pipeline/logs`)
  logEs.onmessage = (e) => {
    if (e.data === '[DONE]') { logEs?.close(); return }
    logLines.value.push(e.data)
    setTimeout(() => {
      if (logContainer.value) logContainer.value.scrollTop = logContainer.value.scrollHeight
    }, 20)
  }
  logEs.onerror = () => logEs?.close()
}

async function retrain() {
  try {
    await triggerPipeline()
    pipelineStatus.value = 'running'
    startLogStream()
    statusTimer = setInterval(async () => {
      await fetchStatus()
      if (pipelineStatus.value !== 'running') {
        clearInterval(statusTimer!); statusTimer = null
        if (pipelineStatus.value === 'success') {
          await loadMetrics()
          await loadReports()
        }
      }
    }, 5000)
  } catch (err: any) {
    if (err?.response?.status === 409) alert('Pipeline is already running.')
  }
}

// ── Data loading ──────────────────────────────────────────────────────────────
async function loadMetrics() {
  try {
    const { data: e } = await getModelEvaluation()
    metrics.value = [
      { label: 'Test RMSE',         value: `${Number(e.rmse).toFixed(2)} cy`,                    target: '< 20',   ok: e.rmse < 20 },
      { label: 'NASA Score',        value: `${Number(e.nasa_score).toFixed(1)}`,                 target: '< 2000', ok: e.nasa_score < 2000 },
      { label: 'Precision (Crit.)', value: `${(Number(e.precision_critical)*100).toFixed(1)}%`, target: '> 80%',  ok: e.precision_critical > 0.8 },
      { label: 'Recall (Crit.)',    value: `${(Number(e.recall_critical)*100).toFixed(1)}%`,    target: '> 75%',  ok: e.recall_critical > 0.75 },
      { label: 'F1 (Crit.)',        value: `${Number(e.f1_critical).toFixed(3)}`,               target: '> 0.80', ok: e.f1_critical > 0.8 },
      { label: 'Accuracy',          value: `${(Number(e.accuracy)*100).toFixed(1)}%`,           target: '> 80%',  ok: e.accuracy > 0.8 },
      { label: 'F1 (Weighted)',     value: `${Number(e.f1_weighted).toFixed(3)}`,               target: '> 0.80', ok: e.f1_weighted > 0.8 },
    ]
  } catch { /* backend not ready */ }
}

async function loadReports() {
  try {
    const { data } = await getDriftReports()
    reports.value = data.reports
  } catch { /* backend not ready */ }
}

const reportUrl = computed(() =>
  activeReport.value ? `${import.meta.env.VITE_API_URL || ''}/drift/reports/${activeReport.value}` : ''
)

function openReport(filename: string) { activeReport.value = filename; showIframe.value = true }
function closeReport()                { showIframe.value = false; activeReport.value = null }

const modelReady = () =>
  !!(store.modelInfo && store.modelInfo.sensors && store.modelInfo.sensors.length > 0)

onMounted(async () => {
  store.fetchModelInfo()
  await Promise.all([loadMetrics(), loadReports(), fetchStatus()])
})

onUnmounted(() => {
  if (statusTimer) clearInterval(statusTimer)
  logEs?.close()
})
</script>

<template>
  <DashboardLayout>
    <div class="p-6 space-y-6">

      <!-- Header -->
      <div class="flex items-center justify-between">
        <div>
          <h1 class="text-lg font-semibold text-white">ML Observability</h1>
          <p class="text-xs text-gray-500 mt-0.5">Model registry, performance metrics, drift monitoring</p>
        </div>
        <!-- Retrain button -->
        <div class="flex items-center gap-3">
          <span class="text-xs" :class="statusColor">{{ statusLabel }}</span>
          <span v-if="pipelineStarted && pipelineStatus !== 'idle'" class="text-xs text-gray-600">
            {{ new Date(pipelineStarted).toLocaleTimeString() }}
          </span>
          <button @click="retrain" :disabled="pipelineStatus === 'running'"
            class="flex items-center gap-2 px-4 py-2 rounded text-xs font-semibold
                   bg-accent text-bg hover:opacity-90
                   disabled:opacity-40 disabled:cursor-not-allowed transition-opacity">
            <span :class="pipelineStatus === 'running' ? 'animate-spin' : ''">⟳</span>
            {{ pipelineStatus === 'running' ? 'Training…' : 'Retrain Model' }}
          </button>
        </div>
      </div>

      <!-- Pipeline log panel -->
      <div v-if="showLogs" class="bg-card border border-border rounded-lg overflow-hidden">
        <div class="flex items-center justify-between px-4 py-2 border-b border-border">
          <div class="flex items-center gap-2">
            <span v-if="pipelineStatus === 'running'" class="w-2 h-2 rounded-full bg-yellow-400 animate-pulse"></span>
            <span v-else-if="pipelineStatus === 'success'" class="w-2 h-2 rounded-full bg-green-400"></span>
            <span v-else class="w-2 h-2 rounded-full bg-red-500"></span>
            <p class="text-xs font-semibold text-gray-300">Pipeline Logs</p>
            <span class="text-xs text-gray-600">{{ logLines.length }} lines</span>
          </div>
          <button @click="showLogs = false" class="text-gray-600 hover:text-white text-xs">✕ hide</button>
        </div>
        <div ref="logContainer"
          class="h-72 overflow-y-auto p-3 font-mono text-xs bg-black/40 space-y-0.5">
          <div v-if="!logLines.length" class="text-gray-600 animate-pulse">Waiting for output…</div>
          <div v-for="(line, i) in logLines" :key="i"
            :class="{
              'text-red-400':    line.includes('ERROR') || line.includes('error'),
              'text-yellow-400': line.includes('WARNING') || line.includes('warning'),
              'text-green-400':  line.includes('completed') || line.includes('COMPLETED') || line.includes('SUCCESS'),
              'text-cyan-400':   line.includes('started') || line.includes('Stage'),
              'text-gray-400':   !line.includes('ERROR') && !line.includes('WARNING')
                                 && !line.includes('completed') && !line.includes('started')
                                 && !line.includes('Stage'),
            }">{{ line }}</div>
        </div>
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
          <ModelArchDiagram />
        </div>
      </div>

      <!-- Performance metrics -->
      <div class="bg-card border border-border rounded-lg p-4">
        <div class="flex items-center justify-between mb-3">
          <h3 class="text-sm font-semibold text-gray-300">Performance Metrics</h3>
          <button v-if="pipelineStatus === 'success'" @click="loadMetrics"
            class="text-xs text-accent hover:opacity-80">↺ refresh</button>
        </div>
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

      <!-- Drift monitoring -->
      <div class="bg-card border border-border rounded-lg p-4">
        <h3 class="text-sm font-semibold text-gray-300 mb-3">Drift Monitoring</h3>

        <div class="grid grid-cols-2 gap-3 text-xs mb-4">
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
        </div>

        <p class="text-xs text-gray-500 mb-2">Evidently Reports
          <span class="ml-2 text-gray-600">({{ reports.length }} available)</span>
        </p>
        <div v-if="!reports.length" class="text-xs text-gray-600 py-3">
          No drift reports yet — run <span class="font-mono text-accent">python src/monitoring/drift_monitor.py</span> to generate one.
        </div>
        <div v-else class="space-y-1">
          <div v-for="r in reports" :key="r.filename"
            class="flex items-center justify-between bg-bg border border-border rounded px-3 py-2
                   hover:border-accent transition-colors cursor-pointer"
            @click="openReport(r.filename)">
            <div class="flex items-center gap-2">
              <span class="text-green-400 text-xs">●</span>
              <span class="text-xs font-mono text-gray-300">{{ r.filename }}</span>
            </div>
            <div class="flex items-center gap-3">
              <span class="text-xs text-gray-600">{{ r.size_kb }} KB</span>
              <span class="text-xs text-accent">View ↗</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Evidently iframe modal -->
      <Teleport to="body">
        <div v-if="showIframe" class="fixed inset-0 z-50 flex flex-col bg-black/80">
          <div class="flex items-center justify-between px-4 py-3 bg-card border-b border-border shrink-0">
            <div>
              <p class="text-sm font-semibold text-white">Evidently Drift Report</p>
              <p class="text-xs text-gray-500 font-mono mt-0.5">{{ activeReport }}</p>
            </div>
            <button @click="closeReport" class="text-gray-400 hover:text-white text-xl leading-none px-2">✕</button>
          </div>
          <iframe :src="reportUrl" class="flex-1 w-full border-0 bg-white" />
        </div>
      </Teleport>

    </div>
  </DashboardLayout>
</template>
