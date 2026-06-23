// components/map-view/map-view.js
Component({
  properties: {
    latitude: { type: Number, value: 31.299 },
    longitude: { type: Number, value: 120.585 },
    markers: { type: Array, value: [] },
  },

  data: {
    defaultMarkers: [],
  },

  observers: {
    'latitude, longitude'(lat, lng) {
      this.setData({
        defaultMarkers: [{
          id: 1,
          latitude: lat,
          longitude: lng,
          iconPath: '/images/marker.png',
          width: 30,
          height: 30,
          callout: { content: '房源位置', padding: 8, borderRadius: 4, display: 'ALWAYS' },
        }],
      });
    },
  },
});
