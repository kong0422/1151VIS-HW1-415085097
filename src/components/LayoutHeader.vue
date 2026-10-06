<template>
  <header>
    <nav class="navbar navbar-expand-lg bg-body-tertiary">
      <div class="container-fluid">
        <img src="@/assets/logo.svg" width="38" height="30" class="me-3" alt="Bootstrap">
        <a class="navbar-brand" href="#">{{page_title}}</a>
        <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarSupportedContent" aria-controls="navbarSupportedContent" aria-expanded="false" aria-label="Toggle navigation">
          <span class="navbar-toggler-icon"></span>
        </button>

        <div class="collapse navbar-collapse" id="navbarSupportedContent">
          <ul class="navbar-nav mt-md-0 ms-md-auto">
            <li class="nav-item">
              <router-link :to="'/weather'" class="nav-link" :class="{ 'active': activePath == '/weather' }">
                Weather
              </router-link>
            </li>
            <li class="nav-item">
              <router-link :to="'/course_example'" class="nav-link" :class="{ 'active': activePath == '/course_example' }">
                CourseExample
              </router-link>
            </li>
          </ul>
        </div>

      </div>
    </nav>
  </header>
</template>

<script>
import { useRouter } from 'vue-router'
export default {
  name: 'LayoutHeader',
  inject: ['getMyData', 'setMyData'],
  props: ['env', 'page_title', 'client_info'],
  data () {
    return {
      activePath: this.$route.path
    }
  },
  mounted () {
  },
  methods: {
  }
}
</script>

<style scoped>
</style>
