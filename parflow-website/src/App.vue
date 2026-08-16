<template>
  <div id="app">
    <el-container>
      <el-header height="80px" class="header">
        <div class="header-left">
          <div class="logo">
            <img src="/new_logo.jpeg" alt="CONCN DataHub" style="height: 60px; vertical-align: middle;" />
          </div>
        </div>

        <div class="header-center">
          <el-menu
            :default-active="activeMenu"
            mode="horizontal"
            background-color="#ffffff"
            text-color="#333333"
            active-text-color="#2c6b9e"
            @select="handleMenuSelect"
            style="border-bottom: none;"
          >
            <el-menu-item index="/home">网站主页</el-menu-item>
            <el-sub-menu index="/data">
              <template #title>流域数据</template>
              <el-menu-item index="/data/view">流域数据</el-menu-item>
            </el-sub-menu>
            <el-menu-item index="/help">使用说明</el-menu-item>
            <el-menu-item index="/notice">公告</el-menu-item>
          </el-menu>
        </div>

        <div class="header-right">
          <el-button type="primary" size="small" @click="switchLanguage">English</el-button>
          <el-button v-if="!isLoggedIn" type="primary" size="small" @click="goToLogin">
            登录/注册
          </el-button>
          <template v-else>
            <span class="username">{{ username }}</span>
            <el-button type="primary" size="small" @click="goToUserCenter">用户中心</el-button>
            <el-button type="primary" size="small" plain class="header-small-btn" @click="goToDownloads">我的下载</el-button>
            <el-button type="danger" size="small" class="header-small-btn" @click="handleLogout">退出</el-button>
          </template>
        </div>
      </el-header>

      <el-main class="main-content">
        <router-view />
      </el-main>
    </el-container>
  </div>
</template>

<script>
import axios from 'axios';

export default {
  name: 'App',
  data() {
    return {
      activeMenu: '/data/view',
      isLoggedIn: false,
      username: ''
    };
  },
  mounted() {
    this.checkLoginStatus();
    this.activeMenu = this.$route.path;
  },
  watch: {
    '$route.path'(newPath) {
      this.activeMenu = newPath;
      this.syncLoginState();
    }
  },
  methods: {
    syncLoginState() {
      const token = localStorage.getItem('auth_token');
      this.isLoggedIn = !!token;
      this.username = token ? this.getStoredUsername() : '';
    },
    getStoredUsername() {
      try {
        const user = JSON.parse(localStorage.getItem('auth_user') || '{}');
        return user.username || '';
      } catch (e) {
        return '';
      }
    },
    // 启动时用后端校验 token 是否仍有效
    checkLoginStatus() {
      this.syncLoginState();
      if (!this.isLoggedIn) return;
      axios.get('/api/me')
        .then(({ data }) => {
          this.isLoggedIn = true;
          this.username = data.username;
          localStorage.setItem('auth_user', JSON.stringify({ username: data.username, email: data.email }));
        })
        .catch(() => {
          // 401 时拦截器已清除本地登录态并跳转登录页
          this.isLoggedIn = false;
          this.username = '';
        });
    },
    handleMenuSelect(index) {
      this.$router.push(index);
      this.activeMenu = index;
    },
    switchLanguage() {
      alert('切换语言功能待开发');
    },
    goToLogin() {
      this.$router.push('/login');
    },
    goToUserCenter() {
      this.$router.push('/profile');
    },
    goToDownloads() {
      this.$router.push('/downloads');
    },
    handleLogout() {
      axios.post('/api/logout').catch(() => {});
      localStorage.removeItem('auth_token');
      localStorage.removeItem('auth_user');
      this.isLoggedIn = false;
      this.username = '';
      this.$message.info('您已退出登录');
      this.$router.push('/login');
    }
  }
};
</script>

<style>
/* 全局样式：确保整个页面占满视口 */
html, body {
  height: 100%;
  margin: 0;
  padding: 0;
}
#app {
  height: 100%;
  font-family: 'Helvetica Neue', Arial, sans-serif;
}
.el-container {
  height: 100%;
  flex-direction: column;
}
</style>

<style scoped>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background-color: #ffffff;
  border-bottom: 1px solid #e6e6e6;
  padding: 0 0;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  flex-shrink: 0;
  width: 100%;
  height: 80px;
}
.header-left {
  display: flex;
  align-items: center;
  min-width: 160px;
  padding-left: 20px;
}
.logo {
  display: flex;
  align-items: center;
}
.header-center {
  flex: 2;
  display: flex;
  justify-content: center;
}
.header-center .el-menu {
  width: 100%;
  max-width: 800px;
  display: flex;
  justify-content: space-around;
}
.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 180px;
  justify-content: flex-end;
  padding-right: 20px;
}
.header-right .username {
  font-size: 16px;
  font-weight: 500;
  color: #333;
  margin-right: 4px;
}
.main-content {
  background-color: #f5f7fa;
  padding: 0;
  flex: 1;
  width: 100%;
  /* 关键：让 main-content 可收缩，防止溢出 */
  min-height: 0;
}

:deep(.el-menu-item),
:deep(.el-sub-menu .el-sub-menu__title) {
  font-size: 20px !important;
  font-weight: bold !important;
}
:deep(.header-right .el-button) {
  font-size: 20px !important;
  font-weight: bold !important;
  padding: 14px 28px !important;
  height: auto !important;
}
/* 我的下载/退出按钮缩小,不与用户中心等主按钮同样大小 */
:deep(.header-right .el-button.header-small-btn) {
  font-size: 14px !important;
  font-weight: normal !important;
  padding: 6px 12px !important;
}
</style>