<template>
  <div ref="mapContainer" class="map-container">
    <!-- 全屏按钮（右上角） -->
    <button
      class="fullscreen-btn"
      :title="isFullscreen ? '退出全屏' : '全屏显示'"
      @click="toggleFullscreen"
    >
      <svg
        v-if="!isFullscreen"
        viewBox="0 0 24 24"
        width="18"
        height="18"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        stroke-linecap="round"
        stroke-linejoin="round"
      >
        <path d="M8 3H5a2 2 0 0 0-2 2v3" />
        <path d="M21 8V5a2 2 0 0 0-2-2h-3" />
        <path d="M3 16v3a2 2 0 0 0 2 2h3" />
        <path d="M16 21h3a2 2 0 0 0 2-2v-3" />
      </svg>
      <svg
        v-else
        viewBox="0 0 24 24"
        width="18"
        height="18"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        stroke-linecap="round"
        stroke-linejoin="round"
      >
        <path d="M8 3v3a2 2 0 0 1-2 2H3" />
        <path d="M21 8h-3a2 2 0 0 1-2-2V3" />
        <path d="M3 16h3a2 2 0 0 1 2 2v3" />
        <path d="M16 21v-3a2 2 0 0 1 2-2h3" />
      </svg>
    </button>

    <!-- 点击流域后的浮动信息卡（右下角，可关闭） -->
    <!-- 关闭只隐藏本卡片（infoVisible），不清空父组件的 currentWatershed，右侧信息栏信息保留 -->
    <div v-if="infoVisible && watershedInfo" class="watershed-info">
      <button class="info-close" title="关闭" @click="infoVisible = false">×</button>
      <h4 class="info-title">流域信息</h4>
      <p><strong>编号：</strong>{{ watershedInfo.id }}</p>
      <p><strong>级别：</strong>{{ watershedInfo.level }}级</p>
      <p><strong>所属地区：</strong>{{ watershedInfo.region || '—' }}</p>
      <p><strong>经纬度范围：</strong>{{ infoBBoxText || '—' }}</p>
      <p><strong>面积：</strong>{{ infoAreaText || '—' }}</p>
      <button
        class="info-download"
        :disabled="infoDownloadLoading"
        @click="$emit('info-download')"
      >
        {{ infoDownloadLoading ? '下载中…' : '下载数据' }}
      </button>
    </div>
  </div>
</template>

<script>
// 普通流域: 蓝色描边无填充; 高亮流域: 半透明橙色填充 + 同普通流域蓝色描边
import { formatBBox, formatArea } from '@/utils/format';

// 普通流域: 蓝色描边无填充; 高亮流域: 半透明橙色填充 + 同普通流域蓝色描边
const DEFAULT_STYLE = { color: '#2c6b9e', weight: 1.5, opacity: 0.85, fillColor: '#ffffff', fillOpacity: 0 };
const HIGHLIGHT_STYLE = { color: '#2c6b9e', weight: 1.5, opacity: 0.85, fillColor: '#e67e22', fillOpacity: 0.35 };

