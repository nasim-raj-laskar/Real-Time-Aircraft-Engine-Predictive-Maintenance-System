<script setup lang="ts">
import { computed } from 'vue'
import { useAlertStore } from '../../stores/alertStore'
import RiskBadge from '../ui/RiskBadge.vue'
import type { RiskLevel } from '../../types'

const store = useAlertStore()
const active = computed(() => store.unacknowledged().slice(0, 8))
</script>

<template>
  <div class="bg-card border border-border rounded-lg p-4">
    <div class="flex items-center justify-between mb-3">
      <h3 class="text-sm font-semibold text-gray-300">Active Alerts</h3>
      <span class="text-xs text-gray-500">{{ active.length }} unack'd</span>
    </div>
    <div v-if="!active.length" class="text-xs text-gray-600 py-4 text-center">No active alerts</div>
    <div v-for="a in active" :key="a.id" class="flex items-center justify-between py-2 border-b border-border last:border-0">
      <div>
        <span class="text-sm text-white font-mono">{{ a.engine_id }}</span>
        <span class="text-xs text-gray-500 ml-2">RUL {{ a.remaining_cycles }}cy</span>
      </div>
      <div class="flex items-center gap-2">
        <RiskBadge :level="a.risk_level as RiskLevel" />
        <button @click="store.acknowledge(a.id)" class="text-xs text-gray-600 hover:text-gray-400">✕</button>
      </div>
    </div>
  </div>
</template>
