// pages/chat/chat.js
const api = require('../../utils/api.js');
const auth = require('../../utils/auth.js');

Page({
  data: {
    messages: [],
    inputValue: '',
    sessionId: null,
    loading: false,
    sending: false,
    scrollToView: '',
    streamingContent: '',
  },

  onLoad() {
    auth.checkLogin().then(() => {
      this.createSession();
    });
  },

  async createSession() {
    try {
      const res = await api.post('/chat/sessions');
      this.setData({ sessionId: res.id });
    } catch (err) {
      wx.showToast({ title: '初始化聊天失败', icon: 'none' });
    }
  },

  // Input handler
  onInput(e) {
    this.setData({ inputValue: e.detail.value });
  },

  // Send message
  async onSend() {
    const text = this.data.inputValue.trim();
    if (!text || !this.data.sessionId || this.data.sending) return;

    const userMsg = { role: 'user', content: text, id: Date.now() };
    const messages = [...this.data.messages, userMsg];
    this.setData({
      messages,
      inputValue: '',
      sending: true,
      streamingContent: '',
    });

    const assistantMsg = { role: 'assistant', content: '', id: Date.now() + 1, loading: true };
    this.setData({ messages: [...this.data.messages, assistantMsg] });

    try {
      // Use request with raw response for SSE streaming
      const token = wx.getStorageSync('access_token');
      const requestTask = wx.request({
        url: getApp().globalData.baseUrl + '/chat/sessions/' + this.data.sessionId + '/messages',
        method: 'POST',
        data: { content: text },
        header: {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer ' + token,
        },
        enableChunked: true,
        success: (res) => {
          // Full response fallback
          const msgs = this.data.messages;
          const lastIdx = msgs.length - 1;
          if (msgs[lastIdx] && msgs[lastIdx].role === 'assistant') {
            msgs[lastIdx].content = res.data?.content || res.data?.reply || '';
            msgs[lastIdx].loading = false;
            this.setData({ messages: msgs, sending: false });
          }
        },
        fail: () => {
          const msgs = this.data.messages;
          const lastIdx = msgs.length - 1;
          if (msgs[lastIdx] && msgs[lastIdx].role === 'assistant') {
            msgs[lastIdx].content = '抱歉，请求失败，请重试。';
            msgs[lastIdx].loading = false;
            this.setData({ messages: msgs, sending: false });
          }
        },
      });
    } catch (err) {
      this.setData({ sending: false });
    }
  },

  // Scroll to bottom
  onReady() {
    this.scrollToBottom();
  },

  scrollToBottom() {
    const msgs = this.data.messages;
    if (msgs.length > 0) {
      this.setData({ scrollToView: 'msg-' + msgs[msgs.length - 1].id });
    }
  },

  // Navigate to property from chat card
  onTapPropertyCard(e) {
    const id = e.currentTarget.dataset.id;
    wx.navigateTo({ url: '/pages/property/property?id=' + id });
  },
});
