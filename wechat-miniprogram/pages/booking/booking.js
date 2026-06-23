// pages/booking/booking.js
const api = require('../../utils/api.js');
const auth = require('../../utils/auth.js');

Page({
  data: {
    bookings: [],
    loading: false,
    statusTab: 'all',
  },

  onShow() {
    auth.checkLogin().then(() => {
      this.loadBookings();
    });
  },

  async loadBookings() {
    this.setData({ loading: true });
    try {
      const res = await api.get('/bookings');
      this.setData({
        bookings: res.items || res.data || [],
        loading: false,
      });
    } catch (err) {
      this.setData({ loading: false });
    }
  },

  // Tab switch
  onTabChange(e) {
    this.setData({ statusTab: e.currentTarget.dataset.tab });
  },

  // Filtered bookings
  get filteredBookings() {
    const all = this.data.bookings;
    if (this.data.statusTab === 'all') return all;
    if (this.data.statusTab === 'pending') return all.filter(b => b.status === 'pending');
    if (this.data.statusTab === 'approved') return all.filter(b => b.status === 'approved');
    if (this.data.statusTab === 'cancelled') return all.filter(b => b.status === 'cancelled' || b.status === 'rejected');
    return all;
  },

  // Navigate to detail
  onTapBooking(e) {
    const id = e.currentTarget.dataset.id;
    wx.navigateTo({ url: '/pages/booking/detail?id=' + id });
  },

  // Pull to refresh
  onPullDownRefresh() {
    this.loadBookings().then(() => wx.stopPullDownRefresh());
  },
});
