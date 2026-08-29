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

    <!-- 天地图 API 加载失败提示层(覆盖地图区域, 可点击重试) -->
    <div v-if="mapLoadFailed" class="map-load-error">
      <div class="map-load-error-box">
        <p>地图服务加载失败,请检查网络后重试</p>
        <button @click="retryMap">重新加载</button>
      </div>
    </div>

    <!-- 比例尺（左下角，随缩放与中心纬度更新） -->
    <div v-if="scaleText" class="scale-bar" :title="'比例尺：' + scaleText">
      <span class="scale-line" :style="{ width: scaleWidth + 'px' }"></span>
      <span class="scale-label">{{ scaleText }}</span>
    </div>

    <!-- 鼠标经纬度（右下角，随鼠标移动更新；E/W 东经西经、N/S 北纬南纬） -->
    <div class="mouse-coords">
      <span>经度：{{ lngText }}</span>
      <span>纬度：{{ latText }}</span>
    </div>

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

// 天地图浏览器端 Key(官网申请, 动态加载与瓦片请求共用)
const TIANDITU_TK = '1d53336bcd00cb17850b2653b8257d7c';
// 天地图 API 动态加载地址: https 优先(未来 HTTPS 部署无混合内容问题), http 兜底
const TIANDITU_API_HTTPS = `https://api.tianditu.gov.cn/api?v=4.0&tk=${TIANDITU_TK}`;
const TIANDITU_API_HTTP = `http://api.tianditu.gov.cn/api?v=4.0&tk=${TIANDITU_TK}`;
// 页面级单例: 一次页面生命周期只注入一次脚本(失败后重置, 供"重新加载"按钮再次尝试)
let _apiLoadPromise = null;

