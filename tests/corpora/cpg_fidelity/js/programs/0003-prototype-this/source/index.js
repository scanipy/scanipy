// CMP-CORP-CPG-js synthesized program 0003
// Coverage: prototype-mutation, this-binding
'use strict';

function Counter(start) {
  this.value = start;
}

Counter.prototype.increment = function increment() {
  this.value += 1;
  return this.value;
};

Counter.prototype.add = function add(n) {
  this.value += n;
  return this.value;
};

function makeBound(counter) {
  return counter.increment.bind(counter);
}

function applyAdd(counter, n) {
  return Counter.prototype.add.call(counter, n);
}

const proto = Object.create(Counter.prototype);
proto.reset = function reset() {
  this.value = 0;
  return this.value;
};

module.exports = { Counter, makeBound, applyAdd, proto };
