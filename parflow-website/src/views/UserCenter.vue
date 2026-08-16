<template>
  <div class="user-center-container">
    <!-- 基本信息 -->
    <el-card shadow="never" class="info-summary-card">
      <template #header>
        <span>基本信息</span>
      </template>
      <div class="info-summary">
        <div class="summary-item">
          <span class="label">用户名</span>
          <span class="value">{{ profile.username || '—' }}</span>
        </div>
        <div class="summary-item">
          <span class="label">邮箱</span>
          <span class="value">{{ profile.email || '—' }}</span>
        </div>
        <div class="summary-item">
          <span class="label">注册时间</span>
          <span class="value">{{ profile.created_at || '—' }}</span>
        </div>
      </div>
    </el-card>

    <el-row :gutter="20" class="settings-row">
      <!-- 修改密码 -->
      <el-col :xs="24" :md="8">
        <el-card shadow="never" class="setting-card">
          <template #header>
            <span>修改密码</span>
          </template>
          <el-form
            ref="passwordFormRef"
            :model="passwordForm"
            :rules="passwordRules"
            label-width="90px"
          >
            <el-form-item label="原密码" prop="old_password">
              <el-input v-model="passwordForm.old_password" type="password" placeholder="请输入原密码" show-password />
            </el-form-item>
            <el-form-item label="新密码" prop="new_password">
              <el-input v-model="passwordForm.new_password" type="password" placeholder="8-16位，须含字母和数字" show-password />
            </el-form-item>
            <el-form-item label="确认新密码" prop="confirm_password">
              <el-input v-model="passwordForm.confirm_password" type="password" placeholder="再次输入新密码" show-password />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="passwordLoading" @click="handleChangePassword" style="width:100%;">确认修改</el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>

      <!-- 修改邮箱 -->
      <el-col :xs="24" :md="8">
        <el-card shadow="never" class="setting-card">
          <template #header>
            <span>修改邮箱</span>
          </template>
          <el-form
            ref="emailFormRef"
            :model="emailForm"
            :rules="emailRules"
            label-width="90px"
          >
            <el-form-item label="当前邮箱">
              <el-input :model-value="profile.email || '—'" disabled />
            </el-form-item>
            <el-form-item label="新邮箱" prop="email">
              <el-input v-model="emailForm.email" placeholder="请输入新邮箱" />
            </el-form-item>
            <el-form-item label="当前密码" prop="password">
              <el-input v-model="emailForm.password" type="password" placeholder="为安全起见需验证密码" show-password />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="emailLoading" @click="handleChangeEmail" style="width:100%;">确认修改</el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>

      <!-- 修改用户名 -->
      <el-col :xs="24" :md="8">
        <el-card shadow="never" class="setting-card">
          <template #header>
            <span>修改用户名</span>
          </template>
          <el-form
            ref="usernameFormRef"
            :model="usernameForm"
            :rules="usernameRules"
            label-width="90px"
          >
            <el-form-item label="当前用户名">
              <el-input :model-value="profile.username || '—'" disabled />
            </el-form-item>
            <el-form-item label="新用户名" prop="username">
              <el-input v-model="usernameForm.username" placeholder="4-16位" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="usernameLoading" @click="handleChangeUsername" style="width:100%;">确认修改</el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script>
import axios from 'axios';
import { validatePassword } from '@/utils/validate';

const API_BASE = ''; // 空字符串，使用相对路径