// 普通流域: 蓝色描边无填充; 高亮流域: 半透明橙色填充 + 同普通流域蓝色描边
const DEFAULT_STYLE = { color: '#2c6b9e', weight: 1.5, opacity: 0.85, fillColor: '#ffffff', fillOpacity: 0 };
const HIGHLIGHT_STYLE = { color: '#2c6b9e', weight: 1.5, opacity: 0.85, fillColor: '#e67e22', fillOpacity: 0.35 };
// 硬停边界: 视口边缘纬度最远到 ±68°(北极圈/南极圈约 ±66.56°, 圈外一点), 不允许滑进极地区域。
// 经度不设限 —— 世界图横向可环绕, 没有空白。中心纬度上限 = 反解(edgeY - 视口半高投影), 见 _centerLimits
const VIEW_EDGE_LAT = 68;

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
      mapLoadFailed: false,    // 天地图 API 加载/地图初始化失败(显示提示层, 可重试)
      boundaryOverlays: [],    // 已添加的边界多边形（T.Polygon）
      renderTimer: null,       // 分批渲染定时器（大级别防止一次性创建数万多边形卡死）
      isFullscreen: false,     // 是否处于全屏状态
      infoVisible: false,      // 浮动信息卡显示状态（关闭只隐藏卡片, 不清空数据）
      _clickFid: null,         // 当前点击高亮的流域 id（点击高亮, 与搜索高亮相互覆盖）
      _skipNextHighlightRender: false, // 点击高亮后跳过父组件同步 highlightIds 触发的重渲染
      _dragging: false,        // 引擎是否正在拖动(由 dragstart/dragend/moveend 事件维护)
      _dragLocked: false,      // 南北极硬停: 拖动越界已冻结(松手时恢复拖动并回界)
      _pendingClampLat: null,  // 冻结时的回界目标纬度
      mouseLng: null,          // 鼠标所在经度（右下角显示）
      mouseLat: null,          // 鼠标所在纬度
      scaleText: '',           // 比例尺文本（如 "500 km" / "5 km"）
      scaleWidth: 0,           // 比例尺线宽（px）
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
    // 鼠标经纬度文本（字母区分方向: E/W 东经西经, N/S 北纬南纬, 与"经纬度范围"方位格式一致）
    lngText() {
      if (this.mouseLng === null) return '—';
      return `${this.mouseLng >= 0 ? 'E' : 'W'}${Math.abs(this.mouseLng).toFixed(5)}`;
    },
    latText() {
      if (this.mouseLat === null) return '—';
      return `${this.mouseLat >= 0 ? 'N' : 'S'}${Math.abs(this.mouseLat).toFixed(5)}`;
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
    if (this.$refs.mapContainer) {
      this.$refs.mapContainer.removeEventListener('mousemove', this._onMouseMove);
    }
    document.removeEventListener('mouseup', this._onPointerUp);
    document.removeEventListener('touchend', this._onPointerUp);
    document.removeEventListener('pointerup', this._onPointerUp);
    document.removeEventListener('pointercancel', this._onPointerUp);
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
      if (!this.$refs.mapContainer) {
        console.error('地图容器未找到');
        return;
      }
      this.mapLoadFailed = false;
      // 天地图 API 改为动态加载: 页面首屏不再被第三方同步脚本阻塞;
      // 加载失败(用户网络不通/被拦截)时显示可见提示层并可重试, 而不是只有控制台报错
      this._ensureTiandituApi()
        .then(() => this._createMap())
        .catch(() => {
          console.error('天地图 API 加载失败');
          this.mapLoadFailed = true;
        });
    },

    // 提示层"重新加载"按钮: 重新走一遍 API 加载 + 地图初始化
    retryMap() {
      this.mapLoadFailed = false;
      this.initMap();
    },

    // 确保天地图 API 已加载: 已加载直接通过; 否则动态注入 script(页面级单例, 失败后重置)
    _ensureTiandituApi() {
      if (typeof T !== 'undefined') return Promise.resolve();
      if (_apiLoadPromise) return _apiLoadPromise;
      _apiLoadPromise = this._loadTiandituScript(0).finally(() => {
        _apiLoadPromise = null;
      });
      return _apiLoadPromise;
    },

    // 动态加载天地图脚本: attempt 0 = https, 1 = http 兜底(部分网络/拦截场景只通其一); 各 15s 超时
    _loadTiandituScript(attempt) {
      const url = attempt === 0 ? TIANDITU_API_HTTPS : TIANDITU_API_HTTP;
      return new Promise((resolve, reject) => {
        const script = document.createElement('script');
        let settled = false;
        let timer = null;
        const finish = (err) => {
          if (settled) return;
          settled = true;
          clearTimeout(timer);
          script.onload = null;
          script.onerror = null;
          if (!err && typeof T !== 'undefined') {
            resolve();
          } else if (attempt < 1) {
            this._loadTiandituScript(attempt + 1).then(resolve, reject);
          } else {
            reject(err || new Error('天地图 API 未就绪'));
          }
        };
        timer = setTimeout(() => finish(new Error('天地图 API 加载超时')), 15000);
        script.onload = () => finish();
        script.onerror = () => finish(new Error('天地图 API 加载失败'));
        script.src = url;
        document.head.appendChild(script);
      });
    },

    // 天地图 API 就绪后创建地图实例(原 initMap 主体)
    _createMap() {
      if (!this.$refs.mapContainer) return; // 组件已卸载(API 加载完成前离开页面)
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

        // 硬停: 拖动/移动/缩放过程中中心纬度越界(视口顶边越过 ±68° 北极圈/南极圈线)
        // 即处理。经度不限(世界图横向可环绕)。注意: 拖动进行中调用 centerAndZoom
        // 会永久损坏引擎拖动手势(实测) → 拖动中越界只 disableDrag 冻结(硬停),
        // 引擎派发 moveend(拖动结束)时再恢复拖动并回界(此时 centerAndZoom 安全)
        // 引擎真实事件名(实测): dragstart / drag / move(每帧) / moveend; 无 dragend
        this.map.addEventListener('dragstart', this._onDragStart);
        this.map.addEventListener('drag', this._clampLatIfNeeded);
        this.map.addEventListener('dragging', this._clampLatIfNeeded);
        this.map.addEventListener('move', this._clampLatIfNeeded);
        this.map.addEventListener('dragend', this._onDragEnd);
        this.map.addEventListener('moveend', this._onDragEnd);
        this.map.addEventListener('zoomend', this._clampLatIfNeeded);
        // 兜底: 指针/触摸松手时若仍处于冻结状态则恢复(引擎 moveend 未能触发时)
        document.addEventListener('mouseup', this._onPointerUp);
        document.addEventListener('touchend', this._onPointerUp);
        document.addEventListener('pointerup', this._onPointerUp);
        document.addEventListener('pointercancel', this._onPointerUp);

        // 2. 设置中心点和缩放
        const center = new T.LngLat(this.center[0], this.center[1]);
        this.map.centerAndZoom(center, this.zoom);

        // 2.5 比例尺随移动/缩放更新; 鼠标经纬度用容器 DOM mousemove 实时换算
        this.map.addEventListener('moveend', this._updateScale);
        this.map.addEventListener('zoomend', this._updateScale);
        this.$refs.mapContainer.addEventListener('mousemove', this._onMouseMove);
        this.$nextTick(() => this._updateScale()); // 初始比例尺

        // 3. 添加行政矢量底图（含道路、水系、边界等）
        const tk = TIANDITU_TK; // 天地图浏览器端 Key
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

        // 竞态兜底: 边界数据先于 API 脚本到达时, watcher 因 map 未就绪被跳过(renderBoundaries 有 !this.map 保护),
        // 这里补渲染一次, 避免"地图正常但边界不显示"
        if (this.boundaryData && this.boundaryData.features) {
          this.renderBoundaries(this.boundaryData, true);
        }
      } catch (error) {
        console.error('地图初始化失败:', error);
        this.mapLoadFailed = true;
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
    focusWatershed(lng, lat, level, bbox) {
      if (!this.map || lng === undefined || lat === undefined) return;
      let centerLng = lng;
      let centerLat = lat;
      let z;
      if (bbox) {
        // 有包围盒: 中心取包围盒中心, 缩放按包围盒大小动态计算(完整装进视野, 不再部分在地图外)
        centerLng = (bbox.minLng + bbox.maxLng) / 2;
        centerLat = (bbox.minLat + bbox.maxLat) / 2;
        z = this._fitZoomForBBox(bbox);
      } else {
        // 无包围盒: 按流域级别给一个合适的缩放（级别越高流域越小，zoom 越大）
        const zoomForLevel = { 2: 6, 4: 7, 6: 8, 8: 9, 10: 10, 12: 11, 14: 12 };
        z = zoomForLevel[level] || 10;
      }
      // 用 centerAndZoom 一步设置中心和缩放。
      // 注意不能用 panTo + setZoom 连调: panTo 带平移动画, 会与 setZoom 相互打断, 导致没有实际移动
      this.map.centerAndZoom(new T.LngLat(centerLng, centerLat), z);
    },

    // 计算让 bbox 完整进入视野的最大缩放(墨卡托投影公式, 与 _centerLimits 同源, 不依赖引擎 API):
    // 世界宽 = 256*2^zoom 像素 ↔ 360° 经度; 纬度按墨卡托 y = R*ln(tan(π/4+φ/2)) 换算像素。
    // 取经度/纬度两个约束中更严格者(取小), 留 10% 余量, 并夹在 [minZoom, maxZoom]。
    _fitZoomForBBox(bbox) {
      const el = this.$refs.mapContainer;
      const W = el ? el.clientWidth : 800;
      const H = el ? el.clientHeight : 600;
      const R = 6378137;
      const mercY = (lat) => R * Math.log(Math.tan(Math.PI / 4 + (lat * Math.PI) / 180 / 2));
      const dLng = Math.max(bbox.maxLng - bbox.minLng, 1e-9);
      const dY = Math.abs(mercY(bbox.maxLat) - mercY(bbox.minLat));
      const zLng = Math.log2((W * 0.9 * 360) / (dLng * 256));
      const zLat = Math.log2((H * 0.9 * 2 * Math.PI * R) / (dY * 256));
      const z = Math.floor(Math.min(zLng, zLat));
      return Math.max(3, Math.min(18, z));
    },

    // ---- 比例尺 + 鼠标经纬度 ----

    // 计算并更新左下角比例尺: 米/像素 = 156543.03392 * cos(φ) / 2^zoom（Web 墨卡托标准值），
    // 选 1/2/5×10^k 的"顺眼"距离, 使线宽落在 40~180px 之间
    _updateScale() {
      if (!this.map) return;
      try {
        const zoom = this.map.getZoom();
        const c = this.map.getCenter();
        const lat = typeof c.lat === 'function' ? c.lat() : c.lat;
        const mpp = 156543.03392 * Math.cos((lat * Math.PI) / 180) / Math.pow(2, zoom);
        const mag = Math.pow(10, Math.floor(Math.log10(mpp * 100)));
        const d = (mpp * 100) / mag;
        let nice;
        if (d <= 1) nice = 1 * mag;
        else if (d <= 2) nice = 2 * mag;
        else if (d <= 5) nice = 5 * mag;
        else nice = 10 * mag;
        this.scaleText = nice >= 1000
          ? `${(nice / 1000).toFixed(nice % 1000 === 0 ? 0 : 1)} km`
          : `${nice} m`;
        this.scaleWidth = Math.max(Math.round(nice / mpp), 40);
      } catch (e) {
        // 计算失败静默（不显示比例尺）
      }
    },

    // 鼠标移动 → 换算容器像素为经纬度（右下角显示）。
    // DOM mousemove 在容器上冒泡, clientX/Y 用容器 rect 换算, 鼠标在子元素(按钮/信息卡)上也正确
    _onMouseMove(e) {
      if (!this.map || !e) return;
      if (typeof e.clientX !== 'number' || !this.$refs.mapContainer) return;
      const rect = this.$refs.mapContainer.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      const ll = this._containerPointToLngLat(x, y);
      if (ll) this._setMouseCoord(ll.lng, ll.lat);
    },

    _setMouseCoord(lng, lat) {
      // 经度归一化到 (-180, 180], 纬度夹到 [-90, 90]
      this.mouseLng = ((lng + 540) % 360) - 180;
      this.mouseLat = Math.max(-90, Math.min(90, lat));
    },

    // 容器像素 → 经纬度: 优先用引擎 containerPointToLngLat（v4 实测存在）,
    // 失败退回墨卡托数学换算（与 _centerLimits/_fitZoomForBBox 同源, 不依赖引擎）
    _containerPointToLngLat(x, y) {
      if (!this.map) return null;
      try {
        if (typeof this.map.containerPointToLngLat === 'function') {
          let pt;
          try {
            pt = new T.Point(x, y);
          } catch (err) {
            pt = { x, y };
          }
          const p = this.map.containerPointToLngLat(pt);
          if (p) {
            const lng = typeof p.lng === 'function' ? p.lng() : p.lng;
            const lat = typeof p.lat === 'function' ? p.lat() : p.lat;
            if (typeof lng === 'number' && typeof lat === 'number') return { lng, lat };
          }
        }
      } catch (err) {
        // 走数学兜底
      }
      try {
        const R = 6378137;
        const zoom = this.map.getZoom();
        const c = this.map.getCenter();
        const clng = typeof c.lng === 'function' ? c.lng() : c.lng;
        const clat = typeof c.lat === 'function' ? c.lat() : c.lat;
        const el = this.$refs.mapContainer;
        const W = el ? el.clientWidth : 800;
        const H = el ? el.clientHeight : 600;
        const WORLD_PX = 256 * Math.pow(2, zoom);
        const dLng = (x - W / 2) / WORLD_PX * 360;
        const cY = R * Math.log(Math.tan(Math.PI / 4 + (clat * Math.PI) / 180 / 2));
        const dY = (H / 2 - y) / WORLD_PX * 2 * Math.PI * R;
        const lat = (2 * Math.atan(Math.exp((cY + dY) / R)) - Math.PI / 2) * 180 / Math.PI;
        return { lng: clng + dLng, lat };
      } catch (err) {
        return null;
      }
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

    // ---- 南北极硬停 ----

    // 中心纬度允许范围: 视口顶边恰好压住 ±VIEW_EDGE_LAT(北极圈/南极圈外)时的中心纬度。
    // 墨卡托投影数学(不依赖引擎 clamp, 高纬/越界时引擎返回值会被 clamp 导致边界漂移):
    //   世界宽高 = 256*2^zoom 像素; 投影 y = R*ln(tan(π/4+φ/2)), R=6378137;
    //   VIEW_EDGE_LAT° ↔ ±edgeY。中心限制 = 反解(edgeY - 视口半高投影)
    _centerLimits() {
      if (!this.map) return null;
      const zoom = this.map.getZoom();
      const el = this.$refs.mapContainer;
      const h = el ? el.clientHeight : 0;
      if (!h) return null;
      try {
        const R = 6378137;
        const WORLD_PX = 256 * Math.pow(2, zoom);
        const halfHProj = (h / 2) * (2 * Math.PI * R) / WORLD_PX;
        const edgeY = R * Math.log(Math.tan(Math.PI / 4 + (VIEW_EDGE_LAT * Math.PI) / 180 / 2));
        const centerYMax = edgeY - halfHProj;
        const maxLat = (2 * Math.atan(Math.exp(centerYMax / R)) - Math.PI / 2) * 180 / Math.PI;
        return { maxLat, minLat: -maxLat };
      } catch (e) {
        return { maxLat: VIEW_EDGE_LAT, minLat: -VIEW_EDGE_LAT };
      }
    },

    _onDragStart() {
      this._dragging = true;
    },

    // 拖动结束(引擎派发 moveend/dragend; 拖动中只有 move/drag, 不派发 moveend):
    // 若有冻结(拖动越界硬停), 恢复拖动并回界 —— 此时引擎手势已结束, centerAndZoom 安全
    _onDragEnd() {
      this._dragging = false;
      if (!this._dragLocked) {
        // 未冻结时也要做一次兜底检查(拖动结束位置可能越界: 冻结瞬间只越界几像素,
        // 但保险起见 moveend 后统一拉回边界)
        this._clampLatIfNeeded();
        return;
      }
      this._dragLocked = false;
      const lat = this._pendingClampLat;
      this._pendingClampLat = null;
      if (!this.map) return;
      try {
        if (typeof this.map.enableDrag === 'function') this.map.enableDrag();
        else if (typeof this.map.enableDragging === 'function') this.map.enableDragging();
      } catch (e) { /* 忽略 */ }
      if (lat !== null) {
        try {
          const c = this.map.getCenter();
          const lng = typeof c.lng === 'function' ? c.lng() : c.lng;
          this.map.centerAndZoom(new T.LngLat(lng, lat), this.map.getZoom());
        } catch (e) { /* 忽略 */ }
      }
    },

    // 中心纬度越界处理(拖动/移动/缩放后调用):
    // ① 拖动中(_dragging): 只 disableDrag 冻结 = 立即硬停无动画。不回界!
    //    拖动进行中 centerAndZoom 会永久损坏引擎手势(实测), 回界推迟到拖动结束
    // ② 非拖动(搜索定位/缩放/程序移动后): 直接 centerAndZoom 回界(无拖动中, 安全)
    _clampLatIfNeeded() {
      if (!this.map) return;
      const limits = this._centerLimits();
      if (!limits) return;
      const c = this.map.getCenter();
      if (!c) return;
      const lat = typeof c.lat === 'function' ? c.lat() : c.lat;
      const lng = typeof c.lng === 'function' ? c.lng() : c.lng;
      // 像素级容差: centerAndZoom 回界后引擎按像素取整, 中心仍可能有最多约 1px 偏移。
      // 旧 EPS=1e-4° 在 zoom≤4 时远小于 1px 对应度数(zoom3 约 0.17°),
      // 导致"回界 → moveend → 再回界"死循环(实测主线程卡死)。
      // 用 2px 容差覆盖引擎取整误差, 低 zoom 下边界略柔化(可多拖 2px), 可接受。
      const zoom = this.map.getZoom();
      const WORLD_PX = 256 * Math.pow(2, zoom);
      const degPerPx = 360 * Math.cos(lat * Math.PI / 180) / WORLD_PX;
      const EPS = Math.max(degPerPx * 2, 1e-6);
      let clamped = null;
      if (lat > limits.maxLat + EPS) clamped = limits.maxLat;
      else if (lat < limits.minLat - EPS) clamped = limits.minLat;
      if (clamped === null) return; // 界内, 无操作
      if (this._dragging) {
        // 拖动中: 冻结拖动(已冻结则不动)
        if (this._dragLocked) return;
        this._dragLocked = true;
        this._pendingClampLat = clamped;
        try {
          if (typeof this.map.disableDrag === 'function') this.map.disableDrag();
          else if (typeof this.map.disableDragging === 'function') this.map.disableDragging();
        } catch (e) { /* 忽略 */ }
      } else {
        // 非拖动(搜索定位/缩放/程序移动后越界): 直接回界。
        // 400ms 冷却: 即使容差仍没盖住引擎误差, 也强制阻断"回界→moveend→再回界"循环
        const now = Date.now();
        if (this._lastClampAt && now - this._lastClampAt < 400) return;
        this._lastClampAt = now;
        try {
          this.map.centerAndZoom(new T.LngLat(lng, clamped), this.map.getZoom());
        } catch (e) { /* 忽略 */ }
      }
    },

    // 兜底松手处理: 引擎 moveend 未派发时(拖动被异常中断)恢复冻结
    _onPointerUp() {
      if (!this._dragLocked) return;
      this._dragLocked = false;
      const lat = this._pendingClampLat;
      this._pendingClampLat = null;
      if (!this.map) return;
      try {
        if (typeof this.map.enableDrag === 'function') this.map.enableDrag();
        else if (typeof this.map.enableDragging === 'function') this.map.enableDragging();
      } catch (e) { /* 忽略 */ }
      if (lat !== null) {
        try {
          const c = this.map.getCenter();
          const lng = typeof c.lng === 'function' ? c.lng() : c.lng;
          this.map.centerAndZoom(new T.LngLat(lng, lat), this.map.getZoom());
        } catch (e) { /* 忽略 */ }
      }
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

/* 比例尺（左下角） */
.scale-bar {
  position: absolute;
  left: 12px;
  bottom: 12px;
  z-index: 900;
  display: flex;
  flex-direction: column;
  align-items: center;
  background: rgba(255, 255, 255, 0.85);
  border-radius: 4px;
  padding: 4px 8px;
  font-size: 12px;
  color: #303133;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.15);
  pointer-events: none; /* 不挡地图拖动 */
}
.scale-line {
  display: block;
  height: 0;
  border-top: 2px solid #303133;
  border-left: 2px solid #303133;
  border-right: 2px solid #303133;
  margin-bottom: 3px;
}
.scale-label {
  line-height: 1.2;
}

/* 天地图 API 加载失败提示层(覆盖地图区域, z-index 高于地图与控件) */
.map-load-error {
  position: absolute;
  inset: 0;
  z-index: 1100;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(245, 247, 250, 0.92);
}
.map-load-error-box {
  text-align: center;
  color: #606266;
}
.map-load-error-box p {
  margin: 0 0 12px;
  font-size: 14px;
}
.map-load-error-box button {
  padding: 6px 20px;
  border: 1px solid #409eff;
  border-radius: 4px;
  background: #fff;
  color: #409eff;
  font-size: 14px;
  cursor: pointer;
}
.map-load-error-box button:hover {
  background: #409eff;
  color: #fff;
}

/* 鼠标经纬度（右下角） */
.mouse-coords {
  position: absolute;
  right: 12px;
  bottom: 12px;
  z-index: 900;
  display: flex;
  gap: 12px;
  background: rgba(255, 255, 255, 0.85);
  border-radius: 4px;
  padding: 3px 10px;
  font-size: 12px;
  color: #303133;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.15);
  pointer-events: none; /* 不挡地图操作 */
  white-space: nowrap;
}

/* 浮动流域信息卡（右下角；bottom 上移避开经纬度条） */
.watershed-info {
  position: absolute;
  right: 12px;
  bottom: 56px;
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
