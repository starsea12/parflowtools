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
          <div class="forgot-row">
            <a href="#" @click.prevent="openForgotDialog">忘记密码？</a>
          </div>
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
              <el-input v-model="registerForm.password" type="password" placeholder="8-16位，须含字母和数字" show-password />
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

    <!-- 忘记密码弹窗:两步流程(验证身份获取重置码 → 凭重置码设置新密码) -->
    <el-dialog
      v-model="forgotDialogVisible"
      title="找回密码"
      width="400px"
      :close-on-click-modal="false"
      @closed="resetForgotState"
    >
      <template v-if="forgotStep === 1">
        <el-form
          ref="forgotFormRef"
          :model="forgotForm"
          :rules="forgotRules"
          label-width="80px"
        >
          <el-form-item label="用户名" prop="username">
            <el-input v-model="forgotForm.username" placeholder="请输入用户名" />
          </el-form-item>
          <el-form-item label="注册邮箱" prop="email">
            <el-input v-model="forgotForm.email" placeholder="请输入注册时填写的邮箱" />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" :loading="forgotLoading" @click="handleGetResetCode" style="width:100%;">获取重置码</el-button>
          </el-form-item>
        </el-form>
      </template>

      <template v-else>
        <el-alert type="success" :closable="false" class="reset-code-alert">
          <template #title>
            重置码：<b class="reset-code">{{ issuedCode }}</b>
            <span class="reset-code-tip">（{{ resetExpiresMinutes }} 分钟内有效）</span>
          </template>
        </el-alert>
        <div class="re-get-row">
          <a href="#" @click.prevent="forgotStep = 1">重新获取重置码</a>
        </div>
        <el-form
          ref="resetFormRef"
          :model="resetForm"
          :rules="resetRules"
          label-width="80px"
          class="reset-form"
        >
          <el-form-item label="重置码" prop="code">
            <el-input v-model="resetForm.code" placeholder="请输入重置码" />
          </el-form-item>
          <el-form-item label="新密码" prop="new_password">
            <el-input v-model="resetForm.new_password" type="password" placeholder="8-16位，须含字母和数字" show-password />
          </el-form-item>
          <el-form-item label="确认密码" prop="confirm_password">
            <el-input v-model="resetForm.confirm_password" type="password" placeholder="再次输入新密码" show-password />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" :loading="resetLoading" @click="handleResetPassword" style="width:100%;">重置密码</el-button>
          </el-form-item>
        </el-form>
      </template>
    </el-dialog>
  </div>
</template>

