<template>
  <!-- 下载用途弹窗:每次下载前必填用途,确认后由父组件发起下载 -->
  <el-dialog
    v-model="reasonVisible"
    title="填写下载用途"
    width="500px"
    :close-on-click-modal="false"
  >
    <p class="dialog-tip">本次下载流域（{{ ids.length }} 个）：<span class="ids-text">{{ idsText }}</span></p>
    <el-input
      v-model="innerInstitution"
      maxlength="100"
      show-word-limit
      placeholder="请填写科研单位，如：XX大学、XX研究所（必填）"
      class="field-gap"
    />
    <el-input
      v-model="innerReason"
      type="textarea"
      :rows="3"
      maxlength="200"
      show-word-limit
      placeholder="请填写下载用途，如：科研分析、毕业设计、课程教学、项目开发等（必填）"
    />
    <template #footer>
      <el-button @click="close">取消</el-button>
      <el-button type="primary" @click="confirmDownload">下载</el-button>
    </template>
  </el-dialog>

  <!-- 受限申请弹窗:超限/级别受限时提交申请,审批通过后可在用户中心下载 -->
  <el-dialog
    v-model="applyVisible"
    title="提交下载申请"
    width="500px"
    :close-on-click-modal="false"
  >
    <el-alert
      type="warning"
      :closable="false"
      show-icon
      title="当前下载受到限额或流域级别限制，可提交申请说明用途，管理员审批通过后将在用户中心通知您，并在「我的申请」中提供下载。"
      class="apply-alert"
    />
    <p class="dialog-tip">申请流域（{{ ids.length }} 个）：<span class="ids-text">{{ idsText }}</span></p>
    <el-input
      v-model="innerInstitution"
      maxlength="100"
      show-word-limit
      placeholder="请填写科研单位，如：XX大学、XX研究所（必填）"
      class="field-gap"
    />
    <el-input
      v-model="innerReason"
      type="textarea"
      :rows="3"
      maxlength="200"
      show-word-limit
      placeholder="请说明申请理由/用途（必填）"
    />
    <template #footer>
      <el-button @click="close">取消</el-button>
      <el-button type="primary" :loading="applying" @click="submitApply">提交申请</el-button>
    </template>
  </el-dialog>
</template>

<script>
import axios from 'axios';

const API_BASE = ''; // 空字符串，使用相对路径

export default {
  name: 'DownloadDialogs',
  props: {
    // 当前显示的弹窗: ''(隐藏) | 'reason'(用途) | 'apply'(申请)
    visible: { type: String, default: '' },
    ids: { type: Array, default: () => [] },
    // 申请弹窗预填的理由(复用下载时填写的用途)
    reason: { type: String, default: '' },
  },
  emits: ['update:visible', 'confirm-download'],
  data() {
    return {
      innerReason: '',
      innerInstitution: '',
      applying: false,
    };
  },
  computed: {
    reasonVisible: {
      get() { return this.visible === 'reason'; },
      set(v) {
        // el-dialog 关闭动画结束后会无条件 emit update:modelValue=false(use-dialog afterLeave)。
        // 若此刻另一个弹窗已打开(visible 已切换),忽略这个噪音事件,避免误关正在显示的弹窗。
        if (!v && this.visible === 'reason') this.close();
      },
    },
    applyVisible: {
      get() { return this.visible === 'apply'; },
      set(v) {
        if (!v && this.visible === 'apply') this.close();
      },
    },
    idsText() {
      if (this.ids.length <= 6) return this.ids.join('、');
      return `${this.ids.slice(0, 6).join('、')} 等 ${this.ids.length} 个`;
    },
  },
  watch: {
    visible(v) {
      if (v === 'reason') {
        // 用途弹窗:每次清空用途;单位默认带出用户上次填写的(可修改)
        this.innerReason = '';
        this.innerInstitution = this.storedInstitution();
      } else if (v === 'apply') {
        // 申请弹窗:预填用途;单位保留刚填的值(403 从用途弹窗切来时),为空才用用户资料带出
        this.innerReason = this.reason;
        if (!this.innerInstitution) this.innerInstitution = this.storedInstitution();
      }
    },
    reason(v) {
      // 申请弹窗打开期间父组件更新预填理由时同步
      if (this.visible === 'apply') this.innerReason = v;
    },
  },
  methods: {
    close() {
      this.$emit('update:visible', '');
    },
    // 读取 localStorage.auth_user.institution(用户最近一次填写,由 /api/me 与提交成功时写入)
    storedInstitution() {
      try {
        const user = JSON.parse(localStorage.getItem('auth_user') || '{}');
        return (user && user.institution) || '';
      } catch (e) {
        return '';
      }
    },
    // 提交成功/确认下载时回写,下次弹窗自动带出
    saveInstitution(institution) {
      try {
        const stored = JSON.parse(localStorage.getItem('auth_user') || '{}');
        stored.institution = institution;
        localStorage.setItem('auth_user', JSON.stringify(stored));
      } catch (e) {
        // 忽略解析失败,下次 /api/me 校验时会修复
      }
    },
    confirmDownload() {
      const reason = this.innerReason.trim();
      if (!reason) {
        this.$message.warning('请填写下载用途');
        return;
      }
      const institution = this.innerInstitution.trim();
      if (!institution) {
        this.$message.warning('请填写科研单位');
        return;
      }
      this.saveInstitution(institution);
      this.$emit('confirm-download', reason, institution);
      // 确认后先关弹窗(下载进行中由父组件按钮 loading 体现;被限额/级别拦截会重新打开申请弹窗)
      this.close();
    },
    async submitApply() {
      const reason = this.innerReason.trim();
      if (!reason) {
        this.$message.warning('请填写申请理由');
        return;
      }
      const institution = this.innerInstitution.trim();
      if (!institution) {
        this.$message.warning('请填写科研单位');
        return;
      }
      this.applying = true;
      try {
        const { data } = await axios.post(`${API_BASE}/api/applications`, { ids: this.ids, reason, institution });
        this.saveInstitution(institution);
        this.$message.success(data.message || '申请已提交，请等待管理员审批');
        this.close();
      } catch (error) {
        this.$message.error(error.response?.data?.error || '申请提交失败，请稍后重试');
      } finally {
        this.applying = false;
      }
    },
  },
};
</script>

<style scoped>
.dialog-tip {
  margin: 0 0 10px;
  color: #606266;
  font-size: 14px;
}
.ids-text {
  font-family: Consolas, Monaco, monospace;
  font-size: 13px;
  color: #303133;
  word-break: break-all;
}
.apply-alert {
  margin-bottom: 12px;
}
.field-gap {
  margin-bottom: 10px;
}
</style>
