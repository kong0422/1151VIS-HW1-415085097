<template>
  <LayoutHeader
    :env="env" :page_title="page_title"
    :client="client_info"
  />

  <div class="container">
    <div class="text-center mt-5">
      <BarChart />
      <hr>
      <LineChart />
      <hr>
      <ScatterPlot />
    </div>
  </div>
    

  <LayoutFooter
    :env="env"
    :client="client_info"
  />
</template>

<script setup>
import '../assets/weather.css';
import LayoutHeader from '@/components/LayoutHeader.vue';
import LayoutFooter from '@/components/LayoutFooter.vue';

import BarChart from '@/components/BarChart.vue';
import LineChart from '@/components/LineChart.vue';
import ScatterPlot from '@/components/ScatterPlot.vue';

import { ref, onMounted, watch } from 'vue';
import * as d3 from 'd3';
</script>

<script>

export default {
  inject: ['getMyData', 'setMyData'],
  props: ['env', 'page_title', 'client_info', 'API_KEY', 'API_URL'],
  data() {
    return {
      isLoading: ref(true),
      errMsg: ref(''),
      obsTime: ref(''),
      weatherData: ref([]),
      h1: ref('111'),
      h2: ref('2222'),
    }
  },

  onMounted() {
  },

  methods() {
  }
}
</script>

<style scoped>
</style>
