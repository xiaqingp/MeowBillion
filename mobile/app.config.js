const app = require('./app.json');

module.exports = {
  ...app.expo,
  extra: { ...app.expo.extra, buildTime: new Date().toISOString() },
};
