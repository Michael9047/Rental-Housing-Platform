// pages/me/me.js
const auth = require('../../utils/auth.js');
const app = getApp();

Page({
  data: {
    userInfo: null,
    isLoggedIn: false,
    roleLabels: {
      tenant: '租客',
      landlord: '房东',
      admin: '管理员',
    },
  },

  onShow() {
    this.loadUserInfo();
  },

  loadUserInfo() {
    const info = auth.getUserInfo();
    const loggedIn = auth.isLoggedIn();
    this.setData({
      userInfo: info,
      isLoggedIn: loggedIn,
    });
  },

  // WeChat login
  onLogin() {
    wx.showLoading({ title: '登录中...' });
    auth.login()
      .then(() => {
        wx.hideLoading();
        wx.showToast({ title: '登录成功', icon: 'success' });
        this.loadUserInfo();
      })
      .catch((err) => {
        wx.hideLoading();
        wx.showToast({ title: '登录失败: ' + (err.message || '未知错误'), icon: 'none' });
      });
  },

  // Bind phone
  onBindPhone(e) {
    const { code } = e.detail;
    if (!code) return;
    wx.showLoading({ title: '绑定中...' });
    const api = require('../../utils/api.js');
    api.post('/auth/wechat/phone', { code })
      .then(() => {
        wx.hideLoading();
        wx.showToast({ title: '手机号绑定成功', icon: 'success' });
        this.loadUserInfo();
      })
      .catch(() => {
        wx.hideLoading();
        wx.showToast({ title: '绑定失败', icon: 'none' });
      });
  },

  // Switch role
  async onRoleSwitch(e) {
    const role = e.currentTarget.dataset.role;
    wx.showModal({
      title: '切换身份',
      content: '确定切换为"' + (this.data.roleLabels[role] || role) + '"吗？',
      success: async (res) => {
        if (res.confirm) {
          try {
            const api = require('../../utils/api.js');
            await api.patch('/users/me', { role });
            wx.showToast({ title: '身份已切换', icon: 'success' });
            auth.checkLogin();
            this.loadUserInfo();
          } catch (err) {
            // handled by interceptor
          }
        }
      },
    });
  },

  // Logout
  onLogout() {
    wx.showModal({
      title: '退出登录',
      content: '确定要退出登录吗？',
      success: (res) => {
        if (res.confirm) {
          auth.logout();
          this.setData({ isLoggedIn: false, userInfo: null });
          wx.showToast({ title: '已退出', icon: 'success' });
        }
      },
    });
  },

  // Navigate to booking
  onGoBookings() {
    wx.switchTab({ url: '/pages/booking/booking' });
  },
});
