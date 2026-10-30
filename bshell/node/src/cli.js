'use strict';
const { version } = require('./version');

const VARIANT = 'bshell-node';

function parse(argv) {
  const args = { _: [], flags: new Set(), opts: {} };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--tarball' || a === '--apps-dir') args.opts[a.slice(2)] = argv[++i];
    else if (a.startsWith('--')) args.flags.add(a.slice(2));
    else args._.push(a);
  }
  return args;
}

async function main(argv, variant = VARIANT) {
  const args = parse(argv);
  const [cmd, sub] = args._;
  if (cmd === 'version') { console.log(version); return 0; }
  if (cmd === 'ui') {
    const ui = require('./ui');
    if (args.flags.has('detach')) { ui.detach(argv.filter((a) => a !== '--detach')); return 0; }
    if (args.flags.has('check')) {
      try { await ui.selfTest(variant, { skipBackend: args.flags.has('skip-backend') }); return 0; }
      catch (e) { console.error('FAILED: ' + e.message); return 1; }
    }
    return ui.run(variant);
  }
  if (cmd === 'update') {
    const code = require('./update').update({ tarball: args.opts.tarball });
    if (code === 0 && process.platform === 'darwin') require('./shell-macos').build(); // default apps dir, or BENCHNOTES_APPS_DIR
    return code;
  }
  if (cmd === 'shell' && sub === 'build') {
    if (!args.opts['apps-dir']) { console.error('shell build needs --apps-dir <dir>'); return 2; }
    try {
      console.log(require('./shell-macos').build(args.opts['apps-dir'], { skipBackend: args.flags.has('skip-backend') }));
      return 0;
    } catch (e) { console.error('FAILED: ' + e.message); return 1; }
  }
  console.error('usage: benchnotes ui [--check [--skip-backend]] | update --tarball <path> | version | shell build --apps-dir <dir>');
  return 2;
}

module.exports = { main, parse };