export default {
  name: 'MapComponent',
  props: {
    center: {
      type: Array,
      default: () => [116.40769, 39.89945],
    },
    zoom: {
      type: Number,
      default: 12,
    },
    // GeoJSON 边界数据（FeatureCollection），用于显示流域多边形
    boundaryData: {
      type: Object,
      default: null,
    },
    // 需要高亮的流域 id 列表（搜索命中）
    highlightIds: {
      type: Array,
      default: () => [],
    },
    // 点击流域后要展示的信息对象（由父组件获取详情后传入；null 表示不显示）
    watershedInfo: {
      type: Object,
      default: null,
    },
    // 信息卡"下载数据"按钮的加载状态（由父组件控制）
    infoDownloadLoading: {
      type: Boolean,
      default: false,
    },
  },
  emits: ['polygon-click', 'info-download'],
  data() {
    return {
      map: null,
      boundaryOverlays: [],    // 已添加的边界多边形（T.Polygon）
      renderTimer: null,       // 分批渲染定时器（大级别防止一次性创建数万多边形卡死）
      isFullscreen: false,     // 是否处于全屏状态
      infoVisible: false,      // 浮动信息卡显示状态（关闭只隐藏卡片, 不清空数据）
      _clickFid: null,         // 当前点击高亮的流域 id（点击高亮, 与搜索高亮相互覆盖）
      _skipNextHighlightRender: false, // 点击高亮后跳过父组件同步 highlightIds 触发的重渲染
    };
  },
  watch: {
    center: {
      handler(newCenter) {
        if (this.map && newCenter) {
          this.map.panTo(new T.LngLat(newCenter[0], newCenter[1]));
        }
      },
      deep: true,
    },
    boundaryData: {
      handler(newData) {
        if (newData && newData.features) {
          // 边界数据变化时渲染，并自动缩放视野以显示全部边界
          this.renderBoundaries(newData, true);
        } else {
          this.clearBoundaries();
        }
      },
      deep: true,
    },
    highlightIds: {
      handler() {
        // 点击流域时已就地切换过样式（_setHighlight），父组件同步 highlightIds 触发的
        // 全量重渲染会丢失点击高亮并可能卡顿 → 跳过这一次
        if (this._skipNextHighlightRender) {
          this._skipNextHighlightRender = false;
          return;
        }
        // 有边界数据时重新渲染（用新颜色标记高亮），不改变视野
        if (this.boundaryData && this.boundaryData.features) {
          this.renderBoundaries(this.boundaryData, false);
        }
      },
      deep: true,
    },
    watershedInfo: {
      handler(newInfo) {
        // 点击流域 → 父组件传入详情 → 显示浮动卡
        if (newInfo) {
          this.infoVisible = true;
        }
      },
    },
  },
  computed: {
    // 浮动信息卡的经纬度范围文本（如 "N26.12 S25.13 W114.22 E115.34"）
    infoBBoxText() {
      return this.watershedInfo ? formatBBox(this.watershedInfo.bbox) : '';
    },
    // 浮动信息卡的面积（保留两位小数）
    infoAreaText() {
      return this.watershedInfo ? formatArea(this.watershedInfo.area) : '';
    },
  },
  mounted() {
    this.initMap();
    // 监听全屏状态变化（Esc 退出全屏等），保持按钮图标同步并重算地图尺寸
    document.addEventListener('fullscreenchange', this.onFullscreenChange);
    document.addEventListener('webkitfullscreenchange', this.onFullscreenChange);
  },
  beforeUnmount() {
    document.removeEventListener('fullscreenchange', this.onFullscreenChange);
    document.removeEventListener('webkitfullscreenchange', this.onFullscreenChange);
    if (this.map) {
      try {
        if (typeof this.map.dispose === 'function') {
          this.map.dispose();
        }
      } catch (e) {
        // 忽略
      }
      this.map = null;
      this.boundaryOverlays = [];
    }
  },
  methods: {
    initMap() {
      if (!this.$refs.mapContainer || typeof T === 'undefined') {
        console.error('地图容器未找到或天地图 API 未加载');
        return;
      }
      try {
        // 1. 创建地图实例
        //    maxZoom=18（天地图瓦片最高 18 级，超过会瓦片缺失出现白屏）、
        //    minZoom=3（防止缩放过远整屏无瓦片）
        this.map = new T.Map(this.$refs.mapContainer, { maxZoom: 18, minZoom: 3 });

        // 兜底：若仍出现超限缩放，强制拉回（某些天地图版本对构造参数支持不完整）
        this.map.addEventListener('zoomend', () => {
          const z = this.map.getZoom();
          if (z > 18) this.map.setZoom(18);
          if (z < 3) this.map.setZoom(3);
        });

        // 2. 设置中心点和缩放
        const center = new T.LngLat(this.center[0], this.center[1]);
        this.map.centerAndZoom(center, this.zoom);

        // 3. 添加行政矢量底图（含道路、水系、边界等）
        const tk = '1d53336bcd00cb17850b2653b8257d7c'; // 替换为你的天地图 Key
        const vecLayer = new T.TileLayer(
          `https://t0.tianditu.gov.cn/vec_w/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=vec&STYLE=default&TILEMATRIXSET=w&FORMAT=tiles&TILEMATRIX={z}&TILEROW={y}&TILECOL={x}&tk=${tk}`
        );
        this.map.addLayer(vecLayer);

        // 4. 添加中文注记图层（显示城市名、地名、道路名称等）
        const cvaLayer = new T.TileLayer(
          `https://t0.tianditu.gov.cn/cva_w/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=cva&STYLE=default&TILEMATRIXSET=w&FORMAT=tiles&TILEMATRIX={z}&TILEROW={y}&TILECOL={x}&tk=${tk}`
        );
        this.map.addLayer(cvaLayer);

        console.log('天地图初始化成功（行政地图 + 注记）');
      } catch (error) {
        console.error('地图初始化失败:', error);
      }
    },

    // ---- 全屏 ----
    async toggleFullscreen() {
      const el = this.$refs.mapContainer;
      const doc = document;
      const isFs = doc.fullscreenElement || doc.webkitFullscreenElement;
      try {
        if (!isFs) {
          const enter = el.requestFullscreen || el.webkitRequestFullscreen;
          if (enter) {
            await enter.call(el);
          }
        } else {
          const exit = doc.exitFullscreen || doc.webkitExitFullscreen;
          if (exit) {
            await exit.call(doc);
          }
        }
      } catch (error) {
        console.error('全屏切换失败:', error);
      }
      // 全屏过渡结束后重算地图尺寸，避免瓦片错位/留白（isFullscreen 由 fullscreenchange 事件同步）
      setTimeout(() => this._forceResize(), 300);
    },

    onFullscreenChange() {
      this.isFullscreen = !!(document.fullscreenElement || document.webkitFullscreenElement);
      setTimeout(() => this._forceResize(), 100);
    },

    // 定位到指定流域：把流域置于地图中央，并按流域级别调整缩放
    focusWatershed(lng, lat, level) {
      if (!this.map || lng === undefined || lat === undefined) return;
      // 按流域级别给一个合适的缩放（级别越高流域越小，zoom 越大）
      const zoomForLevel = { 2: 6, 4: 7, 6: 8, 8: 9, 10: 10, 12: 11, 14: 12 };
      const z = zoomForLevel[level] || 10;
      // 用 centerAndZoom 一步设置中心和缩放。
      // 注意不能用 panTo + setZoom 连调: panTo 带平移动画, 会与 setZoom 相互打断, 导致没有实际移动
      this.map.centerAndZoom(new T.LngLat(lng, lat), z);
    },

    // 地图容器尺寸变化后通知地图重算（兼容不同天地图版本）
    _forceResize() {
      if (!this.map) return;
      if (typeof this.map.resize === 'function') {
        this.map.resize();
        return;
      }
      if (typeof this.map.invalidateSize === 'function') {
        this.map.invalidateSize();
        return;
      }
      if (window) window.dispatchEvent(new Event('resize'));
    },

    // ---- 兼容不同天地图版本：v2.0 用 addOverLay（L 大写），v3/v4 用 addOverlay ----
    _addOverlay(overlay) {
      const fn = this.map.addOverlay || this.map.addOverLay;
      if (typeof fn === 'function') fn.call(this.map, overlay);
    },

    _removeOverlay(overlay) {
      const fn = this.map.removeOverlay || this.map.removeOverLay;
      if (typeof fn === 'function') fn.call(this.map, overlay);
    },

    // ---- 流域边界渲染 ----
    clearBoundaries() {
      // 取消未完成的分批渲染
      if (this.renderTimer) {
        clearTimeout(this.renderTimer);
        this.renderTimer = null;
      }
      this.boundaryOverlays.forEach((p) => {
        this._removeOverlay(p);
      });
      this.boundaryOverlays = [];
    },

    renderBoundaries(geojson, fitViewport = false) {
      if (!this.map || !geojson || !geojson.features) return;

      // 清空旧边界
      this.clearBoundaries();

      const highlightSet = new Set((this.highlightIds || []).map(String));
      const features = geojson.features;

      // 先收集所有待添加的多边形，避免渲染中途被新数据打断
      const jobs = [];
      features.forEach((feature) => {
        const props = feature.properties || {};
        const fid = String(props.PFBAS_ID || props.id || '');
        const isHighlight = highlightSet.size > 0 && highlightSet.has(fid);

        // 普通流域: 只显示蓝色边界轮廓（fillOpacity 0 = 透明）
        // 搜索命中流域: 半透明橙色填充（fillOpacity 0.35, 能透出底图）+ 与普通流域相同的蓝色描边
        const style = isHighlight ? HIGHLIGHT_STYLE : DEFAULT_STYLE;

        const geom = feature.geometry;
        if (!geom) return;

        if (geom.type === 'Polygon') {
          jobs.push({ coordinates: geom.coordinates, style, props });
        } else if (geom.type === 'MultiPolygon') {
          // 每个"部分"结构和 Polygon 相同: [外环, 内环...]，直接传给 _addPolygon
          // （注意: 不能包一层 [part]，否则 _addPolygon 取 coordinates[0] 会拿到整个部分）
          // 所有部分共享同一 PFBAS_ID，点击任一 part 都发射同一 properties
          geom.coordinates.forEach((part) => jobs.push({ coordinates: part, style, props }));
        }
      });

      // 数据变化时先自动缩放视野，让全部边界可见（搜索高亮不缩放）
      if (fitViewport) {
        this.fitToBoundaries(geojson);
      }

      // 分批渲染：大级别（如 14 级 5 万多个多边形）一次性创建会卡死浏览器
      const BATCH_SIZE = 1500;
      let index = 0;
      const addNextBatch = () => {
        this.renderTimer = null;
        const end = Math.min(index + BATCH_SIZE, jobs.length);
        for (; index < end; index++) {
          this._addPolygon(jobs[index].coordinates, jobs[index].style, jobs[index].props);
        }
        if (index < jobs.length) {
          this.renderTimer = setTimeout(addNextBatch, 0);
        } else {
          console.log(`[边界] 已渲染 ${features.length} 个流域边界`);
        }
      };
      addNextBatch();
    },

    // 自动缩放视野以显示全部边界（天地图 setViewport）
    fitToBoundaries(geojson) {
      if (!this.map || !geojson || !geojson.features) return;
      const points = [];
      const walk = (coords) => {
        if (typeof coords[0] === 'number') {
          points.push(new T.LngLat(coords[0], coords[1]));
        } else {
          coords.forEach(walk);
        }
      };
      geojson.features.forEach((feature) => {
        if (feature.geometry) walk(feature.geometry.coordinates);
      });
      if (points.length > 0) {
        this.map.setViewport(points);
      }
    },

    _addPolygon(coordinates, style, properties) {
      // coordinates: Polygon 是 [[lng,lat],...][]，MultiPolygon 我们传的是 [ring]
      // 取第一个环（外环）的坐标
      const outer = coordinates[0];
      if (!outer || outer.length < 3) return;

      const points = outer.map((coord) => new T.LngLat(coord[0], coord[1]));
      const polygon = new T.Polygon(points, {
        color: style.color,
        weight: style.weight,
        opacity: style.opacity,
        fillColor: style.fillColor,
        fillOpacity: style.fillOpacity,
      });

      // 记录流域 id 与初始样式（点击高亮/恢复时用 setStyle 就地修改，避免全量重渲染）
      const fid = properties ? String(properties.PFBAS_ID || properties.id || '') : '';
      polygon._fid = fid;
      polygon._baseStyle = style;

      // 点击多边形时向父组件发射流域属性（PFBAS_ID / area）
      if (properties) {
        const self = this;
        polygon.addEventListener('click', function () {
          // 点击高亮: 把高亮样式就地切换到该流域（_setHighlight 内部会先恢复其他所有流域）
          self._setHighlight(fid);
          // 父组件随后会同步 highlightIds=[该流域] 并触发重渲染 —— 跳过这次,
          // 因为样式已经就地切换好, 避免全量重渲染丢失高亮并卡顿
          self._skipNextHighlightRender = true;
          self.$emit('polygon-click', properties);
        });
      }

      this._addOverlay(polygon);
      this.boundaryOverlays.push(polygon);
    },

    // 就地高亮指定流域（恢复其他流域为各自初始样式，再把高亮样式套到目标流域上）。
    // 只调用 setStyle，不重建多边形 → 大级别下也不会卡顿
    _setHighlight(fid) {
      this._clickFid = fid;
      this.boundaryOverlays.forEach((poly) => {
        if (poly._fid === fid) {
          if (typeof poly.setStyle === 'function') {
            poly.setStyle(HIGHLIGHT_STYLE);
          }
        } else if (poly._baseStyle && typeof poly.setStyle === 'function') {
          poly.setStyle(poly._baseStyle);
        }
      });
    },

    // 供父组件调用: 右侧栏折叠/展开后地图容器尺寸变化，通知地图重算
    handleResize() {
      this._forceResize();
    },
  },
};
</script>

