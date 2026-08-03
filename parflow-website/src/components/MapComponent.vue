<template>
  <div ref="mapContainer" class="map-container"></div>
</template>

<script>
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
    markers: {
      type: Array,
      default: () => [],
    },
  },
  data() {
    return {
      map: null,
      markerLayer: null,
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
    markers: {
      handler(newMarkers) {
        this.updateMarkers(newMarkers);
      },
      deep: true,
    },
  },
  mounted() {
    this.initMap();
  },
  beforeUnmount() {
    if (this.map) {
      try {
        if (typeof this.map.dispose === 'function') {
          this.map.dispose();
        }
      } catch (e) {
        // 忽略
      }
      this.map = null;
      this.markerLayer = null;
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
        this.map = new T.Map(this.$refs.mapContainer);

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

        // 5. 添加标记图层
        this.markerLayer = new T.Layer();
        this.map.addLayer(this.markerLayer);

        // 6. 初始标记
        this.updateMarkers(this.markers);

        console.log('天地图初始化成功（行政地图 + 注记）');
      } catch (error) {
        console.error('地图初始化失败:', error);
      }
    },

    updateMarkers(markersData) {
      if (!this.markerLayer) return;
      this.markerLayer.clear();
      if (!markersData || markersData.length === 0) return;

      markersData.forEach((item) => {
        if (!item.lng || !item.lat) return;
        const point = new T.LngLat(item.lng, item.lat);
        const marker = new T.Marker(point);
        marker.addEventListener('click', () => {
          this.$emit('marker-click', item);
        });
        this.markerLayer.addMarker(marker);
      });
    },

    addMarker(item) {
      if (!this.markerLayer || !item.lng || !item.lat) return;
      const point = new T.LngLat(item.lng, item.lat);
      const marker = new T.Marker(point);
      marker.addEventListener('click', () => {
        this.$emit('marker-click', item);
      });
      this.markerLayer.addMarker(marker);
    },

    clearMarkers() {
      if (this.markerLayer) {
        this.markerLayer.clear();
      }
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
</style>