export default {
  name: 'UserCenterView',
  data() {
    const validateConfirmPassword = (rule, value, callback) => {
      if (this.passwordForm.new_password !== value) {
        callback(new Error('两次输入的新密码不一致'));
      } else {
        callback();
      }
    };

    return {
      profile: { username: '', email: '', created_at: '' },
      passwordForm: { old_password: '', new_password: '', confirm_password: '' },
      passwordRules: {
        old_password: [{ required: true, message: '请输入原密码', trigger: 'blur' }],
        new_password: [
          { required: true, message: '请输入新密码', trigger: 'blur' },
          { validator: validatePassword, trigger: 'blur' }
        ],
        confirm_password: [
          { required: true, message: '请再次输入新密码', trigger: 'blur' },
          { validator: validateConfirmPassword, trigger: 'blur' }
        ]
      },
      passwordLoading: false,
      emailForm: { email: '', password: '' },
      emailRules: {
        email: [
          { required: true, message: '请输入新邮箱', trigger: 'blur' },
          { type: 'email', message: '请输入正确的邮箱格式', trigger: 'blur' }
        ],
        password: [{ required: true, message: '请输入当前密码', trigger: 'blur' }]
      },
      emailLoading: false,
      usernameForm: { username: '' },
      usernameRules: {
        username: [
          { required: true, message: '请输入新用户名', trigger: 'blur' },
          { min: 4, max: 16, message: '用户名长度为4-16位', trigger: 'blur' }
        ]
      },
      usernameLoading: false,
    };
  },
  mounted() {
    this.loadProfile();
  },
  methods: {
    async loadProfile() {
      try {
        const { data } = await axios.get(`${API_BASE}/api/me`);
        this.profile = data;
        // 同步顶栏显示的用户名/邮箱(localStorage 为顶栏数据源)
        this.updateStoredUser();
      } catch (error) {
        console.error('获取用户信息失败:', error);
        this.$message.error('获取用户信息失败，请稍后重试');
      }
    },

    // 用户名/邮箱变更后写入 localStorage,顶栏、登录后各处保持一致
    updateStoredUser() {
      try {
        const stored = JSON.parse(localStorage.getItem('auth_user') || '{}');
        stored.username = this.profile.username;
        stored.email = this.profile.email;
        localStorage.setItem('auth_user', JSON.stringify(stored));
      } catch (e) {
        // 忽略解析失败,顶栏下次 /api/me 校验时会修复
      }
    },

    handleChangePassword() {
      this.$refs.passwordFormRef.validate((valid) => {
        if (!valid) return;
        this.passwordLoading = true;
        axios.put(`${API_BASE}/api/me/password`, {
          old_password: this.passwordForm.old_password,
          new_password: this.passwordForm.new_password,
        })
          .then(({ data }) => {
            this.$message.success(data.message || '密码修改成功');
            this.passwordForm = { old_password: '', new_password: '', confirm_password: '' };
            this.$refs.passwordFormRef.clearValidate();
          })
          .catch((err) => {
            this.$message.error(err.response?.data?.error || '修改失败，请稍后重试');
          })
          .finally(() => {
            this.passwordLoading = false;
          });
      });
    },

    handleChangeEmail() {
      this.$refs.emailFormRef.validate((valid) => {
        if (!valid) return;
        this.emailLoading = true;
        axios.put(`${API_BASE}/api/me/email`, {
          email: this.emailForm.email,
          password: this.emailForm.password,
        })
          .then(({ data }) => {
            this.$message.success(data.message || '邮箱修改成功');
            this.profile.email = data.email;
            this.updateStoredUser();
            this.emailForm = { email: '', password: '' };
            this.$refs.emailFormRef.clearValidate();
          })
          .catch((err) => {
            this.$message.error(err.response?.data?.error || '修改失败，请稍后重试');
          })
          .finally(() => {
            this.emailLoading = false;
          });
      });
    },

    handleChangeUsername() {
      this.$refs.usernameFormRef.validate((valid) => {
        if (!valid) return;
        this.usernameLoading = true;
        axios.put(`${API_BASE}/api/me/username`, { username: this.usernameForm.username })
          .then(({ data }) => {
            this.$message.success(data.message || '用户名修改成功');
            this.profile.username = data.username;
            this.updateStoredUser();
            this.usernameForm = { username: '' };
            this.$refs.usernameFormRef.clearValidate();
          })
          .catch((err) => {
            this.$message.error(err.response?.data?.error || '修改失败，请稍后重试');
          })
          .finally(() => {
            this.usernameLoading = false;
          });
      });
    }
  }
};
</script>

<style scoped>
.user-center-container {
  max-width: 1100px;
  margin: 0 auto;
  padding: 20px;
}
.info-summary-card {
  margin-bottom: 20px;
}
.info-summary {
  display: flex;
  flex-wrap: wrap;
  gap: 40px;
  padding: 4px 8px;
}
.summary-item {
  display: flex;
  align-items: center;
}
.summary-item .label {
  color: #909399;
  font-size: 14px;
  margin-right: 10px;
}
.summary-item .value {
  color: #303133;
  font-size: 14px;
  font-weight: 500;
}
.settings-row {
  margin: 0 !important;
}
.setting-card {
  margin-bottom: 20px;
  height: 100%;
}
</style>
