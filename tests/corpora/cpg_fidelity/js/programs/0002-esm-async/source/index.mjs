// CMP-CORP-CPG-js synthesized program 0002
// Coverage: module-system-esm, async-await
function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function fetchValue(key) {
  await delay(1);
  return key.length;
}

async function fetchAll(keys) {
  const out = [];
  for (const k of keys) {
    const v = await fetchValue(k);
    out.push(v);
  }
  return out;
}

export async function run(keys) {
  const values = await fetchAll(keys);
  return values.reduce((a, b) => a + b, 0);
}

export { fetchValue, fetchAll };
