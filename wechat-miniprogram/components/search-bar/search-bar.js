// components/search-bar/search-bar.js
Component({
  properties: {
    value: { type: String, value: '' },
    placeholder: { type: String, value: '搜索房源' },
  },

  methods: {
    onInput(e) {
      this.triggerEvent('input', { value: e.detail.value });
    },
    onSearch() {
      this.triggerEvent('search', { value: this.data.value });
    },
  },
});