<style scoped>
.map-container {
  width: 100%;
  height: 100%;
  min-height: 400px;
  position: relative;
}

/* 全屏按钮 */
.fullscreen-btn {
  position: absolute;
  top: 10px;
  right: 10px;
  z-index: 1000;
  width: 34px;
  height: 34px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #fff;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  cursor: pointer;
  color: #606266;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.15);
}
.fullscreen-btn:hover {
  color: #409eff;
  border-color: #c6e2ff;
}

/* 浮动流域信息卡（右下角） */
.watershed-info {
  position: absolute;
  right: 12px;
  bottom: 24px;
  z-index: 1000;
  width: 300px; /* 能容纳 "经纬度范围: N26.12 S25.13 W114.22 E115.34" 整行 */
  background: #fff;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.15);
  padding: 14px 16px;
  font-size: 13px;
}
.info-title {
  margin: 0 0 10px;
  font-size: 15px;
  color: #303133;
  border-bottom: 1px solid #f0f0f0;
  padding-bottom: 8px;
}
.watershed-info p {
  margin: 6px 0;
  color: #606266;
  line-height: 1.6;
}
.watershed-info strong {
  display: inline-block;
  white-space: nowrap; /* label（如"经纬度范围:"）不被折行 */
  color: #303133;
}
.info-close {
  position: absolute;
  top: 8px;
  right: 10px;
  border: none;
  background: none;
  font-size: 18px;
  line-height: 1;
  color: #909399;
  cursor: pointer;
  padding: 2px;
}
.info-close:hover {
  color: #f56c6c;
}
/* 信息卡下载按钮 */
.info-download {
  margin-top: 10px;
  width: 100%;
  padding: 7px 0;
  background: #409eff;
  color: #fff;
  border: none;
  border-radius: 4px;
  font-size: 13px;
  cursor: pointer;
}
.info-download:hover:not(:disabled) {
  background: #66b1ff;
}
.info-download:disabled {
  background: #a0cfff;
  cursor: not-allowed;
}
</style>
