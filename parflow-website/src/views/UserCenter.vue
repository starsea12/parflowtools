<template>
  <div class="user-center-container">
    <el-tabs v-model="activeTab" @tab-click="handleTabClick">
      <!-- 基本信息 -->
      <el-tab-pane label="基本信息" name="basic">
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
              <span class="value">{{ formatLocalTime(profile.created_at) }}</span>
            </div>
            <div class="summary-item">
              <span class="label">下载额度</span>
              <span class="value">{{ quotaText }}</span>
            </div>
            <div class="summary-item">
              <span class="label">可下载级别</span>
              <span class="value">{{ levelsText }}</span>
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
      </el-tab-pane>

      <!-- 通知 -->
      <el-tab-pane name="notify">
        <template #label>
          通知
          <el-badge :value="notify.unread" :hidden="!notify.unread" class="notify-badge" />
        </template>
        <el-card shadow="never">
          <template #header>
            <div class="pane-header">
              <span>站内通知（申请审批结果等）</span>
              <el-button size="small" @click="markNotificationsRead">全部标为已读</el-button>
            </div>
          </template>
          <div v-if="notify.items.length" class="notify-list">
            <div
              v-for="item in notify.items"
              :key="item.id"
              class="notify-item"
              :class="{ unread: !item.is_read }"
            >
              <span class="notify-dot" v-if="!item.is_read" />
              <span class="notify-content">{{ item.content }}</span>
              <span class="notify-time">{{ formatLocalTime(item.created_at) }}</span>
            </div>
          </div>
          <el-empty v-else description="暂无通知" :image-size="80" />
        </el-card>
      </el-tab-pane>

      <!-- 我的申请 -->
      <el-tab-pane label="我的申请" name="applications">
        <el-card shadow="never">
          <template #header>
            <div class="pane-header">
              <span>下载申请（下载超限或级别受限时可提交申请，审批通过后可下载）</span>
              <el-button size="small" @click="loadApplications">刷新</el-button>
            </div>
          </template>
          <el-table
            v-loading="applicationsLoading"
            :data="applications"
            style="width: 100%"
            empty-text="暂无申请记录"
          >
            <el-table-column prop="id" label="编号" width="70" />
            <el-table-column label="申请流域" min-width="240">
              <template #default="{ row }">
                <span class="mono-text">{{ displayIds(row.watershed_ids) }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="reason" label="用途/理由" min-width="180">
              <template #default="{ row }">
                <span class="reason-text">{{ row.reason || '—' }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="institution" label="科研单位" min-width="140">
              <template #default="{ row }">{{ row.institution || '—' }}</template>
            </el-table-column>
            <el-table-column label="状态" width="100">
              <template #default="{ row }">
                <el-tag size="small" :type="statusTagType(row.status)">{{ statusText(row.status) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="admin_comment" label="管理员备注" min-width="140">
              <template #default="{ row }">{{ row.admin_comment || '—' }}</template>
            </el-table-column>
            <el-table-column label="提交时间" width="160" :formatter="(row) => formatLocalTime(row.created_at)" />
            <el-table-column label="操作" width="110">
              <template #default="{ row }">
                <el-button
                  v-if="row.status === 'approved'"
                  type="primary"
                  size="mini"
                  :loading="row._downloading"
                  @click="downloadApprovedApplication(row)"
                >下载</el-button>
                <span v-else>—</span>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>

      <!-- 管理员:用户管理 -->
      <el-tab-pane v-if="profile.is_admin" label="用户管理" name="admin-users">
        <el-card shadow="never" class="default-settings-card">
          <template #header>
            <div class="pane-header">
              <span>默认下载权限（新注册用户生效）</span>
              <el-button size="small" type="primary" :loading="defaultSettingsSaving" @click="saveDefaultSettings">保存</el-button>
            </div>
          </template>
          <el-form label-width="110px" inline v-loading="defaultSettingsLoading">
            <el-form-item label="默认下载级别">
              <el-input
                v-model="defaultSettingsForm.allowed_levels"
                placeholder="如：2,4,6（2~14 的偶数，逗号分隔）"
                style="width: 240px"
              />
            </el-form-item>
            <el-form-item label="默认下载数量">
              <el-input-number
                v-model="defaultSettingsForm.download_limit"
                :min="0"
                :disabled="defaultSettingsForm.limit_unlimited"
                controls-position="right"
                style="width: 150px"
              />
              <el-checkbox v-model="defaultSettingsForm.limit_unlimited" class="inline-check">不限</el-checkbox>
            </el-form-item>
          </el-form>
          <div class="form-tip">
            级别留空或数量勾选「不限」= 新用户不受限。保存时会把仍等于旧默认值的存量普通用户一并更新为新默认，已单独设置过权限的用户不受影响。
          </div>
        </el-card>
        <el-card shadow="never">
          <template #header>
            <div class="pane-header">
              <span>用户管理（设置每个用户的下载限额与允许级别）</span>
              <el-button size="small" @click="loadAdminUsers">刷新</el-button>
            </div>
          </template>
          <el-table v-loading="adminUsersLoading" :data="adminUsers" style="width: 100%" empty-text="暂无用户">
            <el-table-column prop="id" label="ID" width="60" />
            <el-table-column prop="username" label="用户名" min-width="100" />
            <el-table-column label="角色" width="110">
              <template #default="{ row }">
                <el-tag v-if="row.is_super_admin" size="small" type="danger">最高管理员</el-tag>
                <el-tag v-else-if="row.is_admin" size="small" type="warning">管理员</el-tag>
                <el-tag v-else size="small" type="info">普通用户</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="下载限额" min-width="150">
              <template #default="{ row }">
                <span v-if="row.is_admin">不限（管理员）</span>
                <span v-else-if="row.download_limit === null">不限</span>
                <span v-else>{{ row.download_limit }} 个</span>
                <span class="used-text">（已用 {{ row.download_used }}）</span>
              </template>
            </el-table-column>
            <el-table-column label="允许级别" min-width="140">
              <template #default="{ row }">
                <span v-if="row.is_admin">全部级别（管理员）</span>
                <span v-else>{{ formatLevels(row.allowed_levels) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="注册时间" width="160" :formatter="(row) => formatLocalTime(row.created_at)" />
            <el-table-column label="操作" width="90">
              <template #default="{ row }">
                <el-button type="primary" size="mini" @click="openUserEdit(row)">设置</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>

      <!-- 管理员:下载记录 -->
      <el-tab-pane v-if="profile.is_admin" label="下载记录" name="admin-downloads">
        <el-card shadow="never">
          <template #header>
            <div class="pane-header">
              <span>全部下载记录（含用途）</span>
              <el-button size="small" @click="loadAdminDownloads(1)">刷新</el-button>
            </div>
          </template>
          <el-table v-loading="adminDownloadsLoading" :data="adminDownloads" style="width: 100%" empty-text="暂无下载记录">
            <el-table-column label="下载时间" width="160" :formatter="(row) => formatLocalTime(row.created_at)" />
            <el-table-column prop="username" label="用户" width="110" />
            <el-table-column label="流域编号" min-width="220">
              <template #default="{ row }">
                <span class="mono-text">{{ displayIds(row.watershed_ids) }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="count" label="数量" width="70">
              <template #default="{ row }">
                <el-tag size="small" type="info">{{ row.count }} 个</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="大小" width="100">
              <template #default="{ row }">{{ formatSize(row.file_size) }}</template>
            </el-table-column>
            <el-table-column prop="reason" label="用途" min-width="180">
              <template #default="{ row }">
                <span class="reason-text">{{ row.reason || '—' }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="institution" label="科研单位" min-width="140">
              <template #default="{ row }">{{ row.institution || '—' }}</template>
            </el-table-column>
          </el-table>
          <el-pagination
            class="pager"
            background
            layout="total, prev, pager, next"
            :total="adminDownloadsTotal"
            :page-size="50"
            :current-page.sync="adminDownloadsPage"
            @current-change="loadAdminDownloads"
          />
        </el-card>
      </el-tab-pane>

      <!-- 管理员:申请审批 -->
      <el-tab-pane v-if="profile.is_admin" label="申请审批" name="admin-apps">
        <el-card shadow="never">
          <template #header>
            <div class="pane-header">
              <span>下载申请审批</span>
              <el-button size="small" @click="loadAdminApps">刷新</el-button>
            </div>
          </template>
          <el-table v-loading="adminAppsLoading" :data="adminApps" style="width: 100%" empty-text="暂无申请">
            <el-table-column prop="id" label="编号" width="70" />
            <el-table-column prop="username" label="用户" width="110" />
            <el-table-column label="申请流域" min-width="220">
              <template #default="{ row }">
                <span class="mono-text">{{ displayIds(row.watershed_ids) }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="reason" label="用途/理由" min-width="180">
              <template #default="{ row }">
                <span class="reason-text">{{ row.reason || '—' }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="institution" label="科研单位" min-width="140">
              <template #default="{ row }">{{ row.institution || '—' }}</template>
            </el-table-column>
            <el-table-column label="状态" width="90">
              <template #default="{ row }">
                <el-tag size="small" :type="statusTagType(row.status)">{{ statusText(row.status) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="提交时间" width="160" :formatter="(row) => formatLocalTime(row.created_at)" />
            <el-table-column label="操作" width="140">
              <template #default="{ row }">
                <template v-if="row.status === 'pending'">
                  <el-button type="success" size="mini" @click="openReview(row, 'approved')">通过</el-button>
                  <el-button type="danger" size="mini" @click="openReview(row, 'rejected')">拒绝</el-button>
                </template>
                <span v-else>—</span>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>
    </el-tabs>

    <!-- 管理员:设置用户限额/级别弹窗 -->
    <el-dialog
      v-model="userEditVisible"
      title="设置用户下载权限"
      width="480px"
      :close-on-click-modal="false"
    >
      <el-form label-width="100px">
        <el-form-item label="用户名">
          <b>{{ userEditForm.username }}</b>
        </el-form-item>
        <el-form-item label="下载限额">
          <el-input-number
            v-model="userEditForm.download_limit"
            :min="0"
            :disabled="userEditForm.limit_unlimited"
            controls-position="right"
          />
          <el-checkbox v-model="userEditForm.limit_unlimited" class="inline-check">不限</el-checkbox>
          <div class="form-tip">不限 = 可下载任意数量流域；0 = 禁止下载</div>
        </el-form-item>
        <el-form-item label="允许级别">
          <el-input
            v-model="userEditForm.allowed_levels"
            placeholder="如：2,4,6（2~14 的偶数，逗号分隔）"
          />
          <div class="form-tip">留空或填写“不限” = 不限级别</div>
        </el-form-item>
        <el-form-item label="管理员" v-if="profile.is_super_admin">
          <el-switch
            v-model="userEditForm.is_admin"
            :disabled="userEditForm.id === profile.id || userEditForm.is_super_admin"
          />
          <span class="form-tip" v-if="userEditForm.id === profile.id">不能修改自己的管理员状态</span>
          <span class="form-tip" v-else-if="userEditForm.is_super_admin">最高管理员不可取消</span>
        </el-form-item>
        <el-form-item v-else label="管理员">
          <span class="form-tip">仅最高管理员可设置或取消管理员</span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="userEditVisible = false">取消</el-button>
        <el-button type="primary" :loading="userEditSaving" @click="saveAdminUser">保存</el-button>
      </template>
    </el-dialog>

    <!-- 管理员:审批弹窗 -->
    <el-dialog
      v-model="reviewVisible"
      :title="reviewAction === 'approved' ? '通过申请' : '拒绝申请'"
      width="480px"
      :close-on-click-modal="false"
    >
      <div class="review-info">
        <p><b>申请编号：</b>#{{ reviewApp.id }}</p>
        <p><b>申请用户：</b>{{ reviewApp.username }}</p>
        <p><b>申请流域：</b><span class="mono-text">{{ displayIds(reviewApp.watershed_ids) }}</span></p>
        <p><b>科研单位：</b>{{ reviewApp.institution || '—' }}</p>
        <p><b>用途/理由：</b>{{ reviewApp.reason || '—' }}</p>
      </div>
      <el-input
        v-model="reviewComment"
        type="textarea"
        :rows="3"
        maxlength="200"
        show-word-limit
        :placeholder="reviewAction === 'approved' ? '审批备注（选填，如放行原因）' : '拒绝原因（选填，将通知给用户）'"
      />
      <template #footer>
        <el-button @click="reviewVisible = false">取消</el-button>
        <el-button
          :type="reviewAction === 'approved' ? 'success' : 'danger'"
          :loading="reviewSaving"
          @click="confirmReview"
        >{{ reviewAction === 'approved' ? '确认通过' : '确认拒绝' }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script>
import axios from 'axios';
import { validatePassword } from '@/utils/validate';
import { formatLocalTime } from '@/utils/time';

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
      activeTab: 'basic',
      profile: { username: '', email: '', created_at: '', is_admin: false, is_super_admin: false, download_limit: 1, allowed_levels: '2', download_used: 0 },
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
      // 通知
      notify: { unread: 0, items: [] },
      // 我的申请
      applications: [],
      applicationsLoading: false,
      // 管理员:用户管理
      adminUsers: [],
      adminUsersLoading: false,
      userEditVisible: false,
      userEditSaving: false,
      userEditForm: { id: null, username: '', download_limit: 1, limit_unlimited: false, allowed_levels: '', is_admin: false, is_super_admin: false },
      // 管理员:默认下载权限(新注册用户)
      defaultSettingsForm: { allowed_levels: '', download_limit: 0, limit_unlimited: false },
      defaultSettingsLoading: false,
      defaultSettingsSaving: false,
      // 管理员:下载记录
      adminDownloads: [],
      adminDownloadsLoading: false,
      adminDownloadsTotal: 0,
      adminDownloadsPage: 1,
      // 管理员:申请审批
      adminApps: [],
      adminAppsLoading: false,
      reviewVisible: false,
      reviewSaving: false,
      reviewAction: 'approved',
      reviewApp: { id: null, username: '', watershed_ids: [], reason: '', institution: '' },
      reviewComment: '',
    };
  },
  computed: {
    quotaText() {
      // 管理员默认不受限
      if (this.profile.is_admin) return '不限（管理员）';
      const limit = this.profile.download_limit;
      const used = this.profile.download_used ?? 0;
      return limit === null || limit === undefined ? `已用 ${used} 个 / 不限` : `已用 ${used} / ${limit} 个`;
    },
    levelsText() {
      // 管理员默认不受限
      if (this.profile.is_admin) return '全部级别（管理员）';
      return this.formatLevels(this.profile.allowed_levels);
    },
  },
  mounted() {
    // 顶栏用户中心下拉菜单可通过 ?tab=xxx 直接定位到对应功能页
    const t = this.$route.query.tab;
    if (t) this.activeTab = t;
    this.loadProfile();
    this.loadNotifications(false);
  },
  methods: {
    formatLocalTime,
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

    // 用户名/邮箱/管理员标记变更后写入 localStorage,顶栏、登录后各处保持一致
    updateStoredUser() {
      try {
        const stored = JSON.parse(localStorage.getItem('auth_user') || '{}');
        stored.username = this.profile.username;
        stored.email = this.profile.email;
        stored.is_admin = !!this.profile.is_admin;
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
    },

    // ---------- 通知 ----------
    async loadNotifications(markRead) {
      try {
        const { data } = await axios.get(`${API_BASE}/api/notifications`);
        this.notify = data;
        if (markRead && data.unread > 0) {
          await this.markNotificationsRead();
        }
      } catch (error) {
        console.error('获取通知失败:', error);
      }
    },
    async markNotificationsRead() {
      try {
        await axios.post(`${API_BASE}/api/notifications/read`);
        this.notify.unread = 0;
        this.notify.items.forEach((n) => { n.is_read = true; });
      } catch (error) {
        console.error('标记已读失败:', error);
      }
    },

    // ---------- 我的申请 ----------
    async loadApplications() {
      this.applicationsLoading = true;
      try {
        const { data } = await axios.get(`${API_BASE}/api/applications/mine`);
        this.applications = data;
      } catch (error) {
        console.error('获取申请列表失败:', error);
        this.$message.error('获取申请列表失败，请稍后重试');
      } finally {
        this.applicationsLoading = false;
      }
    },

    // 已批准申请:放行下载(一次性,application_id 标记已用)
    async downloadApprovedApplication(app) {
      app._downloading = true;
      try {
        const response = await axios.post(
          `${API_BASE}/api/download`,
          // 单位优先带申请快照(老申请为 '' 时后端走用户资料兜底链)
          { ids: app.watershed_ids, reason: app.reason, application_id: app.id, institution: app.institution || '' },
          { responseType: 'blob', timeout: 600000 }
        );
        const contentDisposition = response.headers['content-disposition'];
        let filename = 'watershed_data.zip';
        if (contentDisposition) {
          const match = contentDisposition.match(/filename="?([^"]+)"?/);
          if (match) filename = match[1];
        }
        const blob = new Blob([response.data]);
        const url = window.URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        window.URL.revokeObjectURL(url);
        this.$message.success('下载已开始');
        // 放行后申请标记为已用,刷新状态
        await this.loadApplications();
      } catch (error) {
        console.error('下载失败:', error);
        let message = '下载失败，请检查后端服务。';
        if (error.response?.data instanceof Blob) {
          try {
            const payload = JSON.parse(await error.response.data.text());
            if (payload.error) message = payload.error;
          } catch (_) {
            // 非 JSON 错误响应，保留通用提示
          }
        }
        this.$message.error(message);
      } finally {
        app._downloading = false;
      }
    },

    // ---------- 管理员:默认下载权限 ----------
    async loadDefaultSettings() {
      this.defaultSettingsLoading = true;
      try {
        const { data } = await axios.get(`${API_BASE}/api/admin/default-settings`);
        this.defaultSettingsForm.allowed_levels = data.allowed_levels || '';
        this.defaultSettingsForm.limit_unlimited = !data.download_limit;
        this.defaultSettingsForm.download_limit = data.download_limit ? Number(data.download_limit) : 0;
      } catch (error) {
        console.error('获取默认权限设置失败:', error);
        this.$message.error('获取默认权限设置失败');
      } finally {
        this.defaultSettingsLoading = false;
      }
    },
    async saveDefaultSettings() {
      this.defaultSettingsSaving = true;
      try {
        const payload = {
          allowed_levels: this.defaultSettingsForm.allowed_levels.trim(),
          download_limit: this.defaultSettingsForm.limit_unlimited ? '' : this.defaultSettingsForm.download_limit,
        };
        const { data } = await axios.post(`${API_BASE}/api/admin/default-settings`, payload);
        let msg = '默认权限已保存';
        if (data.updated_levels || data.updated_limits) {
          msg += `，已同步 ${data.updated_levels} 名用户的级别、${data.updated_limits} 名用户的数量`;
        }
        this.$message.success(msg);
        await this.loadAdminUsers(); // 批量更新可能影响用户列表显示
      } catch (error) {
        this.$message.error(error.response?.data?.error || '保存失败，请稍后重试');
      } finally {
        this.defaultSettingsSaving = false;
      }
    },

    // ---------- 管理员:用户管理 ----------
    async loadAdminUsers() {
      this.adminUsersLoading = true;
      try {
        const { data } = await axios.get(`${API_BASE}/api/admin/users`);
        this.adminUsers = data;
      } catch (error) {
        console.error('获取用户列表失败:', error);
        this.$message.error('获取用户列表失败，请稍后重试');
      } finally {
        this.adminUsersLoading = false;
      }
    },
    openUserEdit(row) {
      // 管理员默认不受限:无论字段值如何,弹窗按"不限"展示
      const unlimited = row.is_admin || row.download_limit === null;
      this.userEditForm = {
        id: row.id,
        username: row.username,
        download_limit: unlimited ? 1 : row.download_limit,
        limit_unlimited: unlimited,
        allowed_levels: row.allowed_levels || '',
        is_admin: !!row.is_admin,
        is_super_admin: !!row.is_super_admin,
      };
      this.userEditVisible = true;
    },
    async saveAdminUser() {
      const form = this.userEditForm;
      let allowedLevels = (form.allowed_levels || '').trim();
      if (allowedLevels && allowedLevels !== '不限') {
        const parts = allowedLevels.split(',');
        if (!parts.every((p) => /^\d+$/.test(p.trim()) && [2, 4, 6, 8, 10, 12, 14].includes(Number(p.trim())))) {
          this.$message.warning('允许级别需为 2~14 的偶数级别，多个用逗号分隔');
          return;
        }
        allowedLevels = parts.map((p) => p.trim()).join(',');
      }
      this.userEditSaving = true;
      try {
        await axios.put(`${API_BASE}/api/admin/users/${form.id}`, {
          download_limit: form.limit_unlimited ? null : form.download_limit,
          allowed_levels: allowedLevels,
          is_admin: form.is_admin,
        });
        this.$message.success('设置已保存');
        this.userEditVisible = false;
        await this.loadAdminUsers();
      } catch (error) {
        this.$message.error(error.response?.data?.error || '保存失败，请稍后重试');
      } finally {
        this.userEditSaving = false;
      }
    },

    // ---------- 管理员:下载记录 ----------
    async loadAdminDownloads(page) {
      this.adminDownloadsLoading = true;
      try {
        const { data } = await axios.get(`${API_BASE}/api/admin/downloads`, {
          params: { page: page || this.adminDownloadsPage, page_size: 50 },
        });
        this.adminDownloads = data.items;
        this.adminDownloadsTotal = data.total;
        this.adminDownloadsPage = data.page;
      } catch (error) {
        console.error('获取下载记录失败:', error);
        this.$message.error('获取下载记录失败，请稍后重试');
      } finally {
        this.adminDownloadsLoading = false;
      }
    },

    // ---------- 管理员:申请审批 ----------
    async loadAdminApps() {
      this.adminAppsLoading = true;
      try {
        const { data } = await axios.get(`${API_BASE}/api/admin/applications`);
        this.adminApps = data;
      } catch (error) {
        console.error('获取申请列表失败:', error);
        this.$message.error('获取申请列表失败，请稍后重试');
      } finally {
        this.adminAppsLoading = false;
      }
    },
    openReview(row, action) {
      this.reviewApp = row;
      this.reviewAction = action;
      this.reviewComment = '';
      this.reviewVisible = true;
    },
    async confirmReview() {
      this.reviewSaving = true;
      try {
        const url = this.reviewAction === 'approved'
          ? `${API_BASE}/api/admin/applications/${this.reviewApp.id}/approve`
          : `${API_BASE}/api/admin/applications/${this.reviewApp.id}/reject`;
        await axios.post(url, { comment: this.reviewComment.trim() });
        this.$message.success(this.reviewAction === 'approved' ? '已通过该申请' : '已拒绝该申请');
        this.reviewVisible = false;
        await this.loadAdminApps();
      } catch (error) {
        this.$message.error(error.response?.data?.error || '操作失败，请稍后重试');
      } finally {
        this.reviewSaving = false;
      }
    },

    // ---------- 通用 ----------
    handleTabClick(tab) {
      const name = tab.paneName;
      if (name === 'notify') {
        this.loadNotifications(true); // 打开通知页即标为已读
      } else if (name === 'applications') {
        this.loadApplications();
      } else if (name === 'admin-users') {
        this.loadAdminUsers();
        this.loadDefaultSettings();
      } else if (name === 'admin-downloads') {
        this.loadAdminDownloads(1);
      } else if (name === 'admin-apps') {
        this.loadAdminApps();
      }
    },

    displayIds(ids) {
      if (!ids || !ids.length) return '—';
      if (ids.length <= 3) return ids.join('、');
      return `${ids.slice(0, 3).join('、')} 等 ${ids.length} 个`;
    },
    formatSize(bytes) {
      if (!bytes && bytes !== 0) return '—';
      if (bytes < 1024) return `${bytes} B`;
      if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
      return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
    },
    formatLevels(levels) {
      if (!levels) return '不限';
      return levels.split(',').map((l) => `${l}级`).join('、');
    },
    statusText(status) {
      return { pending: '待审批', approved: '已通过', rejected: '未通过', used: '已下载' }[status] || status;
    },
    statusTagType(status) {
      return { pending: 'warning', approved: 'success', rejected: 'danger', used: 'info' }[status] || 'info';
    },
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
.default-settings-card {
  margin-bottom: 12px;
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
.pane-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.notify-badge {
  margin-left: 6px;
}
.notify-list {
  max-height: 480px;
  overflow-y: auto;
}
.notify-item {
  display: flex;
  align-items: baseline;
  padding: 10px 8px;
  border-bottom: 1px solid #f0f0f0;
}
.notify-item.unread {
  background-color: #f5f9ff;
}
.notify-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background-color: #f56c6c;
  flex-shrink: 0;
  margin-right: 8px;
  align-self: center;
}
.notify-content {
  flex: 1;
  color: #303133;
  font-size: 14px;
}
.notify-time {
  color: #909399;
  font-size: 12px;
  margin-left: 16px;
  flex-shrink: 0;
}
.mono-text {
  font-family: Consolas, Monaco, monospace;
  font-size: 12px;
  color: #606266;
}
.reason-text {
  color: #303133;
  font-size: 13px;
}
.used-text {
  color: #909399;
  font-size: 12px;
}
.pager {
  margin-top: 14px;
  justify-content: flex-end;
}
.inline-check {
  margin-left: 10px;
}
.form-tip {
  color: #909399;
  font-size: 12px;
  line-height: 1.6;
}
.review-info p {
  margin: 4px 0;
  color: #606266;
  font-size: 14px;
}
</style>
