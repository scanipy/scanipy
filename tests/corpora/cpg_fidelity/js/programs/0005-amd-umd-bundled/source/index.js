// CMP-CORP-CPG-js synthesized program 0005
// Coverage: module-system-amd-umd, bundled-transpiled (parse-success stressor)
// UMD wrapper as emitted by legacy bundlers; contains a dynamic dispatch site
// (registry[name]()) that the ground truth tags `dynamic` and EXCLUDES from
// call-edge precision/recall (CW-DETECT territory, DOC §3.4).
(function (root, factory) {
  if (typeof define === 'function' && define.amd) {
    define(['exports'], factory);
  } else if (typeof exports === 'object') {
    factory(exports);
  } else {
    factory((root.widget = {}));
  }
})(typeof self !== 'undefined' ? self : this, function (exports) {
  'use strict';

  function square(x) {
    return x * x;
  }

  function cube(x) {
    return x * square(x);
  }

  var registry = { square: square, cube: cube };

  function dispatch(name, value) {
    // dynamic call site: target not statically resolvable -> tagged `dynamic`
    return registry[name](value);
  }

  exports.square = square;
  exports.cube = cube;
  exports.dispatch = dispatch;
});
