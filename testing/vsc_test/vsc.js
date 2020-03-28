const fs = require('fs');
const vsctm = require('vscode-textmate');

if (process.argv.length < 4) {
    console.log('usage: t.js GRAMMAR FILE');
    process.exit(1);
}

const grammar = process.argv[2];
const file = process.argv[3];

const scope = JSON.parse(fs.readFileSync(grammar, {encoding: 'UTF-8'})).scopeName;

/**
 * Utility to read a file as a promise
 */
function readFile(path) {
    return new Promise((resolve, reject) => {
        fs.readFile(path, (error, data) => error ? reject(error) : resolve(data));
    })
}

// Create a registry that can create a grammar from a scope name.
const registry = new vsctm.Registry({
    loadGrammar: (scopeName) => {
        if (scopeName === scope) {
            return readFile(grammar).then(data => vsctm.parseRawGrammar(data.toString(), grammar))
        }
        console.log(`Unknown scope name: ${scopeName}`);
        return null;
    }
});

// Load the JavaScript grammar and any other grammars included by it async.
registry.loadGrammar(scope).then(grammar => {
    const text = fs.readFileSync(file, {encoding: 'UTF-8'}).trimEnd('\n').split(/\n/);
    let ruleStack = vsctm.INITIAL;
    for (let i = 0; i < text.length; i++) {
        const line = text[i];
        const lineTokens = grammar.tokenizeLine(line, ruleStack);
        console.log(`\nTokenizing line: ${line}`);
        for (let j = 0; j < lineTokens.tokens.length; j++) {
            const token = lineTokens.tokens[j];
            console.log(` - token from ${token.startIndex} to ${token.endIndex} ` +
              `(${line.substring(token.startIndex, token.endIndex)}) ` +
              `with scopes ${token.scopes.join(', ')}`
            );
        }
        ruleStack = lineTokens.ruleStack;
    }
});
