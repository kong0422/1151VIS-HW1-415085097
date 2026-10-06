<template>
  <div>
    <h2>Monthly Visitors - Line Chart</h2>
    <svg ref="chart"></svg>
  </div>
</template>

<script setup>
import { ref, onMounted } from "vue";
import * as d3 from "d3";

const chart = ref(null);

const data = [
  { month: "Sun", value: 60 },
  { month: "Jan", value: 30 },
  { month: "Feb", value: 45 },
  { month: "Mar", value: 38 },
  { month: "Apr", value: 65 },
  { month: "May", value: 72 },
  { month: "Jun", value: 60 }
];

onMounted(() => {

  const width = 600;
  const height = 400;

  const margin = {
    top: 20,
    right: 30,
    bottom: 50,
    left: 50
  };

  const svg = d3
    .select(chart.value)
    .attr("width", width)
    .attr("height", height);

  // X scale
  const x = d3
    .scalePoint()
    .domain(data.map(d => d.month))
    .range([margin.left, width - margin.right]);

  // Y scale
  const y = d3
    .scaleLinear()
    .domain([0, d3.max(data, d => d.value)])
    .nice()
    .range([height - margin.bottom, margin.top]);

  // Line generator
  const line = d3
    .line()
    .x(d => x(d.month))
    .y(d => y(d.value));

  // Draw line
  svg
    .append("path")
    .datum(data)
    .attr("fill", "none")
    .attr("stroke", "yellow")
    .attr("stroke-width", 6)
    .attr("d", line);

  // Draw data points
  svg
    .selectAll("circle")
    .data(data)
    .join("circle")
    .attr("cx", d => x(d.month))
    .attr("cy", d => y(d.value))
    .attr("r", 8)
    .attr("fill", "orange");

  // X Axis
  svg
    .append("g")
    .attr(
      "transform",
      `translate(0,${height - margin.bottom})`
    )
    .call(d3.axisBottom(x));

  // Y Axis
  svg
    .append("g")
    .attr(
      "transform",
      `translate(${margin.left},0)`
    )
    .call(d3.axisLeft(y));
});
</script>
