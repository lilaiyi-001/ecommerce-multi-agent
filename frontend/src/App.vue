<script setup>
import { useRoute } from 'vue-router'
import NavBar from './components/NavBar.vue'

const route = useRoute()
</script>

<template>
  <div v-if="route.path === '/login'" class="login-layout">
    <router-view />
  </div>
  <div v-else class="app-container">
    <NavBar />
    <main class="main-content">
      <router-view />
    </main>
  </div>
</template>

<style scoped>
.app-container {
  display: flex;
  min-height: 100vh;
}
.login-layout {
  min-height: 100vh;
}
.main-content {
  flex: 1;
  margin-left: 220px;
  padding: 24px;
  background: #f5f6fa;
  min-height: 100vh;
}
</style>
