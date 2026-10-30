'use strict';
const fs = require('node:fs');
const path = require('node:path');
const { dataDir } = require('./store');

function logDir(variant) {
  return process.env.BENCHNOTES_LOG_DIR || path.join(dataDir(variant), 'logs');
}

function logPath(variant) {
  const dir = logDir(variant);
  fs.mkdirSync(dir, { recursive: true });
  return path.join(dir, 'benchnotes.log');
}

module.exports = { logDir, logPath };
