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
        <el-table-column prop="created_at" label="下载时间" width="180" />
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
  </div>
</template>

<script>
import axios from 'axios';

const API_BASE = ''; // 空字符串，使用相对路径

export default {
  name: 'MyDownloadsView',
  data() {
    return {
      loading: false,
      downloads: []
    };
  },
  mounted() {
    this.loadDownloads();
  },
  methods: {
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

    // 重新下载:与 DataView 下载逻辑一致(后端重新裁剪打包)
    async redownload(row) {
      row._downloading = true;
      try {
        const response = await axios.post(
          `${API_BASE}/api/download`,
          { ids: row.watershed_ids },
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
        this.$message.error('下载失败，请检查后端服务。');
      } finally {
        row._downloading = false;
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
