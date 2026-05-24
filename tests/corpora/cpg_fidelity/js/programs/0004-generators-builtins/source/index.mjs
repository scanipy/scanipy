// CMP-CORP-CPG-js synthesized program 0004
// Coverage: generators, node-builtins, module-system-esm
import { createHash } from 'crypto';

function hashOf(text) {
  return createHash('sha256').update(text).digest('hex');
}

function* tokenize(text) {
  for (const part of text.split(/\s+/)) {
    if (part.length > 0) {
      yield part;
    }
  }
}

function* hashed(text) {
  for (const token of tokenize(text)) {
    yield hashOf(token);
  }
}

export function digestStream(text) {
  const out = [];
  for (const h of hashed(text)) {
    out.push(h);
  }
  return out;
}
