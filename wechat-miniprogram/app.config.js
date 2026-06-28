// app.config.js - Environment and API configuration
const config = {
  development: {
    baseUrl: 'http://localhost:8000/api/v1',
    wsUrl: 'ws://localhost:8000',
  },
  production: {
    baseUrl: 'https://api.yourdomain.com/api/v1',
    wsUrl: 'wss://api.yourdomain.com',
  },
};

const env = 'development'; // Switch to 'production' for release

module.exports = config[env];
