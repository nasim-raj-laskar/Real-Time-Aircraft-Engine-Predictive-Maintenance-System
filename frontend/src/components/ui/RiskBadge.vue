<script setup lang="ts">
import type { RiskLevel } from '../../types'
defineProps<{ level: RiskLevel }>()
</script>

<template>
  <span :class="`badge-${level} text-xs font-semibold px-2 py-0.5 rounded`">
    {{ level }}
  </span>
</template>
