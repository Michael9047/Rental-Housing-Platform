// utils/auth.js - WeChat login state management
const api = require('./api.js');
const app = getApp();

const auth = {
  /**
   * Perform WeChat login: wx.login -> backend -> store token
   */
  login() {
    return new Promise((resolve, reject) => {
      wx.login({
        success(res) {
          if (res.code) {
            api.post('/wechat/auth/wechat/login', { code: res.code })
              .then((data) => {
                // Store token and user info
                wx.setStorageSync('access_token', data.access_token);
                wx.setStorageSync('user', JSON.stringify(data.user));
                app.globalData.isLoggedIn = true;
                app.globalData.userInfo = data.user;
                resolve(data);
              })
              .catch(reject);
          } else {
            reject(new Error('wx.login failed: ' + res.errMsg));
          }
        },
        fail(err) {
          reject(err);
        },
      });
    });
  },

  /**
   * Check if user is logged in, try login if not
   */
  checkLogin() {
    const token = wx.getStorageSync('access_token');
    if (token) {
      app.globalData.isLoggedIn = true;
      const userStr = wx.getStorageSync('user');
      if (userStr) {
        try {
          app.globalData.userInfo = JSON.parse(userStr);
        } catch (e) {
          // ignore parse error
        }
      }
      return Promise.resolve();
    }
    return this.login();
  },

  /**
   * Logout: clear local storage
   */
  logout() {
    wx.removeStorageSync('access_token');
    wx.removeStorageSync('user');
    app.globalData.isLoggedIn = false;
    app.globalData.userInfo = null;
  },

  /**
   * Get current user info from global data
   */
  getUserInfo() {
    return app.globalData.userInfo;
  },

  /**
   * Check login status
   */
  isLoggedIn() {
    return app.globalData.isLoggedIn;
  },
};

module.exports = auth;
