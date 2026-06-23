// app.js
App({
  onLaunch() {
    // Check login status on launch
    this.checkLoginStatus();
  },

  checkLoginStatus() {
    const token = wx.getStorageSync('access_token');
    if (token) {
      this.globalData.isLoggedIn = true;
    }
  },

  globalData: {
    isLoggedIn: false,
    userInfo: null,
    baseUrl: 'http://localhost:8000/api/v1',
  },
});
