import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/course_example',
      name: 'CourseExampleView',
      component: () => import('../views/CourseExampleView.vue')
    },
    {
      path: '/weather',
      name: 'Weather',
      alias: ['/', '/weather'],
      component: () => import('../views/WeatherView.vue')
    }
  ]
})

export default router
