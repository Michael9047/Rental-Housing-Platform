// pages/index/index.js
const api = require('../../utils/api.js');
const auth = require('../../utils/auth.js');

Page({
  data: {
    searchKeyword: '',
    recommendList: [],
    banners: [],
    loading: false,
  },

  onLoad() {
    auth.checkLogin().then(() => {
      this.loadRecommendList();
    });
  },

  onShow() {
    if (auth.isLoggedIn()) {
      this.loadRecommendList();
    }
  },

  // Load recommended properties
  async loadRecommendList() {
    this.setData({ loading: true });
    try {
      const res = await api.get('/properties', { page: 1, size: 10 });
      this.setData({
        recommendList: res.items || res.data || [],
        loading: false,
      });
    } catch (err) {
      this.setData({ loading: false });
    }
  },

  // Handle search input
  onSearchInput(e) {
    this.setData({ searchKeyword: e.detail.value });
  },

  // Navigate to search page
  onSearch() {
    const keyword = this.data.searchKeyword.trim();
    if (!keyword) {
      wx.showToast({ title: '请输入搜索关键词', icon: 'none' });
      return;
    }
    wx.navigateTo({
      url: '/pages/search/search?keyword=' + encodeURIComponent(keyword),
    });
  },

  // Navigate to property detail
  onTapProperty(e) {
    const id = e.currentTarget.dataset.id;
    wx.navigateTo({ url: '/pages/property/property?id=' + id });
  },

  // Open map mode
  onMapMode() {
    wx.navigateTo({ url: '/pages/search/search?mapMode=1' });
  },

  // Pull to refresh
  onPullDownRefresh() {
    this.loadRecommendList().then(() => {
      wx.stopPullDownRefresh();
    });
  },
});
