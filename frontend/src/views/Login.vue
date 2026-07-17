<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import { setToken } from '../api/index.js'

const router = useRouter()
const username = ref('admin')
const password = ref('admin123')
const loading = ref(false)
const error = ref('')

async function handleLogin() {
  if (!username.value || !password.value) {
    error.value = '请输入用户名和密码'
    return
  }
  loading.value = true
  error.value = ''
  try {
    const resp = await axios.post('/api/v1/auth/login', {
      username: username.value,
      password: password.value,
    })
    if (resp.data.access_token) {
      setToken(resp.data.access_token)
      router.push('/')
    } else {
      error.value = '登录失败：未获取到 token'
    }
  } catch (e) {
    if (e.response && e.response.status === 401) {
      error.value = '用户名或密码错误'
    } else {
      error.value = '登录失败：' + (e.message || '网络错误')
    }
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-page">
    <div class="login-card">
      <h1 class="login-title">电商选品运营系统</h1>
      <p class="login-subtitle">多智能体协作平台</p>
      <form @submit.prevent="handleLogin" class="login-form">
        <div class="form-group">
          <label for="username">用户名</label>
          <input
            id="username"
            v-model="username"
            type="text"
            placeholder="请输入用户名"
            autocomplete="username"
          />
        </div>
        <div class="form-group">
          <label for="password">密码</label>
          <input
            id="password"
            v-model="password"
            type="password"
            placeholder="请输入密码"
            autocomplete="current-password"
          />
        </div>
        <div v-if="error" class="login-error">{{ error }}</div>
        <button type="submit" class="login-btn" :disabled="loading">
          {{ loading ? '登录中...' : '登 录' }}
        </button>
      </form>
    </div>
  </div>
</template>

<style scoped>
.login-page {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
}
.login-card {
  background: #fff;
  border-radius: 12px;
  padding: 40px;
  width: 380px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
}
.login-title {
  font-size: 22px;
  font-weight: 700;
  color: #1a1a2e;
  text-align: center;
  margin: 0 0 4px;
}
.login-subtitle {
  font-size: 13px;
  color: #888;
  text-align: center;
  margin: 0 0 28px;
}
.form-group {
  margin-bottom: 16px;
}
.form-group label {
  display: block;
  font-size: 13px;
  font-weight: 500;
  color: #555;
  margin-bottom: 6px;
}
.form-group input {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid #ddd;
  border-radius: 6px;
  font-size: 14px;
  box-sizing: border-box;
  transition: border-color 0.2s;
}
.form-group input:focus {
  outline: none;
  border-color: #4fc3f7;
}
.login-error {
  background: #fff0f0;
  color: #d32f2f;
  padding: 8px 12px;
  border-radius: 6px;
  font-size: 13px;
  margin-bottom: 12px;
}
.login-btn {
  width: 100%;
  padding: 12px;
  background: #1a1a2e;
  color: #fff;
  border: none;
  border-radius: 6px;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.2s;
}
.login-btn:hover {
  background: #16213e;
}
.login-btn:disabled {
  background: #999;
  cursor: not-allowed;
}
</style>
