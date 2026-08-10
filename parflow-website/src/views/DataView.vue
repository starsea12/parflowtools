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

    <!-- 主体区域：左侧地图 + 右侧流域信息（可折叠，折叠后地图占满，信息栏缩成悬浮按钮） -->
    <el-row :gutter="0" class="main-row">
      <el-col
        :xs="24"
        :sm="infoPanelVisible ? 16 : 24"
        :md="infoPanelVisible ? 16 : 24"
        :lg="infoPanelVisible ? 16 : 24"
        class="map-col"
      >
        <el-card class="map-card" shadow="never">
          <template #header>
            <span>流域分布地图</span>
          </template>
          <MapComponent
            ref="mapComponent"
            :center="mapCenter"
            :boundary-data="boundaryData"
            :highlight-ids="highlightIds"
            :watershed-info="currentWatershed"
            :info-download-loading="downloading"
            @polygon-click="onPolygonClick"
            @info-download="downloadCurrentWatershed"
          />
        </el-card>
      </el-col>
      <el-col v-if="infoPanelVisible" :xs="24" :sm="8" :md="8" :lg="8" class="info-col">
        <el-card class="info-card" shadow="never">
          <template #header>
            <div class="info-card-header">
              <span>流域信息</span>
              <el-button
                class="info-collapse-btn"
                type="primary"
                size="mini"
                title="收起信息栏"
                @click="infoPanelVisible = false"
              >收起</el-button>
            </div>
          </template>
          <div v-if="currentWatershed" class="info-content">
            <p><strong>编号：</strong>{{ currentWatershed.id }}</p>
            <p><strong>级别：</strong>{{ currentWatershed.level }}级</p>
            <p><strong>所属地区：</strong>{{ currentWatershed.region }}</p>
            <p><strong>经纬度范围：</strong>{{ bboxText || '—' }}</p>
            <p><strong>面积：</strong>{{ areaText || '—' }}</p>
          </div>
          <div v-else class="info-placeholder">
            <span style="color: #bbb;">请搜索或点击地图上的流域查看详情</span>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 信息栏折叠后的恢复按钮（悬浮在地图右下角，展开信息栏） -->
    <button
      v-if="!infoPanelVisible"
      class="info-restore-btn"
      @click="infoPanelVisible = true"
    >流域信息 ▸</button>
  </div>
</template>

