<script setup lang="ts">
import { computed } from 'vue'
import { use } from 'echarts/core'
import { PieChart } from 'echarts/charts'
import { TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'
import { useEngineStore } from '../../stores/engineStore'

use([PieChart, TooltipComponent, LegendComponent, CanvasRenderer])

const store = useEngineStore()

const option = computed(() => {
  const preds = [...store.predictions.values()]
  const counts = { LOW: 0, MEDIUM: 0, HIGH: 0, CRITICAL: 0 }
  preds.forEach(p => counts[p.risk_level]++)
  return {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    legend: { show: false },
    series: [{
      type: 'pie',
      radius: ['50%', '75%'],
      data: [
        { value: counts.LOW,      name: 'LOW',      itemStyle: { color: '#4ade80' } },
        { value: counts.MEDIUM,   name: 'MEDIUM',   itemStyle: { color: '#facc15' } },
        { value: counts.HIGH,     name: 'HIGH',     itemStyle: { color: '#fb923c' } },
        { value: counts.CRITICAL, name: 'CRITICAL', itemStyle: { color: '#f87171' } },
      ],
      label: { show: false },
      emphasis: { label: { show: true, fontSize: 12, color: '#fff' } },
    }],
  }
})
</script>

<template>
  <div class="bg-card border border-border rounded-lg p-4">
    <h3 class="text-sm font-semibold text-gray-300 mb-2">Risk Distribution</h3>
    <VChart :option="option" style="height:180px" autoresize />
    <div class="flex justify-around mt-2 text-xs">
      <span class="text-green-400">LOW</span>
      <span class="text-yellow-400">MEDIUM</span>
      <span class="text-orange-400">HIGH</span>
      <span class="text-red-400">CRITICAL</span>
    </div>
  </div>
</template>
