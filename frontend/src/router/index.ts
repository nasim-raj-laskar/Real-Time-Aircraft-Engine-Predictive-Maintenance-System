import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/',           name: 'fleet',    component: () => import('../pages/FleetPage.vue') },
    { path: '/engine/:id', name: 'engine',   component: () => import('../pages/EnginePage.vue') },
    { path: '/pipeline',   name: 'pipeline', component: () => import('../pages/PipelinePage.vue') },
    { path: '/mlops',      name: 'mlops',    component: () => import('../pages/MLOpsPage.vue') },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

router.onError((err) => {
  console.error('[router error]', err)
})

export default router
