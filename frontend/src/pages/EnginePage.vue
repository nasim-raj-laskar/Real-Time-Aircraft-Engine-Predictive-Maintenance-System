<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import DashboardLayout from '../layouts/DashboardLayout.vue'
import RulGauge from '../components/charts/RulGauge.vue'
import RiskBadge from '../components/ui/RiskBadge.vue'
import { useEngineStore } from '../stores/engineStore'
import { predictEngine } from '../services/api'
import type { RiskLevel } from '../types'

const route = useRoute()
const router = useRouter()
const store = useEngineStore()

const engineId = computed(() => route.params.id as string)
const prediction = computed(() => store.predictions.get(engineId.value) ?? null)
const meta = computed(() => store.telemetry.get(engineId.value) ?? null)
const loading = ref(false)
const error = ref('')

// Fetch once if not yet in store
onMounted(async () => {
  if (!prediction.value) {
    loading.value = true
    try {
      const res = await predictEngine(engineId.value)
      store.applyPredictions([res.data])
    } catch (e: any) {
      error.value = e?.response?.data?.detail ?? 'Engine not found'
    } finally {
      loading.value = false
    }
  }
})

const sensors = computed(() => store.modelInfo?.sensors ?? [])
</script>

<template>
  <DashboardLayout>
    <div class="p-6 space-y-6">
      <!-- Back + header -->
      <div class="flex items-center gap-4">
        <button @click="router.back()" class="text-gray-500 hover:text-white text-sm">← Back</button>
        <div>
          <h1 class="text-lg font-semibold text-white font-mono">{{ engineId }}</h1>
          <p class="text-xs text-gray-500">Engine Detail View</p>
        </div>
      </div>

      <div v-if="loading" class="text-gray-500 text-sm">Loading…</div>
      <div v-else-if="error" class="text-red-400 text-sm">{{ error }}</div>

      <template v-else-if="prediction">
        <!-- Health summary -->
        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
          <!-- Gauge -->
          <div class="bg-card border border-border rounded-lg p-4 flex flex-col items-center">
            <p class="text-xs text-gray-500 uppercase tracking-widest mb-2">Failure Risk</p>
            <RulGauge :risk="prediction.failure_risk" :rul="prediction.remaining_cycles" />
            <RiskBadge :level="prediction.risk_level as RiskLevel" />
          </div>

          <!-- Stats -->
          <div class="md:col-span-2 grid grid-cols-2 gap-4">
            <div class="bg-card border border-border rounded-lg p-4">
              <p class="text-xs text-gray-500 uppercase tracking-widest mb-1">Remaining Cycles</p>
              <p :class="`text-3xl font-semibold risk-${prediction.risk_level}`">
                {{ prediction.remaining_cycles }}
              </p>
              <p class="text-xs text-gray-600 mt-1">out of 125 max</p>
            </div>
            <div class="bg-card border border-border rounded-lg p-4">
              <p class="text-xs text-gray-500 uppercase tracking-widest mb-1">Confidence</p>
              <p class="text-3xl font-semibold text-cyan-400">{{ (prediction.confidence * 100).toFixed(0) }}%</p>
            </div>
            <div class="bg-card border border-border rounded-lg p-4">
              <p class="text-xs text-gray-500 uppercase tracking-widest mb-1">Current Cycle</p>
              <p class="text-2xl font-semibold text-white">{{ meta?.cycle ?? '—' }}</p>
            </div>
            <div class="bg-card border border-border rounded-lg p-4">
              <p class="text-xs text-gray-500 uppercase tracking-widest mb-1">Model</p>
              <p class="text-sm font-mono text-gray-300 mt-2">{{ prediction.model_version }}</p>
            </div>
          </div>
        </div>

        <!-- Sensor list -->
        <div class="bg-card border border-border rounded-lg p-4">
          <h3 class="text-sm font-semibold text-gray-300 mb-3">Active Sensors ({{ sensors.length }})</h3>
          <div class="flex flex-wrap gap-2">
            <span v-for="s in sensors" :key="s"
              class="text-xs font-mono bg-bg border border-border px-2 py-1 rounded text-cyan-400">
              {{ s }}
            </span>
          </div>
        </div>

        <!-- Metadata -->
        <div class="bg-card border border-border rounded-lg p-4">
          <h3 class="text-sm font-semibold text-gray-300 mb-3">Prediction Metadata</h3>
          <div class="grid grid-cols-2 md:grid-cols-4 gap-4 text-xs">
            <div>
              <p class="text-gray-500">Timestamp</p>
              <p class="text-white mt-1">{{ new Date(prediction.timestamp).toLocaleString() }}</p>
            </div>
            <div>
              <p class="text-gray-500">Risk Score</p>
              <p class="text-white mt-1">{{ (prediction.failure_risk * 100).toFixed(1) }}%</p>
            </div>
            <div>
              <p class="text-gray-500">Window Size</p>
              <p class="text-white mt-1">{{ meta?.window_size ?? 30 }} cycles</p>
            </div>
            <div>
              <p class="text-gray-500">Source</p>
              <p class="text-white mt-1">Redis Feature Store</p>
            </div>
          </div>
        </div>
      </template>
    </div>
  </DashboardLayout>
</template>
