// CMP-CORP-CPG-js synthesized program 0001
// Coverage: module-system-commonjs, higher-order-functions, node-builtins
'use strict';

const fs = require('fs');

function readConfig(path) {
  return fs.readFileSync(path, 'utf8');
}

function parseConfig(text) {
  return JSON.parse(text);
}

function compose(f, g) {
  return function (x) {
    return f(g(x));
  };
}

function loadConfig(path) {
  const pipeline = compose(parseConfig, readConfig);
  return pipeline(path);
}

function applyAll(value, fns) {
  let acc = value;
  for (const fn of fns) {
    acc = fn(acc);
  }
  return acc;
}

module.exports = { readConfig, parseConfig, compose, loadConfig, applyAll };
