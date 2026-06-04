// build_lock.mjs — assemble/validate tests/corpora/cpg_fidelity/js/corpus.lock.
//
// Responsibilities (DOC-CMP-CORP-CPG-js §3.2, §3.4, §7):
//   1. Walk programs/<id>/, load provenance.yaml + extraction.yaml, hash source/
//      and ground_truth/ trees.
//   2. Refuse to emit on any DOC §7 HARD failure:
//        - missing source_url / commit_sha / license / surface / module_system
//        - license not on the allow-list
//        - surface=ts without tsconfig.json
//        - missing ground_truth/{ast,cfg,callgraph,pdg}.json
//        - construct-coverage tag union not fully covered (§4.3)
//        - a §4.3 module_system value with zero programs
//        - surface imbalance > 90%
//        - extraction tool versions != README-pinned versions
//   3. Emit corpus.lock with corpus_version + corpus_digest, where corpus_digest
//      is sha256 of the canonical serialization EXCLUDING volatile built_at /
//      built_by and the digest field itself (DOC §8).
//
// Run:  node build_lock.mjs --write    # write lock
//       node build_lock.mjs --check    # CI: fail on digest drift / hard failures

import {
  readFileSync,
  writeFileSync,
  readdirSync,
  statSync,
  existsSync,
} from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';
import { createHash } from 'crypto';

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = join(HERE, '..');
const PROGRAMS_DIR = join(ROOT, 'programs');
const LOCK_PATH = join(ROOT, 'corpus.lock');

const CORPUS_ID = 'CMP-CORP-CPG-js';
const CORPUS_VERSION = '0.1.0'; // README §Status: NOT the v1.0.0 gate-passing bar
const BUILT_BY = 'corpus-agent/CMP-CORP-CPG-js';

const LICENSE_ALLOWLIST = new Set([
  'MIT',
  'Apache-2.0',
  'BSD-2-Clause',
  'BSD-3-Clause',
  'MPL-2.0',
  'ISC',
]);

// §4.3 required construct-coverage tags (union must be covered).
const REQUIRED_TAGS = new Set([
  'module-system-commonjs',
  'module-system-esm',
  'module-system-amd-umd',
  'higher-order-functions',
  'prototype-mutation',
  'this-binding',
  'async-await',
  'generators',
  'type-informed-dispatch',
  'jsx-tsx',
  'decorators-experimental',
  'node-builtins',
  'bundled-transpiled',
]);

// §4.3 module systems that must each have >= 1 program.
const REQUIRED_MODULE_SYSTEMS = new Set(['commonjs', 'esm', 'umd']);

// README-pinned extraction tool versions (drift => hard fail).
const PINNED_TOOLS = { node: '24.13.0', typescript_eslint: '6.18.0' };

