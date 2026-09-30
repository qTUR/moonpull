// Loads the game's core block from the single source file for tooling.
const fs = require('fs'), path = require('path');
const html = fs.readFileSync(path.join(__dirname, '..', 'src', 'game.html'), 'utf8');
const m = html.match(/\/\*<CORE>\*\/([\s\S]*?)\/\*<\/CORE>\*\//);
module.exports = new Function(m[1] + '\nreturn Core;')();
