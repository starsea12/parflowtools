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
          <el-button v-if="!isLoggedIn" type="primary" size="small" @click="goToLogin">
            登录/注册
          </el-button>
          <template v-else>
            <!-- 用户中心下拉: 按钮显示用户名, 功能入口(我的下载/用户中心各 tab/退出)都在菜单里 -->
            <el-dropdown trigger="click" @command="handleUserMenu">
              <el-badge :value="unreadCount" :hidden="unreadCount === 0" class="notify-badge">
                <span class="username-btn">{{ username }}<span class="caret">▾</span></span>
              </el-badge>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="downloads">我的下载</el-dropdown-item>
                  <el-dropdown-item command="profile:basic">用户中心</el-dropdown-item>
                  <el-dropdown-item command="profile:applications">我的申请</el-dropdown-item>
                  <el-dropdown-item command="profile:notify">通知</el-dropdown-item>
                  <el-dropdown-item v-if="isAdmin" command="profile:admin-users" divided>用户管理</el-dropdown-item>
                  <el-dropdown-item v-if="isAdmin" command="profile:admin-downloads">下载记录</el-dropdown-item>
                  <el-dropdown-item command="logout" divided>退出登录</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
            <el-button type="primary" size="small" @click="switchLanguage">English</el-button>
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
      username: '',
      isAdmin: false, // 是否管理员(用户中心下拉显示用户管理/下载记录入口)
      unreadCount: 0 // 未读通知数(审批结果等),用户中心角标
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
      this.refreshUnread();
    }
  },
  methods: {
    syncLoginState() {
      const token = localStorage.getItem('auth_token');
      this.isLoggedIn = !!token;
      this.username = token ? this.getStoredUsername() : '';
      this.isAdmin = token ? this.getStoredIsAdmin() : false;
    },
    getStoredUsername() {
      try {
        const user = JSON.parse(localStorage.getItem('auth_user') || '{}');
        return user.username || '';
      } catch (e) {
        return '';
      }
    },
    getStoredIsAdmin() {
      try {
        const user = JSON.parse(localStorage.getItem('auth_user') || '{}');
        return !!user.is_admin;
      } catch (e) {
        return false;
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
          this.isAdmin = !!data.is_admin;
          localStorage.setItem('auth_user', JSON.stringify({ username: data.username, email: data.email, is_admin: !!data.is_admin, institution: data.institution || '' }));
          this.refreshUnread();
        })
        .catch(() => {
          // 401 时拦截器已清除本地登录态并跳转登录页
          this.isLoggedIn = false;
          this.username = '';
          this.isAdmin = false;
        });
    },
    // 刷新未读通知数(登录后/切换页面时;用户中心内标记已读后,离开时重新拉取)
    refreshUnread() {
      if (!this.isLoggedIn) return;
      axios.get('/api/notifications')
        .then(({ data }) => { this.unreadCount = data.unread; })
        .catch(() => {});
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
    // 用户中心下拉菜单: downloads=我的下载; profile:xxx=用户中心指定 tab; logout=退出登录
    handleUserMenu(command) {
      if (command === 'logout') { this.handleLogout(); return; }
      if (command.startsWith('profile:')) {
        this.$router.push({ path: '/profile', query: { tab: command.split(':')[1] } });
        return;
      }
      if (command === 'downloads') { this.$router.push('/downloads'); }
    },
    handleLogout() {
      axios.post('/api/logout').catch(() => {});
      localStorage.removeItem('auth_token');
      localStorage.removeItem('auth_user');
      this.isLoggedIn = false;
      this.username = '';
      this.isAdmin = false;
      this.unreadCount = 0;
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
/* 用户中心下拉菜单(唯一的 el-dropdown): 菜单项文字居中 */
.el-dropdown-menu .el-dropdown-menu__item {
  justify-content: center;
  text-align: center;
  min-width: 140px;
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
/* 用户名下拉触发按钮(替代原用户中心按钮) */
.header-right .username-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 20px;
  font-weight: bold;
  color: #2c6b9e;
  background-color: #ffffff;
  border: 1px solid #d3dce6;
  border-radius: 4px;
  padding: 14px 20px;
  cursor: pointer;
  user-select: none;
  white-space: nowrap;
  line-height: 1;
}
.header-right .username-btn:hover {
  border-color: #2c6b9e;
  color: #2c6b9e;
  background-color: #f0f7ff;
}
.header-right .caret {
  font-size: 14px;
  color: #999;
}
.header-right .notify-badge {
  line-height: 1;
}
.header-right .notify-badge :deep(.el-badge__content) {
  transform: translate(50%, -50%);
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
</style>