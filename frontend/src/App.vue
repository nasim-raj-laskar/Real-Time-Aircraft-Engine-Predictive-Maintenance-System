<script setup lang="ts">
import { useWebSockets } from './composables/useWebSockets'
import { useEngineStore } from './stores/engineStore'

// Single global WS connection — shared across all pages via Pinia store
useWebSockets()
useEngineStore().fetchHealth()
useEngineStore().fetchModelInfo()
</script>

<template>
  <router-view />
</template>
