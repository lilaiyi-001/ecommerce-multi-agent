<script setup>
import { useRoute, useRouter } from 'vue-router'
import { clearToken } from '../api/index.js'

const route = useRoute()
const router = useRouter()

const navItems = [
  { path: '/', name: 'Dashboard', icon: '📊', label: '概览' },
  { path: '/report', name: 'ReportGenerator', icon: '📋', label: '生成报告' },
]

function handleLogout() {
  clearToken()
  router.push('/login')
}
</script>

<template>
  <aside class="sidebar">
    <div class="sidebar-header">
      <h1 class="logo">电商选品</h1>
      <p class="subtitle">多智能体运营系统</p>
    </div>
    <nav class="nav-list">
      <router-link
        v-for="item in navItems"
        :key="item.path"
        :to="item.path"
        class="nav-item"
        :class="{ active: route.path === item.path }"
      >
        <span class="nav-icon">{{ item.icon }}</span>
        <span class="nav-label">{{ item.label }}</span>
      </router-link>
    </nav>
    <div class="sidebar-footer">
      <span class="user-icon">👤</span>
      <span class="user-name">admin</span>
      <button class="logout-btn" @click="handleLogout" title="退出登录">退出</button>
    </div>
  </aside>
</template>

<style scoped>
.sidebar {
  position: fixed;
  left: 0;
  top: 0;
  width: 220px;
  height: 100vh;
  background: #1a1a2e;
  color: #fff;
  display: flex;
  flex-direction: column;
  z-index: 100;
}
.sidebar-header {
  padding: 20px 16px;
  border-bottom: 1px solid rgba(255,255,255,0.1);
}
.logo {
  font-size: 18px;
  font-weight: 700;
  margin: 0;
  color: #4fc3f7;
}
.subtitle {
  font-size: 12px;
  opacity: 0.6;
  margin: 4px 0 0;
}
.nav-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px 0;
}
.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 16px;
  color: rgba(255,255,255,0.7);
  text-decoration: none;
  font-size: 14px;
  transition: all 0.2s;
}
.nav-item:hover {
  background: rgba(255,255,255,0.08);
  color: #fff;
}
.nav-item.active {
  background: rgba(79, 195, 247, 0.15);
  color: #4fc3f7;
  border-right: 3px solid #4fc3f7;
}
.nav-icon { font-size: 18px; width: 24px; text-align: center; }
.nav-label { font-size: 13px; }

.sidebar-footer {
  padding: 12px 16px;
  border-top: 1px solid rgba(255,255,255,0.1);
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
}
.user-icon { font-size: 16px; }
.user-name { color: rgba(255,255,255,0.8); flex: 1; }
.logout-btn {
  background: none;
  border: 1px solid rgba(255,255,255,0.2);
  color: rgba(255,255,255,0.6);
  padding: 4px 10px;
  border-radius: 4px;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
}
.logout-btn:hover {
  background: rgba(255,255,255,0.1);
  color: #fff;
}
</style>
