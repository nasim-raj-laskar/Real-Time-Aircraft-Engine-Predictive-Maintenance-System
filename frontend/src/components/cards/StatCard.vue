<script setup lang="ts">
defineProps<{ label: string; value: string | number; sub?: string; color?: string }>()
</script>

<template>
  <div class="bg-card border border-border rounded-lg p-4">
    <p class="text-xs text-gray-500 uppercase tracking-widest mb-1">{{ label }}</p>
    <p :class="`text-2xl font-semibold ${color ?? 'text-white'}`">{{ value }}</p>
    <p v-if="sub" class="text-xs text-gray-500 mt-1">{{ sub }}</p>
  </div>
</template>
