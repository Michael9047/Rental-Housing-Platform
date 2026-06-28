// components/property-card/property-card.js
Component({
  properties: {
    property: {
      type: Object,
      value: {},
    },
  },

  data: {
    coverUrl: '',
  },

  observers: {
    'property'(val) {
      if (val && val.cover_url) {
        const app = getApp();
        const base = app.globalData.baseUrl.replace('/api/v1', '');
        this.setData({ coverUrl: base + '/api/v1/uploads/' + val.cover_url });
      }
    },
  },

  methods: {
    onTap() {
      this.triggerEvent('tap', { id: this.data.property.id });
    },
  },
});
