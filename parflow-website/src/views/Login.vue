<template>
  <div class="login-container">
    <div class="login-box">
      <div class="login-header">
        <img src="/new_logo.jpeg" alt="CONCN DataHub" class="logo-img" />
      </div>

      <el-tabs v-model="activeTab" @tab-click="handleTabClick">
        <el-tab-pane label="登录" name="login">
          <el-form
            ref="loginFormRef"
            :model="loginForm"
            :rules="loginRules"
            label-width="80px"
            @keyup.enter="handleLogin"
          >
            <el-form-item label="用户名" prop="username">
              <el-input v-model="loginForm.username" placeholder="请输入用户名" />
            </el-form-item>
            <el-form-item label="密码" prop="password">
              <el-input v-model="loginForm.password" type="password" placeholder="请输入密码" show-password />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="handleLogin" :loading="loginLoading" style="width:100%;">登录</el-button>
            </el-form-item>
          </el-form>
        </el-tab-pane>

        <el-tab-pane label="注册" name="register">
          <el-form
            ref="registerFormRef"
            :model="registerForm"
            :rules="registerRules"
            label-width="80px"
            @keyup.enter="handleRegister"
          >
            <el-form-item label="用户名" prop="username">
              <el-input v-model="registerForm.username" placeholder="请输入用户名（4-16位）" />
            </el-form-item>
            <el-form-item label="密码" prop="password">
              <el-input v-model="registerForm.password" type="password" placeholder="请输入密码（至少6位）" show-password />
            </el-form-item>
            <el-form-item label="确认密码" prop="confirmPassword">
              <el-input v-model="registerForm.confirmPassword" type="password" placeholder="请再次输入密码" show-password />
            </el-form-item>
            <el-form-item label="邮箱" prop="email">
              <el-input v-model="registerForm.email" placeholder="请输入邮箱（必填）" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="handleRegister" :loading="registerLoading" style="width:100%;">注册</el-button>
            </el-form-item>
          </el-form>
        </el-tab-pane>
      </el-tabs>

      <div class="login-footer">
        <span v-if="activeTab === 'login'">还没有账号？<a href="#" @click.prevent="activeTab='register'">立即注册</a></span>
        <span v-else>已有账号？<a href="#" @click.prevent="activeTab='login'">去登录</a></span>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'LoginView',
  data() {
    const validateConfirmPassword = (rule, value, callback) => {
      if (this.registerForm.password !== value) {
        callback(new Error('两次输入的密码不一致'));
      } else {
        callback();
      }
    };
    const validateUsernameExists = (rule, value, callback) => {
      const existing = JSON.parse(localStorage.getItem('existingUsers') || '[]');
      if (value && existing.includes(value)) {
        callback(new Error('该用户名已被占用，请更换'));
      } else {
        callback();
      }
    };

    return {
      activeTab: 'login',
      loginForm: { username: '', password: '' },
      loginRules: {
        username: [
          { required: true, message: '请输入用户名', trigger: 'blur' },
          { min: 4, max: 16, message: '用户名长度为4-16位', trigger: 'blur' }
        ],
        password: [
          { required: true, message: '请输入密码', trigger: 'blur' },
          { min: 6, message: '密码长度至少6位', trigger: 'blur' }
        ]
      },
      loginLoading: false,
      registerForm: { username: '', password: '', confirmPassword: '', email: '' },
      registerRules: {
        username: [
          { required: true, message: '请输入用户名', trigger: 'blur' },
          { min: 4, max: 16, message: '用户名长度为4-16位', trigger: 'blur' },
          { validator: validateUsernameExists, trigger: 'blur' }
        ],
        password: [
          { required: true, message: '请输入密码', trigger: 'blur' },
          { min: 6, message: '密码长度至少6位', trigger: 'blur' }
        ],
        confirmPassword: [
          { required: true, message: '请再次输入密码', trigger: 'blur' },
          { validator: validateConfirmPassword, trigger: 'blur' }
        ],
        email: [
          { required: true, message: '请输入邮箱', trigger: 'blur' },
          { type: 'email', message: '请输入正确的邮箱格式', trigger: 'blur' }
        ]
      },
      registerLoading: false,
    };
  },
  mounted() {
    if (localStorage.getItem('user')) {
      this.$router.push('/');
    }
    if (!localStorage.getItem('existingUsers')) {
      localStorage.setItem('existingUsers', JSON.stringify(['admin', 'testuser']));
    }
  },
  methods: {
    handleTabClick() {
      this.$refs.loginFormRef?.clearValidate();
      this.$refs.registerFormRef?.clearValidate();
    },
    // 登录：无延迟，立即执行
    handleLogin() {
      this.$refs.loginFormRef.validate((valid) => {
        if (!valid) return;
        this.loginLoading = true;
        const { username, password } = this.loginForm;
        const existing = JSON.parse(localStorage.getItem('existingUsers') || '[]');
        if (existing.includes(username) && password === '123456') {
          localStorage.setItem('user', JSON.stringify({ username }));
          this.$message.success(`欢迎回来，${username}！`);
          this.$router.push('/');
          // 刷新以更新主布局的用户状态（若使用 Vuex/Pinia 可避免）
          setTimeout(() => location.reload(), 100);
        } else {
          this.$message.error('用户名或密码错误');
        }
        this.loginLoading = false;
      });
    },
    // 注册：无延迟，立即执行
    handleRegister() {
      this.$refs.registerFormRef.validate((valid) => {
        if (!valid) return;
        this.registerLoading = true;
        const { username, password, email } = this.registerForm;
        const existing = JSON.parse(localStorage.getItem('existingUsers') || '[]');
        existing.push(username);
        localStorage.setItem('existingUsers', JSON.stringify(existing));
        localStorage.setItem('user', JSON.stringify({ username, email }));
        this.$message.success(`注册成功，欢迎 ${username}！`);
        this.$router.push('/');
        setTimeout(() => location.reload(), 100);
        this.registerLoading = false;
      });
    }
  }
};
</script>

<style scoped>
.login-container {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  background: #f0f2f5;
  padding: 0;
}
.login-box {
  width: 420px;
  background: #fff;
  border-radius: 8px;
  padding: 40px 35px 30px;
  box-shadow: 0 4px 12px rgba(0,0,0,0.1);
}
.login-header {
  text-align: center;
  margin-bottom: 30px;
}
.login-header .logo-img {
  height: 60px;
  vertical-align: middle;
}
.login-footer {
  text-align: center;
  margin-top: 20px;
  font-size: 14px;
  color: #909399;
}
.login-footer a {
  color: #2c6b9e;
  text-decoration: none;
}
.login-footer a:hover {
  text-decoration: underline;
}
</style>