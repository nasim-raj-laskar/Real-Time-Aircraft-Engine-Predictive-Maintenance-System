<script setup lang="ts">
import { onMounted } from 'vue'
import DashboardLayout from '../layouts/DashboardLayout.vue'
import StatCard from '../components/cards/StatCard.vue'
import EngineTable from '../components/cards/EngineTable.vue'
import AlertsPanel from '../components/cards/AlertsPanel.vue'
import RiskDistributionChart from '../components/charts/RiskDistributionChart.vue'
import RulBarChart from '../components/charts/RulBarChart.vue'
import { useEngineStore } from '../stores/engineStore'
import { useWebSockets } from '../composables/useWebSockets'

const store = useEngineStore()
useWebSockets()

onMounted(() => {
  store.fetchHealth()
  store.fetchModelInfo()
})
</script>

<template>
  <DashboardLayout>
    <div class="p-6 space-y-6">
      <!-- Header -->
      <div class="flex items-center justify-between">
        <div>
          <h1 class="text-lg font-semibold text-white">Fleet Command Center</h1>
          <p class="text-xs text-gray-500 mt-0.5">
            Last update: {{ store.lastUpdated || '—' }}
            <span v-if="store.modelInfo" class="ml-3 text-gray-600">
              Model: {{ store.modelInfo.model_version }}
            </span>
          </p>
        </div>
        <div class="flex items-center gap-2 text-xs">
          <span :class="store.wsConnected ? 'bg-green-400' : 'bg-red-500'" class="w-2 h-2 rounded-full animate-pulse"></span>
          <span class="text-gray-500">{{ store.wsConnected ? 'Live stream' : 'Connecting…' }}</span>
        </div>
      </div>

      <!-- Stat cards -->
      <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard label="Active Engines"  :value="store.predictions.size" />
        <StatCard label="Critical"        :value="store.criticalCount"  color="text-red-400" />
        <StatCard label="High Risk"       :value="store.highCount"      color="text-orange-400" />
        <StatCard label="Avg Fleet RUL"   :value="`${store.avgRul} cy`" color="text-cyan-400" />
      </div>

      <!-- Charts row -->
      <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
        <RiskDistributionChart />
        <div class="md:col-span-2"><RulBarChart /></div>
      </div>

      <!-- Table + Alerts -->
      <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div class="md:col-span-2"><EngineTable /></div>
        <AlertsPanel />
      </div>
    </div>
  </DashboardLayout>
</template>
