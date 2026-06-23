// utils/api.js - Wrapper around wx.request for backend API calls
const app = getApp();

const request = (options) => {
  return new Promise((resolve, reject) => {
    const token = wx.getStorageSync('access_token');
    const header = {
      'Content-Type': 'application/json',
    };
    if (token) {
      header['Authorization'] = 'Bearer ' + token;
    }

    wx.request({
      url: app.globalData.baseUrl + options.url,
      method: options.method || 'GET',
      data: options.data || {},
      header,
      success(res) {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve(res.data);
        } else if (res.statusCode === 401) {
          // Token expired, try to re-login
          wx.removeStorageSync('access_token');
          wx.removeStorageSync('user');
          app.globalData.isLoggedIn = false;
          app.globalData.userInfo = null;
          reject({ code: 401, message: '登录已过期，请重新登录' });
        } else {
          const msg = res.data?.detail || '请求失败';
          wx.showToast({ title: msg, icon: 'none' });
          reject(res.data);
        }
      },
      fail(err) {
        wx.showToast({ title: '网络请求失败', icon: 'none' });
        reject(err);
      },
    });
  });
};

const api = {
  get: (url, data) => request({ url, method: 'GET', data }),
  post: (url, data) => request({ url, method: 'POST', data }),
  put: (url, data) => request({ url, method: 'PUT', data }),
  patch: (url, data) => request({ url, method: 'PATCH', data }),
  delete: (url, data) => request({ url, method: 'DELETE', data }),
};

module.exports = api;
