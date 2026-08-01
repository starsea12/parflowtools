<template>
  <div id="data-view">
    <!-- 搜索区域 -->
    <el-card class="search-card" shadow="never">
      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="流域编号/名称">
          <el-input
            v-model="searchForm.keyword"
            placeholder="请输入编号或名称"
            clearable
            style="width: 220px;"
          />
        </el-form-item>
        <el-form-item label="所属地区">
          <el-select
            v-model="searchForm.region"
            placeholder="请选择地区"
            clearable
            style="width: 160px;"
          >
            <el-option label="长江流域" value="长江流域" />
            <el-option label="黄河流域" value="黄河流域" />
            <el-option label="淮河流域" value="淮河流域" />
            <el-option label="海河流域" value="海河流域" />
          </el-select>
        </el-form-item>
        <el-form-item label="流域级别">
          <el-select
            v-model="searchForm.level"
            placeholder="请选择级别"
            clearable
            style="width: 140px;"
          >
            <el-option
              v-for="num in levelOptions"
              :key="num"
              :label="num + '级'"
              :value="num"
            />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSearch" :loading="loading">搜索</el-button>
          <el-button @click="resetSearch">重置</el-button>
          <el-button type="primary" @click="handleDownload" :loading="downloading">下载数据</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 主体区域：左侧地图 + 右侧流域信息 -->
    <el-row :gutter="0" class="main-row">
      <el-col :xs="24" :sm="16" :md="16" :lg="16" class="map-col">
        <el-card class="map-card" shadow="never">
          <template #header>
            <span>流域分布地图</span>
          </template>
          <MapComponent
            ref="mapComponent"
            :center="mapCenter"
            :markers="mapMarkers"
            @marker-click="onMarkerClick"
          />
        </el-card>
      </el-col>
      <el-col :xs="24" :sm="8" :md="8" :lg="8" class="info-col">
        <el-card class="info-card" shadow="never">
          <template #header>
            <span>流域信息</span>
          </template>
          <div v-if="currentWatershed" class="info-content">
            <p><strong>编号：</strong>{{ currentWatershed.id }}</p>
            <p><strong>级别：</strong>{{ currentWatershed.level }}级</p>
            <p><strong>所属地区：</strong>{{ currentWatershed.region }}</p>
            <p><strong>经度：</strong>{{ currentWatershed.lng || '—' }}</p>
            <p><strong>纬度：</strong>{{ currentWatershed.lat || '—' }}</p>
            <p><strong>面积：</strong>{{ currentWatershed.area ? currentWatershed.area + ' km²' : '—' }}</p>
          </div>
          <div v-else class="info-placeholder">
            <span style="color: #bbb;">请搜索或点击地图上的流域查看详情</span>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script>
import axios from 'axios';
import MapComponent from '@/components/MapComponent.vue';

const API_BASE = ''; // 空字符串，使用相对路径

export default {
  name: 'DataView',
  components: {
    MapComponent,
  },
  data() {
    return {
      searchForm: {
        keyword: '',
        region: '',
        level: null,
      },
      levelOptions: (() => {
        const arr = [];
        for (let i = 2; i <= 14; i += 2) arr.push(i);
        return arr;
      })(),
      tableData: [],
      currentWatershed: null,
      loading: false,
      downloading: false,
      mapCenter: [116.40769, 39.89945], // 默认中心（首次加载使用，搜索后不再更新）
      mapMarkers: [],
    };
  },
  mounted() {
    this.handleSearch();
  },
  methods: {
    async handleSearch() {
      this.loading = true;
      try {
        const params = {
          keyword: this.searchForm.keyword || '',
          region: this.searchForm.region || '',
          level: this.searchForm.level || '',
        };
        const response = await axios.get(`${API_BASE}/api/watersheds`, { params });
        this.tableData = response.data;
        this.currentWatershed = this.tableData.length > 0 ? this.tableData[0] : null;
        // 更新地图标记
        this.updateMapMarkers();
        // 【取消刷新】不再更新地图中心，地图保持在当前视口
        // 注释掉以下代码：
        // if (this.currentWatershed && this.currentWatershed.lng && this.currentWatershed.lat) {
        //   this.mapCenter = [this.currentWatershed.lng, this.currentWatershed.lat];
        // }
      } catch (error) {
        console.error('搜索失败:', error);
        alert('搜索失败，请检查后端服务是否运行');
      } finally {
        this.loading = false;
      }
    },

    resetSearch() {
      this.searchForm.keyword = '';
      this.searchForm.region = '';
      this.searchForm.level = null;
      this.handleSearch();
    },

    async handleDownload() {
      if (this.tableData.length === 0) {
        alert('没有可下载的数据，请先搜索。');
        return;
      }
      const ids = this.tableData.map((row) => row.id);
      console.log('[前端] 发送的 ids:', ids);
      this.downloading = true;
      try {
        const response = await axios.post(
          `${API_BASE}/api/download`,
          { ids },
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
      } catch (error) {
        console.error('下载失败:', error);
        alert('下载失败，请检查后端服务。');
      } finally {
        this.downloading = false;
      }
    },

    updateMapMarkers() {
      this.mapMarkers = this.tableData
        .filter((item) => item.lng && item.lat)
        .map((item) => ({
          lng: item.lng,
          lat: item.lat,
          id: item.id,
          name: item.name,
          region: item.region,
        }));
    },

    onMarkerClick(markerData) {
      const found = this.tableData.find((item) => item.id === markerData.id);
      if (found) {
        this.currentWatershed = found;
      }
    },
  },
};
</script>

<style scoped>
#data-view {
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: 0;
  font-family: 'Helvetica Neue', Arial, sans-serif;
  background-color: #f5f7fa;
}
.search-card {
  margin-bottom: 16px;
  flex-shrink: 0;
  border-radius: 0;
}
.search-form {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  padding: 0 10px;
}
.main-row {
  flex: 1;
  margin: 0 !important;
  width: 100%;
  min-height: 0;
}
.map-col,
.info-col {
  display: flex;
  flex-direction: column;
}
.map-card {
  height: 100%;
  border-radius: 0;
  display: flex;
  flex-direction: column;
}
.map-card :deep(.el-card__body) {
  flex: 1;
  padding: 0;
  display: flex;
  flex-direction: column;
}
.map-card :deep(.map-container) {
  flex: 1;
  width: 100%;
  min-height: 300px;
  background-color: #f5f7fa;
}
.info-card {
  height: 100%;
  border-radius: 0;
  display: flex;
  flex-direction: column;
}
.info-card :deep(.el-card__body) {
  flex: 1;
  padding: 0;
  display: flex;
  flex-direction: column;
}
.info-content {
  flex: 1;
  padding: 15px;
  overflow-y: auto;
}
.info-content p {
  margin: 8px 0;
  font-size: 14px;
  line-height: 1.8;
  border-bottom: 1px solid #f0f0f0;
  padding-bottom: 6px;
}
.info-content strong {
  display: inline-block;
  width: 70px;
  color: #606266;
}
.info-placeholder {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #bbb;
  font-size: 16px;
}
@media (max-width: 768px) {
  .map-card :deep(.map-container) {
    min-height: 200px;
  }
  .info-placeholder {
    min-height: 150px;
  }
  .search-form {
    padding: 0 5px;
  }
  .search-form .el-form-item {
    margin-bottom: 5px;
  }
}
</style>