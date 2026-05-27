<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useEngineStore } from '../stores/engineStore'
import { useAlertStore } from '../stores/alertStore'

const route = useRoute()
const engineStore = useEngineStore()
const alertStore = useAlertStore()

const nav = [
  { to: '/',         label: 'Fleet',    icon: '⬡' },
  { to: '/pipeline', label: 'Pipeline', icon: '⇌' },
  { to: '/mlops',    label: 'MLOps',    icon: '◈' },
]

const unackCount = computed(() => alertStore.unacknowledged().length)
</script>

<template>
  <div class="flex h-screen overflow-hidden">
    <!-- Sidebar -->
    <aside class="w-52 bg-card border-r border-border flex flex-col shrink-0">
      <div class="px-4 py-5 border-b border-border">
        <p class="text-xs text-accent font-semibold tracking-widest uppercase">AeroWatch</p>
        <p class="text-xs text-gray-600 mt-0.5">Predictive Maintenance</p>
      </div>

      <nav class="flex-1 px-2 py-4 space-y-1">
        <router-link v-for="n in nav" :key="n.to" :to="n.to"
          :class="[
            'flex items-center gap-3 px-3 py-2 rounded text-sm transition-colors',
            route.path === n.to
              ? 'bg-accent/10 text-accent'
              : 'text-gray-400 hover:text-white hover:bg-white/5'
          ]">
          <span class="text-base">{{ n.icon }}</span>
          {{ n.label }}
        </router-link>
      </nav>

      <div class="px-4 py-4 border-t border-border space-y-2 text-xs">
        <div class="flex justify-between text-gray-500">
          <span>Engines</span>
          <span class="text-white">{{ engineStore.predictions.size }}</span>
        </div>
        <div class="flex justify-between text-gray-500">
          <span>Critical</span>
          <span :class="engineStore.criticalCount > 0 ? 'text-red-400' : 'text-white'">
            {{ engineStore.criticalCount }}
          </span>
        </div>
        <div class="flex justify-between text-gray-500">
          <span>Alerts</span>
          <span :class="unackCount > 0 ? 'text-orange-400' : 'text-white'">{{ unackCount }}</span>
        </div>
        <div class="flex items-center gap-2 pt-1">
          <span :class="engineStore.wsConnected ? 'bg-green-400' : 'bg-red-500'" class="w-2 h-2 rounded-full"></span>
          <span class="text-gray-600">{{ engineStore.wsConnected ? 'Live' : 'Offline' }}</span>
        </div>
      </div>
    </aside>

    <!-- Main content -->
    <main class="flex-1 overflow-auto bg-bg">
      <slot />
    </main>
  </div>
</template>
