<script setup lang="ts">
import { computed } from 'vue'
import { use } from 'echarts/core'
import { BarChart } from 'echarts/charts'
import { TooltipComponent, GridComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'
import { useEngineStore } from '../../stores/engineStore'

use([BarChart, TooltipComponent, GridComponent, CanvasRenderer])

const store = useEngineStore()

const option = computed(() => {
  const preds = [...store.sortedPredictions].slice(0, 15)
  return {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis', formatter: (p: any) => `${p[0].name}<br/>RUL: ${p[0].value} cycles` },
    grid: { left: 60, right: 10, top: 10, bottom: 40 },
    xAxis: {
      type: 'category',
      data: preds.map(p => p.engine_id.replace('ENG-', '')),
      axisLabel: { color: '#6b7280', fontSize: 10 },
      axisLine: { lineStyle: { color: '#1f2937' } },
    },
    yAxis: {
      type: 'value',
      max: 125,
      axisLabel: { color: '#6b7280', fontSize: 10 },
      splitLine: { lineStyle: { color: '#1f2937' } },
    },
    series: [{
      type: 'bar',
      data: preds.map(p => ({
        value: p.remaining_cycles,
        itemStyle: {
          color: p.risk_level === 'CRITICAL' ? '#f87171'
               : p.risk_level === 'HIGH'     ? '#fb923c'
               : p.risk_level === 'MEDIUM'   ? '#facc15'
               : '#4ade80',
        },
      })),
      barMaxWidth: 20,
    }],
  }
})
</script>

<template>
  <div class="bg-card border border-border rounded-lg p-4">
    <h3 class="text-sm font-semibold text-gray-300 mb-2">RUL by Engine (top 15 at-risk)</h3>
    <VChart :option="option" style="height:200px" autoresize />
  </div>
</template>