<script>
import axios from 'axios';
import { validatePassword } from '@/utils/validate';

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

    const validateResetConfirmPassword = (rule, value, callback) => {
      if (this.resetForm.new_password !== value) {
        callback(new Error('两次输入的新密码不一致'));
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
          { min: 4, max: 16, message: '用户名长度为4-16位', trigger: 'blur' }
        ],
        password: [
          { required: true, message: '请输入密码', trigger: 'blur' },
          { validator: validatePassword, trigger: 'blur' }
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
      // 忘记密码(重置码流程)
      forgotDialogVisible: false,
      forgotStep: 1,             // 1=验证身份获取重置码, 2=凭重置码设置新密码
      forgotLoading: false,
      resetLoading: false,
      issuedCode: '',            // 后端返回的重置码(无 SMTP,直接展示给用户)
      resetExpiresMinutes: 30,
      forgotForm: { username: '', email: '' },
      forgotRules: {
        username: [
          { required: true, message: '请输入用户名', trigger: 'blur' },
          { min: 4, max: 16, message: '用户名长度为4-16位', trigger: 'blur' }
        ],
        email: [
          { required: true, message: '请输入注册邮箱', trigger: 'blur' },
          { type: 'email', message: '请输入正确的邮箱格式', trigger: 'blur' }
        ]
      },
      resetForm: { code: '', new_password: '', confirm_password: '' },
      resetRules: {
        code: [{ required: true, message: '请输入重置码', trigger: 'blur' }],
        new_password: [
          { required: true, message: '请输入新密码', trigger: 'blur' },
          { validator: validatePassword, trigger: 'blur' }
        ],
        confirm_password: [
          { required: true, message: '请再次输入新密码', trigger: 'blur' },
          { validator: validateResetConfirmPassword, trigger: 'blur' }
        ]
      },
    };
  },
  mounted() {
    if (localStorage.getItem('auth_token')) {
      this.$router.push('/');
    }
  },
  methods: {
    handleTabClick() {
      this.$refs.loginFormRef?.clearValidate();
      this.$refs.registerFormRef?.clearValidate();
    },
    saveAuth(data) {
      localStorage.setItem('auth_token', data.token);
      localStorage.setItem('auth_user', JSON.stringify({ username: data.username, email: data.email }));
    },
    handleLogin() {
      this.$refs.loginFormRef.validate((valid) => {
        if (!valid) return;
        this.loginLoading = true;
        axios.post('/api/login', this.loginForm)
          .then(({ data }) => {
            this.saveAuth(data);
            this.$message.success(`欢迎回来，${data.username}！`);
            this.$router.push('/');
          })
          .catch((err) => {
            this.$message.error(err.response?.data?.error || '登录失败，请稍后重试');
          })
          .finally(() => {
            this.loginLoading = false;
          });
      });
    },
    handleRegister() {
      this.$refs.registerFormRef.validate((valid) => {
        if (!valid) return;
        this.registerLoading = true;
        const { username, password, email } = this.registerForm;
        axios.post('/api/register', { username, password, email })
          .then(({ data }) => {
            this.saveAuth(data);
            this.$message.success(`注册成功，欢迎 ${data.username}！`);
            this.$router.push('/');
          })
          .catch((err) => {
            this.$message.error(err.response?.data?.error || '注册失败，请稍后重试');
          })
          .finally(() => {
            this.registerLoading = false;
          });
      });
    },

    // ---------- 忘记密码 ----------
    openForgotDialog() {
      this.forgotDialogVisible = true;
      this.forgotStep = 1;
      // 预填登录框里已输入的用户名,少打一遍
      if (!this.forgotForm.username && this.loginForm.username) {
        this.forgotForm.username = this.loginForm.username;
      }
    },

    // 弹窗关闭后清空整个流程状态(下次打开是全新流程)
    resetForgotState() {
      this.forgotStep = 1;
      this.forgotForm = { username: '', email: '' };
      this.resetForm = { code: '', new_password: '', confirm_password: '' };
      this.issuedCode = '';
      this.$refs.forgotFormRef?.clearValidate();
      this.$refs.resetFormRef?.clearValidate();
    },

    // 第一步:验证用户名+注册邮箱,后端签发重置码并直接返回展示(无邮件服务)
    handleGetResetCode() {
      this.$refs.forgotFormRef.validate((valid) => {
        if (!valid) return;
        this.forgotLoading = true;
        axios.post('/api/forgot-password', this.forgotForm)
          .then(({ data }) => {
            this.issuedCode = data.code;
            this.resetExpiresMinutes = data.expires_in_minutes || 30;
            this.resetForm.code = data.code; // 重置码直接可见,自动填入省得手抄
            this.forgotStep = 2;
            this.$message.success('重置码已生成，请设置新密码');
          })
          .catch((err) => {
            this.$message.error(err.response?.data?.error || '获取重置码失败，请稍后重试');
          })
          .finally(() => {
            this.forgotLoading = false;
          });
      });
    },

    // 第二步:凭重置码设置新密码
    handleResetPassword() {
      this.$refs.resetFormRef.validate((valid) => {
        if (!valid) return;
        this.resetLoading = true;
        axios.post('/api/reset-password', {
          username: this.forgotForm.username,
          code: this.resetForm.code,
          new_password: this.resetForm.new_password,
        })
          .then(({ data }) => {
            this.$message.success(data.message || '密码重置成功，请使用新密码登录');
            // 回到登录页并预填用户名,方便直接用新密码登录
            this.loginForm.username = this.forgotForm.username;
            this.loginForm.password = '';
            this.forgotDialogVisible = false;
            this.activeTab = 'login';
          })
          .catch((err) => {
            this.$message.error(err.response?.data?.error || '重置失败，请稍后重试');
          })
          .finally(() => {
            this.resetLoading = false;
          });
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
.forgot-row {
  text-align: right;
  margin-top: -6px;
}
.forgot-row a {
  color: #909399;
  font-size: 13px;
  text-decoration: none;
}
.forgot-row a:hover {
  color: #2c6b9e;
  text-decoration: underline;
}
.reset-code-alert {
  margin-bottom: 8px;
}
.reset-code {
  font-family: Consolas, Monaco, monospace;
  font-size: 16px;
  letter-spacing: 1px;
}
.reset-code-tip {
  font-weight: normal;
  font-size: 12px;
}
.re-get-row {
  text-align: right;
  margin-bottom: 8px;
}
.re-get-row a {
  color: #2c6b9e;
  font-size: 13px;
  text-decoration: none;
}
.re-get-row a:hover {
  text-decoration: underline;
}
.reset-form {
  margin-top: 10px;
}
</style>