<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useEngineStore } from '../../stores/engineStore'
import RiskBadge from '../ui/RiskBadge.vue'
import type { RiskLevel } from '../../types'

const store = useEngineStore()
const router = useRouter()
const filter = ref<string>('')
const riskFilter = ref<string>('ALL')

const rows = computed(() => {
  let list = store.sortedPredictions
  if (filter.value) list = list.filter(p => p.engine_id.toLowerCase().includes(filter.value.toLowerCase()))
  if (riskFilter.value !== 'ALL') list = list.filter(p => p.risk_level === riskFilter.value)
  return list
})
</script>

<template>
  <div class="bg-card border border-border rounded-lg p-4">
    <div class="flex items-center gap-3 mb-3">
      <h3 class="text-sm font-semibold text-gray-300 flex-1">Engine Fleet</h3>
      <input v-model="filter" placeholder="Search engine…"
        class="bg-bg border border-border rounded px-2 py-1 text-xs text-gray-300 w-36 focus:outline-none focus:border-accent" />
      <select v-model="riskFilter"
        class="bg-bg border border-border rounded px-2 py-1 text-xs text-gray-300 focus:outline-none focus:border-accent">
        <option>ALL</option>
        <option>CRITICAL</option>
        <option>HIGH</option>
        <option>MEDIUM</option>
        <option>LOW</option>
      </select>
    </div>

    <div class="overflow-auto max-h-80">
      <table class="w-full text-xs">
        <thead>
          <tr class="text-gray-500 border-b border-border">
            <th class="text-left py-2 pr-4">Engine</th>
            <th class="text-right pr-4">RUL</th>
            <th class="text-right pr-4">Risk</th>
            <th class="text-right pr-4">Status</th>
            <th class="text-right">Updated</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="p in rows" :key="p.engine_id"
            @click="router.push(`/engine/${p.engine_id}`)"
            class="border-b border-border/50 hover:bg-white/5 cursor-pointer transition-colors">
            <td class="py-2 pr-4 font-mono text-white">{{ p.engine_id }}</td>
            <td class="text-right pr-4" :class="`risk-${p.risk_level}`">{{ p.remaining_cycles }} cy</td>
            <td class="text-right pr-4"><RiskBadge :level="p.risk_level as RiskLevel" /></td>
            <td class="text-right pr-4 text-gray-500">{{ (p.failure_risk * 100).toFixed(0) }}%</td>
            <td class="text-right text-gray-600">{{ new Date(p.timestamp).toLocaleTimeString() }}</td>
          </tr>
          <tr v-if="!rows.length">
            <td colspan="5" class="text-center text-gray-600 py-6">No engines — waiting for telemetry…</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