// ---- tiny YAML helpers (deterministic) ------------------------------------
function parseSimpleYaml(text) {
  // Minimal parser for our provenance/extraction docs: top-level scalars,
  // one-level nested mappings (2-space indent), top-level scalar lists
  // (`  - item`), and literal block scalars (`key: |`).
  const out = {};
  const lines = text.split('\n');
  let i = 0;
  let curList = null; // active top-level list
  let curMap = null; // active one-level nested mapping
  let block = null; // active literal block scalar
  while (i < lines.length) {
    const raw = lines[i];
    if (block) {
      if (raw.startsWith('  ') || raw.trim() === '') {
        block.lines.push(raw.replace(/^ {2}/, ''));
        i++;
        continue;
      } else {
        out[block.key] = block.lines.join('\n').replace(/\n+$/, '');
        block = null;
      }
    }
    const line = raw.replace(/\s+$/, '');
    if (line === '') {
      i++;
      continue;
    }
    // top-level scalar list item
    if (/^  - /.test(line) && curList) {
      curList.push(parseScalar(line.replace(/^  - /, '').trim()));
      i++;
      continue;
    }
    // nested mapping member (2-space indented `key: value`, not a list item)
    const nested = line.match(/^ {2}([A-Za-z0-9_]+):\s*(.*)$/);
    if (nested && curMap && !/^  - /.test(line)) {
      curMap[nested[1]] = parseScalar(nested[2]);
      i++;
      continue;
    }
    // top-level key
    const m = line.match(/^([A-Za-z0-9_]+):\s*(.*)$/);
    if (m) {
      curList = null;
      curMap = null;
      const curKey = m[1];
      const val = m[2];
      if (val === '|') {
        block = { key: curKey, lines: [] };
      } else if (val === '') {
        // could be a list or a nested mapping; decide from the next non-blank line
        let j = i + 1;
        while (j < lines.length && lines[j].trim() === '') j++;
        if (j < lines.length && /^  - /.test(lines[j])) {
          curList = [];
          out[curKey] = curList;
        } else {
          curMap = {};
          out[curKey] = curMap;
        }
      } else {
        out[curKey] = parseScalar(val);
      }
    }
    i++;
  }
  if (block) out[block.key] = block.lines.join('\n').replace(/\n+$/, '');
  return out;
}
function parseScalar(v) {
  const s = v.replace(/^["']|["']$/g, '');
  if (v === 'null') return null;
  if (v === 'true') return true;
  if (v === 'false') return false;
  if (/^-?\d+$/.test(v)) return parseInt(v, 10);
  return s;
}

function emitYaml(obj, indent = 0) {
  const pad = '  '.repeat(indent);
  let out = '';
  for (const key of Object.keys(obj)) {
    const v = obj[key];
    if (Array.isArray(v)) {
      if (v.length === 0) {
        out += `${pad}${key}: []\n`;
      } else if (typeof v[0] === 'object' && v[0] !== null) {
        out += `${pad}${key}:\n`;
        for (const item of v) {
          const inner = emitYaml(item, indent + 2);
          const innerLines = inner.replace(/\n$/, '').split('\n');
          out += `${'  '.repeat(indent + 1)}- ${innerLines[0].trimStart()}\n`;
          for (const l of innerLines.slice(1)) out += `${l}\n`;
        }
      } else {
        out += `${pad}${key}:\n`;
        for (const item of v) out += `${'  '.repeat(indent + 1)}- ${scalar(item)}\n`;
      }
    } else if (v && typeof v === 'object') {
      out += `${pad}${key}:\n${emitYaml(v, indent + 1)}`;
    } else {
      out += `${pad}${key}: ${scalar(v)}\n`;
    }
  }
  return out;
}
function scalar(v) {
  if (v === null) return 'null';
  if (typeof v === 'string') {
    if (v === '' || /[:#]/.test(v) || /^\d/.test(v)) return JSON.stringify(v);
    return v;
  }
  return String(v);
}

// ---- hashing ---------------------------------------------------------------
function sha256Dir(dir) {
  const h = createHash('sha256');
  const files = [];
  (function rec(d) {
    for (const n of readdirSync(d).sort()) {
      const p = join(d, n);
      if (statSync(p).isDirectory()) rec(p);
      else files.push(p);
    }
  })(dir);
  for (const f of files.sort()) {
    h.update(f.slice(dir.length + 1));
    h.update('\0');
    h.update(readFileSync(f));
    h.update('\0');
  }
  return 'sha256:' + h.digest('hex');
}

// ---- assemble --------------------------------------------------------------
function assemble() {
  const hard = [];
  const warn = [];
  const programs = [];
  const tagUnion = new Set();
  const moduleSystems = new Set();
  let jsCount = 0;
  let tsCount = 0;

  const dirs = readdirSync(PROGRAMS_DIR)
    .filter((d) => statSync(join(PROGRAMS_DIR, d)).isDirectory())
    .sort();

  for (const id of dirs) {
    const pdir = join(PROGRAMS_DIR, id);
    const provPath = join(pdir, 'provenance.yaml');
    const extPath = join(pdir, 'extraction.yaml');
    const srcDir = join(pdir, 'source');
    const gtDir = join(pdir, 'ground_truth');

    if (!existsSync(provPath) || !existsSync(extPath) || !existsSync(srcDir)) {
      hard.push(`${id}: missing provenance/extraction/source`);
      continue;
    }
    const prov = parseSimpleYaml(readFileSync(provPath, 'utf8'));
    const ext = parseSimpleYaml(readFileSync(extPath, 'utf8'));

    for (const req of ['source_url', 'commit_sha', 'license', 'surface', 'module_system']) {
      if (prov[req] === undefined || prov[req] === null || prov[req] === '') {
        hard.push(`${id}: provenance missing ${req}`);
      }
    }
    if (prov.license && !LICENSE_ALLOWLIST.has(prov.license)) {
      hard.push(`${id}: license ${JSON.stringify(prov.license)} not in allow-list`);
    }
    for (const gt of ['ast', 'cfg', 'callgraph', 'pdg']) {
      if (!existsSync(join(gtDir, `${gt}.json`))) {
        hard.push(`${id}: missing ground_truth/${gt}.json`);
      }
    }
    if (prov.surface === 'ts' && !existsSync(join(srcDir, 'tsconfig.json'))) {
      hard.push(`${id}: surface=ts but no tsconfig.json (DOC §7)`);
    }
    // tool-version drift
    const tv = ext.tool_versions || {};
    if (tv.node && tv.node !== PINNED_TOOLS.node) {
      hard.push(`${id}: node ${tv.node} != pinned ${PINNED_TOOLS.node}`);
    }
    if (tv.typescript_eslint && tv.typescript_eslint !== PINNED_TOOLS.typescript_eslint) {
      hard.push(`${id}: typescript_eslint ${tv.typescript_eslint} != pinned ${PINNED_TOOLS.typescript_eslint}`);
    }

    const coverage = Array.isArray(prov.construct_coverage) ? prov.construct_coverage : [];
    if (!Array.isArray(prov.construct_coverage)) {
      hard.push(`${id}: construct_coverage missing or not a list`);
    }
    for (const t of coverage) tagUnion.add(t);
    if (prov.module_system) moduleSystems.add(prov.module_system);
    if (prov.surface === 'js') jsCount++;
    if (prov.surface === 'ts') tsCount++;

    programs.push({
      id,
      source_url: prov.source_url,
      commit_sha: prov.commit_sha,
      sha256_source_tree: sha256Dir(srcDir),
      sha256_ground_truth: existsSync(gtDir) ? sha256Dir(gtDir) : null,
      license: prov.license,
      surface: prov.surface,
      module_system: prov.module_system,
      synthetic: prov.synthetic === true,
      loc: prov.loc ?? null,
      construct_coverage: coverage.slice().sort(),
      extraction_tools: {
        node: tv.node ?? null,
        typescript_eslint: tv.typescript_eslint ?? null,
        jelly: tv.jelly ?? null,
        tsc: tv.tsc ?? null,
      },
    });
  }

  // coverage gates
  const missingTags = [...REQUIRED_TAGS].filter((t) => !tagUnion.has(t)).sort();
  if (missingTags.length) hard.push(`missing construct tags: ${missingTags.join(', ')}`);
  const missingMs = [...REQUIRED_MODULE_SYSTEMS].filter((m) => !moduleSystems.has(m)).sort();
  if (missingMs.length) hard.push(`missing module systems: ${missingMs.join(', ')}`);
  if (jsCount === 0 || tsCount === 0) hard.push(`both surfaces required (js=${jsCount} ts=${tsCount})`);
  const total = jsCount + tsCount;
  if (total > 0 && (jsCount / total > 0.9 || tsCount / total > 0.9)) {
    hard.push(`surface imbalance > 90% (js=${jsCount} ts=${tsCount})`);
  }

  const lock = {
    corpus_id: CORPUS_ID,
    corpus_version: CORPUS_VERSION,
    corpus_digest: 'sha256:PENDING',
    language: 'js-ts',
    language_levels: { ecmascript: '2022', typescript: '5.x' },
    built_at: new Date().toISOString().replace(/\.\d+Z$/, 'Z'),
    built_by: BUILT_BY,
    surface_counts: { js: jsCount, ts: tsCount },
    ground_truth_method:
      'AST: @typescript-eslint/typescript-estree 6.18.0 -> one ESTree (JS+TS), ' +
      'canonical serialization (sorted keys, loc/range preserved). ' +
      'CFG: per-function statement CFG with branch/loop/await/yield edges. ' +
      'Call graph + PDG (v0.1.0): documented intraprocedural resolver in ' +
      'pipeline/extract_ground_truth.mjs; dynamic/HOF/type-informed sites tagged ' +
      '`dynamic` and EXCLUDED from gate precision/recall. v1.0.0 replaces with ' +
      'Jelly 1.4 + tsc --noEmit --declaration (CLAR-CORP-12). See README.md §3.',
    programs,
  };
  return { lock, hard, warn };
}

function canonicalDigest(lock) {
  const drop = new Set(['corpus_digest', 'built_at', 'built_by']);
  const payload = {};
  for (const k of Object.keys(lock).sort()) if (!drop.has(k)) payload[k] = lock[k];
  const canonical = JSON.stringify(sortDeep(payload));
  return 'sha256:' + createHash('sha256').update(canonical).digest('hex');
}
function sortDeep(v) {
  if (Array.isArray(v)) return v.map(sortDeep);
  if (v && typeof v === 'object') {
    const o = {};
    for (const k of Object.keys(v).sort()) o[k] = sortDeep(v[k]);
    return o;
  }
  return v;
}

function main() {
  const write = process.argv.includes('--write');
  const check = process.argv.includes('--check');
  const { lock, hard, warn } = assemble();

  for (const w of warn) process.stderr.write(`[warn] ${w}\n`);
  if (hard.length) {
    process.stderr.write('CORPUS BUILD REFUSED — DOC §7 HARD failures:\n');
    for (const e of hard) process.stderr.write(`  - ${e}\n`);
    process.exit(2);
  }

  lock.corpus_digest = canonicalDigest(lock);

  if (check) {
    if (!existsSync(LOCK_PATH)) {
      process.stderr.write('corpus.lock missing; run --write\n');
      process.exit(3);
    }
    const existing = parseLockDigest(readFileSync(LOCK_PATH, 'utf8'));
    if (existing.digest !== lock.corpus_digest) {
      process.stderr.write(
        `corpus_digest drift: recorded=${existing.digest} recomputed=${lock.corpus_digest}\n`,
      );
      process.exit(4);
    }
    process.stdout.write(`corpus.lock digest OK: ${existing.digest}\n`);
    return;
  }

  if (write) {
    writeFileSync(LOCK_PATH, emitYaml(lock));
    process.stdout.write(`wrote ${LOCK_PATH}\n`);
    process.stdout.write(`corpus_version: ${lock.corpus_version}\n`);
    process.stdout.write(`corpus_digest:  ${lock.corpus_digest}\n`);
    return;
  }
  process.stdout.write(lock.corpus_digest + '\n');
}

function parseLockDigest(text) {
  const m = text.match(/^corpus_digest:\s*(\S+)\s*$/m);
  return { digest: m ? m[1].replace(/^["']|["']$/g, '') : null };
}

main();
