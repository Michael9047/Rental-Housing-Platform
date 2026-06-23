// pages/property/property.js
const api = require('../../utils/api.js');
const auth = require('../../utils/auth.js');
const app = getApp();

Page({
  data: {
    property: null,
    images: [],
    loading: true,
    bookingVisible: false,
    bookingRemark: '',
    submitting: false,
  },

  onLoad(options) {
    const id = options.id;
    if (!id) {
      wx.showToast({ title: '参数错误', icon: 'none' });
      return;
    }
    this.loadProperty(id);
  },

  async loadProperty(id) {
    this.setData({ loading: true });
    try {
      const res = await api.get('/properties/' + id);
      const images = res.images?.map(img => app.globalData.baseUrl.replace('/api/v1', '') + '/api/v1/uploads/' + img.filename) || [];
      this.setData({
        property: res,
        images: images.length > 0 ? images : [res.cover_url || ''],
        loading: false,
      });
    } catch (err) {
      this.setData({ loading: false });
    }
  },

  // Preview image
  onPreviewImage(e) {
    const current = e.currentTarget.dataset.src;
    wx.previewImage({
      urls: this.data.images,
      current,
    });
  },

  // Show booking modal
  onBookViewing() {
    auth.checkLogin().then(() => {
      this.setData({ bookingVisible: true, bookingRemark: '' });
    });
  },

  // Hide booking modal
  onCancelBooking() {
    this.setData({ bookingVisible: false });
  },

  // Remark input
  onRemarkInput(e) {
    this.setData({ bookingRemark: e.detail.value });
  },

  // Submit booking
  async onSubmitBooking() {
    this.setData({ submitting: true });
    try {
      await api.post('/bookings', {
        property_id: this.data.property.id,
        remark: this.data.bookingRemark,
      });
      wx.showToast({ title: '预约成功', icon: 'success' });
      this.setData({ bookingVisible: false, submitting: false });
    } catch (err) {
      this.setData({ submitting: false });
    }
  },

  // Call landlord
  onCallLandlord() {
    if (this.data.property?.landlord_phone) {
      wx.makePhoneCall({ phoneNumber: this.data.property.landlord_phone });
    } else {
      wx.showToast({ title: '暂无联系方式', icon: 'none' });
    }
  },
});
