<script setup lang="ts">
import { computed } from 'vue'
import { use } from 'echarts/core'
import { GaugeChart } from 'echarts/charts'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'

use([GaugeChart, CanvasRenderer])

const props = defineProps<{ risk: number; rul: number }>()

const option = computed(() => ({
  backgroundColor: 'transparent',
  series: [{
    type: 'gauge',
    startAngle: 200,
    endAngle: -20,
    min: 0,
    max: 1,
    splitNumber: 4,
    radius: '90%',
    axisLine: {
      lineStyle: {
        width: 12,
        color: [[0.3, '#4ade80'], [0.6, '#facc15'], [0.8, '#fb923c'], [1, '#f87171']],
      },
    },
    pointer: { itemStyle: { color: 'auto' } },
    axisTick: { show: false },
    splitLine: { show: false },
    axisLabel: { show: false },
    detail: {
      valueAnimation: true,
      formatter: () => `${props.rul} cy\nRUL`,
      color: '#e5e7eb',
      fontSize: 14,
      offsetCenter: [0, '60%'],
    },
    data: [{ value: props.risk }],
  }],
}))
</script>

<template>
  <VChart :option="option" style="height:200px" autoresize />
</template>