<script>
import axios from 'axios';
import MapComponent from '@/components/MapComponent.vue';
import { formatBBox, formatArea } from '@/utils/format';

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
      // 流域边界
      boundaryData: null,      // 当前显示的全量边界 GeoJSON
      boundaryLevel: null,     // 当前加载的边界级别
      highlightIds: [],        // 搜索命中的流域 id（用于高亮）
      pendingFocus: null,      // 搜索后待定位的流域 { lng, lat, level }（等边界加载完成后执行）
      infoPanelVisible: true,  // 右侧流域信息栏是否展开（折叠后地图占满，显示恢复按钮）
      bboxMap: {},             // 流域 id → 包围盒 {minLng,minLat,maxLng,maxLat}（从已加载边界 GeoJSON 建立）
    };
  },
  mounted() {
    // 默认显示第 2 级流域边界（触发 watcher → loadBoundaries(2)）
    // 不做自动搜索: 不产生高亮 → 所有级别默认都是蓝色，点击"搜索"后才橙色
    if (!this.searchForm.level) {
      this.searchForm.level = 2;
    }
  },
  computed: {
    // 当前流域的经纬度范围文本（如 "N26.12 S25.13 W114.22 E115.34"）
    bboxText() {
      return this.currentWatershed ? formatBBox(this.currentWatershed.bbox) : '';
    },
    // 当前流域面积（保留两位小数，如 "1234.56"）
    areaText() {
      return this.currentWatershed ? formatArea(this.currentWatershed.area) : '';
    },
  },
  watch: {
    'searchForm.level'(newLevel, oldLevel) {
      // 级别变化时加载对应边界
      if (newLevel !== oldLevel) {
        this.loadBoundaries(newLevel);
      }
    },
    // 信息栏折叠/展开改变列宽后，地图容器尺寸变化 → 等布局完成再通知地图重算，避免瓦片错位/留白
    infoPanelVisible() {
      this.$nextTick(() => {
        setTimeout(() => {
          if (this.$refs.mapComponent) {
            this.$refs.mapComponent.handleResize();
          }
        }, 300);
      });
    },
  },
  methods: {
    async handleSearch() {
      this.loading = true;
      try {
        const keyword = (this.searchForm.keyword || '').trim();
        const region = this.searchForm.region || '';
        // 没有任何搜索条件（空搜索会命中全部 7 万流域 → 全量高亮 + 跳级别）:
        // 拦截并保持当前视图, 不搜索、不高亮、不跳转
        if (!keyword && !region) {
          this.tableData = [];
          this.currentWatershed = null;
          this.highlightIds = [];
          this.$message.info('请输入流域编号/名称, 或选择所属地区后再搜索');
          return;
        }
        // 注意: 不传 level 过滤 —— 搜索框级别仅用于控制地图显示的边界级别,
        // 搜索结果命中后会自动切换到该流域的级别（见 focusOnSearchResult）。
        // 若带 level 过滤, 搜索与当前级别不同的流域会被后端直接过滤掉, 搜不到。
        const params = {
          keyword,
          region,
        };
        const response = await axios.get(`${API_BASE}/api/watersheds`, { params });
        this.tableData = response.data;
        this.currentWatershed = this.tableData.length > 0 ? this._attachBBox(this.tableData[0]) : null;
        // 更新搜索命中高亮
        this.updateHighlightIds();
        // 如果已加载边界但搜索结果为空，保留当前边界显示
        if (this.tableData.length === 0 && this.boundaryData) {
          this.highlightIds = [];
        }
        // 搜索到流域：切换到该流域的级别，并把流域移到地图中央
        this.focusOnSearchResult();
      } catch (error) {
        console.error('搜索失败:', error);
        alert('搜索失败，请检查后端服务是否运行');
      } finally {
        this.loading = false;
      }
    },

    resetSearch() {
      // 重置: 清空搜索条件与结果, 边界随 level=null 由 watcher 清空(loadBoundaries(null) 会清高亮)
      this.searchForm.keyword = '';
      this.searchForm.region = '';
      this.searchForm.level = null;
      this.tableData = [];
      this.currentWatershed = null;
    },

    async handleDownload() {
      if (this.tableData.length === 0) {
        alert('没有可下载的数据，请先搜索。');
        return;
      }
      await this.downloadByIds(this.tableData.map((row) => row.id));
    },

    // 地图信息卡"下载数据"：直接下载当前点击的流域
    async downloadCurrentWatershed() {
      if (!this.currentWatershed || !this.currentWatershed.id) {
        alert('请先点击地图上的流域。');
        return;
      }
      await this.downloadByIds([this.currentWatershed.id]);
    },

    // 按 id 列表下载数据（打包 zip 并触发浏览器保存）
    async downloadByIds(ids) {
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

    // ---- 流域边界加载 ----
    async loadBoundaries(level) {
      if (!level) {
        this.boundaryData = null;
        this.boundaryLevel = null;
        this.highlightIds = [];
        return;
      }

      // 所有级别均全量加载（10/12/14 级已由后端简化；前端分批渲染防卡顿）
      this.boundaryData = null;
      this.boundaryLevel = level;
      try {
        const response = await axios.get(`${API_BASE}/api/boundaries`, {
          params: { level },
          timeout: 120000,
        });
        this.boundaryData = response.data;
        // 建立 "流域 id → 包围盒" 索引，供信息栏显示经纬度范围
        this.bboxMap = this._buildBBoxMap(response.data);
      } catch (error) {
        console.error('加载边界失败:', error);
        this.$message.error('加载流域边界失败，请检查后端服务');
        this.boundaryData = null;
      }
      // 边界就绪后执行搜索跳转的待定定位（放在边界加载完成后，避免被自动缩放视野覆盖）
      this._flushPendingFocus();
    },

    // 从边界 GeoJSON 建立 "流域 id → 包围盒" 索引（坐标顺序 [lng, lat]）
    _buildBBoxMap(geojson) {
      const map = {};
      if (!geojson || !geojson.features) return map;
      geojson.features.forEach((feature) => {
        const props = feature.properties || {};
        const fid = String(props.PFBAS_ID || props.id || '');
        if (!fid || !feature.geometry) return;
        let minLng = Infinity;
        let minLat = Infinity;
        let maxLng = -Infinity;
        let maxLat = -Infinity;
        const walk = (coords) => {
          if (typeof coords[0] === 'number') {
            if (coords[0] < minLng) minLng = coords[0];
            if (coords[1] < minLat) minLat = coords[1];
            if (coords[0] > maxLng) maxLng = coords[0];
            if (coords[1] > maxLat) maxLat = coords[1];
          } else {
            coords.forEach(walk);
          }
        };
        walk(feature.geometry.coordinates);
        if (minLng !== Infinity) {
          map[fid] = { minLng, minLat, maxLng, maxLat };
        }
      });
      return map;
    },

    // 给流域数据附加包围盒（范围），来自当前已加载边界的 bboxMap；
    // 搜索/点击两个入口统一走这里，保证信息栏和浮动卡都能显示范围
    _attachBBox(w) {
      if (!w || !w.id) return w;
      return { ...w, bbox: this.bboxMap[String(w.id)] || null };
    },

    // 搜索到流域后：切换边界级别并定位到该流域（地图中央）
    focusOnSearchResult() {
      const target = this.currentWatershed;
      if (!target || !target.lng || !target.lat) return;
      if (target.level && this.searchForm.level !== target.level) {
        // 级别不同：记录待定位，切换级别会触发 loadBoundaries，加载完成后自动定位
        this.pendingFocus = { lng: target.lng, lat: target.lat, level: target.level };
        this.searchForm.level = target.level;
      } else if (this.boundaryLevel !== target.level) {
        // 级别相同但该级别边界还没加载过：直接加载后再定位
        this.pendingFocus = { lng: target.lng, lat: target.lat, level: target.level };
        this.loadBoundaries(target.level);
      } else {
        // 边界已就绪：直接定位
        this._focusWatershed(target);
      }
    },

    // 执行待定的流域定位
    _flushPendingFocus() {
      if (!this.pendingFocus) return;
      const { lng, lat, level } = this.pendingFocus;
      this.pendingFocus = null;
      this.$nextTick(() => this._focusWatershed({ lng, lat, level }));
    },

    _focusWatershed(w) {
      if (this.$refs.mapComponent && w.lng !== undefined && w.lat !== undefined) {
        this.$refs.mapComponent.focusWatershed(w.lng, w.lat, w.level);
      }
    },

    // 高亮搜索命中的流域
    updateHighlightIds() {
      this.highlightIds = this.tableData.map((row) => row.id);
    },

    // 地图上点击流域多边形 → 获取该流域详情并显示在右侧信息栏
    async onPolygonClick(properties) {
      const id = properties.PFBAS_ID || properties.id;
      if (!id) {
        console.warn('点击的流域缺少 PFBAS_ID');
        return;
      }
      // 点击高亮切换: 高亮对象从"搜索命中"切换为"被点击流域"
      // （MapComponent 已就地切换样式并跳过本次重渲染，这里只同步状态，保证后续搜索/重渲染正确）
      this.highlightIds = [String(id)];
      // 点击流域时自动展开信息栏（若之前被收起）
      this.infoPanelVisible = true;
      try {
        const response = await axios.get(`${API_BASE}/api/watersheds/${id}`);
        this.currentWatershed = this._attachBBox(response.data);
      } catch (error) {
        console.error('获取流域详情失败:', error);
        if (error.response && error.response.status === 404) {
          this.$message.warning(`未找到流域 ${id} 的信息`);
        } else {
          this.$message.error('获取流域信息失败，请检查网络连接');
        }
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
/* 统一两个卡片 header 的高度与内边距并垂直居中，保证标题线（header 下边框）水平对齐 */
.map-card :deep(.el-card__header),
.info-card :deep(.el-card__header) {
  display: flex;
  align-items: center;
  height: 52px;
  padding: 0 20px;
  box-sizing: border-box;
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
  width: 90px; /* 容纳最长的 label "经纬度范围:"（6 字符 ≈ 84px）不折行 */
  white-space: nowrap;
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
/* 信息栏 header: 收起按钮推至整个屏幕最右侧 */
.info-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex: 1; /* 占满 header 整行, 否则 space-between 只在内容宽度内生效, 右侧留大片空白 */
}
/* 覆盖统一 header 的右内边距: 与登录页注册按钮右缘对齐
   （登录框 .login-box 右内边距 35px, 注册按钮 width:100% 距屏幕右缘即 35px） */
.info-card :deep(.el-card__header) {
  padding-right: 35px;
}
.info-collapse-btn {
  /* 实心蓝底白字（type="primary" 默认样式, 与登录按钮一致）;
     字号比 mini 默认放大半号（12px → 14px）;
     padding 相应收窄, 保证按钮整体大小不变（与缩小后尺寸接近） */
  margin: 0;
  padding: 2px 8px;
  font-size: 14px;
  flex-shrink: 0;
}
/* 信息栏折叠后的悬浮恢复按钮（覆盖在地图右下角） */
.info-restore-btn {
  position: fixed;
  right: 24px;
  bottom: 32px;
  z-index: 2000;
  padding: 8px 14px;
  background: #fff;
  color: #409eff;
  border: 1px solid #c6e2ff;
  border-radius: 18px;
  font-size: 13px;
  cursor: pointer;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
}
.info-restore-btn:hover {
  background: #ecf5ff;
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