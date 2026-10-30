#!/usr/bin/env node
'use strict';
require('../src/cli').main(process.argv.slice(2)).then((code) => {
  // null = the GUI is running; the process stays alive until the window closes.
  if (code !== null && code !== undefined) process.exit(code);
}, (e) => { console.error(e); process.exit(1); });
