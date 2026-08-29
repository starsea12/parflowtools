<template>
  <div class="downloads-container">
    <el-card shadow="never">
      <template #header>
        <div class="downloads-header">
          <span>我的下载</span>
          <el-button type="primary" size="small" @click="loadDownloads">刷新</el-button>
        </div>
      </template>

      <el-table
        v-loading="loading"
        :data="downloads"
        style="width: 100%"
        empty-text="暂无下载记录"
      >
        <el-table-column label="下载时间" width="180" :formatter="(row) => formatLocalTime(row.created_at)" />
        <el-table-column prop="count" label="流域数量" width="100">
          <template #default="{ row }">
            <el-tag size="small" type="info">{{ row.count }} 个</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="流域编号" min-width="260">
          <template #default="{ row }">
            <span class="ids-text">{{ displayIds(row.watershed_ids) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="文件大小" width="120">
          <template #default="{ row }">
            {{ formatSize(row.file_size) }}
          </template>
        </el-table-column>
        <el-table-column label="用途" min-width="180">
          <template #default="{ row }">
            <span class="reason-text">{{ row.reason || '—' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120">
          <template #default="{ row }">
            <el-button
              type="primary"
              size="mini"
              :loading="row._downloading"
              @click="redownload(row)"
            >重新下载</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 下载用途 / 受限申请弹窗（每次下载必填用途） -->
    <DownloadDialogs
      v-model:visible="downloadGate"
      :ids="pendingIds"
      :reason="pendingReason"
      @confirm-download="(reason, institution) => doDownload(pendingIds, reason, institution)"
    />
  </div>
</template>

<script>
import axios from 'axios';
import DownloadDialogs from '@/components/DownloadDialogs.vue';
import { formatLocalTime } from '@/utils/time';

const API_BASE = ''; // 空字符串，使用相对路径

export default {
  name: 'MyDownloadsView',
  components: {
    DownloadDialogs,
  },
  data() {
    return {
      loading: false,
      downloads: [],
      downloadGate: '',   // 下载弹窗状态: ''(隐藏) | 'reason'(填写用途) | 'apply'(受限申请)
      pendingIds: [],
      pendingReason: '',
    };
  },
  mounted() {
    this.loadDownloads();
  },
  methods: {
    formatLocalTime,
    async loadDownloads() {
      this.loading = true;
      try {
        const { data } = await axios.get(`${API_BASE}/api/downloads`, { params: { limit: 100 } });
        this.downloads = data;
      } catch (error) {
        console.error('获取下载记录失败:', error);
        this.$message.error('获取下载记录失败，请稍后重试');
      } finally {
        this.loading = false;
      }
    },

    // 编号过多时只显示前几个 + 省略
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

    // 重新下载:先弹窗填写用途,确认后由 doDownload 发起(后端重新裁剪打包)
    redownload(row) {
      this.pendingIds = row.watershed_ids;
      this.pendingReason = '';
      this.downloadGate = 'reason';
    },

    // 填写用途确认后实际发起下载
    async doDownload(ids, reason, institution) {
      try {
        const response = await axios.post(
          `${API_BASE}/api/download`,
          { ids, reason, institution },
          {
            responseType: 'blob',
            timeout: 600000,
          }
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
        // 重新下载也会写一条审计记录,刷新列表
        await this.loadDownloads();
      } catch (error) {
        console.error('下载失败:', error);
        let message = '下载失败，请检查后端服务。';
        let errorType = '';
        if (error.response?.data instanceof Blob) {
          try {
            const payload = JSON.parse(await error.response.data.text());
            if (payload.error) message = payload.error;
            if (payload.error_type) errorType = payload.error_type;
          } catch (_) {
            // 非 JSON 错误响应，保留通用提示
          }
        }
        if (errorType === 'quota_exceeded' || errorType === 'level_restricted') {
          this.pendingReason = reason;
          this.downloadGate = 'apply';
        }
        this.$message.error(message);
      }
    }
  }
};
</script>

<style scoped>
.downloads-container {
  max-width: 900px;
  margin: 0 auto;
  padding: 20px;
}
.downloads-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.ids-text {
  font-family: Consolas, Monaco, monospace;
  font-size: 12px;
  color: #606266;
}
</style>
