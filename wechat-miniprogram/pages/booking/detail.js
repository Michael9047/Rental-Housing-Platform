// pages/booking/detail.js
const api = require('../../utils/api.js');

Page({
  data: {
    booking: null,
    loading: true,
  },

  onLoad(options) {
    const id = options.id;
    if (!id) return;
    this.loadBooking(id);
  },

  async loadBooking(id) {
    this.setData({ loading: true });
    try {
      const res = await api.get('/bookings/' + id);
      this.setData({ booking: res, loading: false });
    } catch (err) {
      this.setData({ loading: false });
    }
  },

  async onCancelBooking() {
    const res = await new Promise((resolve) => {
      wx.showModal({
        title: '确认取消',
        content: '确定要取消此预约吗？',
        success: (r) => resolve(r.confirm),
      });
    });
    if (!res) return;

    try {
      await api.patch('/bookings/' + this.data.booking.id + '/cancel');
      wx.showToast({ title: '已取消', icon: 'success' });
      this.loadBooking(this.data.booking.id);
    } catch (err) {
      // handled by interceptor
    }
  },
});
