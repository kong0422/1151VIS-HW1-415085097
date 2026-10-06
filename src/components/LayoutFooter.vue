<template>
  <footer class="footer mt-auto py-2 bg-dark text-light fixed-bottom">
    <div class="container text-center">
      {{page_title}}
    </div>
  </footer>
</template>

<script>
export default {
  props: ['env', 'client_info', 'page_title'],
  data () {
    return {
    }
  },
  created () {
  },
  methods: {
  }
}
</script>

<style scoped>
</style>
