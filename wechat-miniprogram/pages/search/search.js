// pages/search/search.js
const api = require('../../utils/api.js');

Page({
  data: {
    keyword: '',
    filters: {
      district: '',
      minPrice: 0,
      maxPrice: 0,
      propertyType: '',
    },
    results: [],
    page: 1,
    hasMore: true,
    loading: false,
    mapMode: false,
  },

  onLoad(options) {
    if (options.keyword) {
      this.setData({ keyword: decodeURIComponent(options.keyword) });
    }
    if (options.mapMode) {
      this.setData({ mapMode: true });
    }
    this.doSearch();
  },

  // Perform search
  async doSearch(reset = true) {
    if (this.data.loading) return;
    if (reset) {
      this.setData({ page: 1, results: [], hasMore: true });
    }
    if (!this.data.hasMore) return;

    this.setData({ loading: true });
    try {
      const params = {
        keyword: this.data.keyword,
        page: this.data.page,
        size: 20,
      };
      if (this.data.filters.district) params.district = this.data.filters.district;
      if (this.data.filters.propertyType) params.property_type = this.data.filters.propertyType;
      if (this.data.filters.minPrice) params.min_price = this.data.filters.minPrice;
      if (this.data.filters.maxPrice) params.max_price = this.data.filters.maxPrice;

      const res = await api.get('/properties/search', params);
      const items = res.items || res.data || [];
      const newResults = reset ? items : [...this.data.results, ...items];
      this.setData({
        results: newResults,
        page: this.data.page + 1,
        hasMore: items.length >= 20,
        loading: false,
      });
    } catch (err) {
      this.setData({ loading: false });
    }
  },

  // Keyword input
  onKeywordInput(e) {
    this.setData({ keyword: e.detail.value });
  },

  // Confirm search
  onSearchConfirm() {
    this.doSearch();
  },

  // Filter changes
  onFilterChange(e) {
    const { field } = e.currentTarget.dataset;
    const value = e.detail.value;
    this.setData({
      ['filters.' + field]: value,
    });
    this.doSearch();
  },

  // Navigate to property detail
  onTapProperty(e) {
    const id = e.currentTarget.dataset.id;
    wx.navigateTo({ url: '/pages/property/property?id=' + id });
  },

  // Load more
  onReachBottom() {
    this.doSearch(false);
  },

  // Pull to refresh
  onPullDownRefresh() {
    this.doSearch().then(() => wx.stopPullDownRefresh());
  },
});
