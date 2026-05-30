<script setup lang="ts">
const layers = [
  { type: 'input',   label: 'INPUT 30×11', color: '#00d9ff', width: 70,  height: 140 },
  { type: 'gru',     label: 'GRU 128',     color: '#3b82f6', width: 55,  height: 190 },
  { type: 'dropout', label: 'DROP 0.2',    color: '#a855f7', width: 24,  height: 160 },
  { type: 'gru',     label: 'GRU 64',      color: '#2563eb', width: 50,  height: 150 },
  { type: 'dropout', label: 'DROP 0.2',    color: '#a855f7', width: 24,  height: 130 },
  { type: 'gru',     label: 'GRU 32',      color: '#1d4ed8', width: 42,  height: 110 },
  { type: 'dropout', label: 'DROP 0.15',   color: '#9333ea', width: 22,  height: 90  },
  { type: 'dense',   label: 'DENSE 32',    color: '#f59e0b', width: 34,  height: 80  },
  { type: 'dense',   label: 'DENSE 16',    color: '#facc15', width: 28,  height: 60  },
  { type: 'output',  label: 'OUT 1',       color: '#22c55e', width: 18,  height: 40  },
]

const spacing = 92
const startX  = 40
const centerY = 180

function getX(index: number) {
  return startX + index * spacing
}
</script>

<template>
  <div class="w-full overflow-x-auto rounded-xl border border-[#1e293b] bg-[#081121] p-5">
    <svg width="1100" height="300" class="min-w-[1050px]">

      <defs>
        <filter id="glow">
          <feGaussianBlur stdDeviation="2" result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
        <marker id="arrow" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto">
          <path d="M0,0 L0,6 L9,3 z" fill="#475569" />
        </marker>
      </defs>

      <!-- CONNECTIONS -->
      <g v-for="(layer, i) in layers.slice(0, -1)" :key="'line-' + i">
        <line
          :x1="getX(i) + layer.width + 12"
          :y1="centerY"
          :x2="getX(i + 1) - 8"
          :y2="centerY"
          stroke="#475569"
          stroke-width="2"
          marker-end="url(#arrow)"
        />
      </g>

      <!-- LAYERS -->
      <g v-for="(layer, i) in layers" :key="layer.label">

        <!-- MAIN BLOCK -->
        <rect
          :x="getX(i)"
          :y="centerY - layer.height / 2"
          :width="layer.width"
          :height="layer.height"
          :fill="layer.color"
          fill-opacity="0.12"
          :stroke="layer.color"
          stroke-width="2"
          rx="6"
          filter="url(#glow)"
        />

        <!-- INTERNAL LINES -->
        <g v-if="layer.type !== 'dropout' && layer.type !== 'output'">
          <line
            v-for="n in 6"
            :key="n"
            :x1="getX(i) + 7"
            :x2="getX(i) + layer.width - 7"
            :y1="centerY - layer.height / 2 + n * (layer.height / 7)"
            :y2="centerY - layer.height / 2 + n * (layer.height / 7)"
            :stroke="layer.color"
            stroke-opacity="0.35"
          />
        </g>

        <!-- OUTPUT NODE -->
        <circle
          v-if="layer.type === 'output'"
          :cx="getX(i) + layer.width / 2"
          :cy="centerY"
          r="7"
          :fill="layer.color"
          filter="url(#glow)"
        />

        <!-- VERTICAL TEXT -->
        <g :transform="`translate(${getX(i) + layer.width / 2}, ${centerY}) rotate(-90)`">
          <text
            text-anchor="middle"
            fill="#cbd5e1"
            font-size="11"
            font-weight="700"
            letter-spacing="1"
          >
            {{ layer.label }}
          </text>
        </g>

      </g>

    </svg>
  </div>
</template>
