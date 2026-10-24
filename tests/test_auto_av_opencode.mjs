import assert from 'node:assert/strict';
import { createProtocol, snapshot, automaticPrompt } from '../opencode/plugins/auto-av-v2/protocol.js';
const user = (id, text = 'request', metadata) => ({ type: 'user', id, text, metadata });
const answer = text => ({ type: 'assistant', content: [{ type: 'text', text }] });
const report = 'Full draft\nwith details'.padEnd(301, '.');
const history = [user('u1'), answer(report)];
const p = createProtocol('POLICY', 'CANONICAL\nBODY');
const entry = p.begin('s1', history);
assert.equal(p.begin('s1', history), undefined);
assert.equal(p.selectorPrompt(entry), 'POLICY\n\n'+JSON.stringify({ assignment: 'request', draft: report }));
assert.equal(p.finish('s1', entry, 'SKIP', history), undefined);
assert.ok(p.finish('s1', entry, 'APPLY', history).startsWith('CANONICAL\nBODY\n'));
assert.equal(p.begin('s1', [...history, user('synthetic', 'av', { 'auto-av': true }), answer('revised')]), undefined);
assert.ok(p.begin('s1', [...history, user('u2'), answer('later'.padEnd(301, '.'))]));
assert.equal(p.finish('s1', entry, 'APPLY', history), undefined);
const q = createProtocol('POLICY', 'BODY');
const other = q.begin('other', history);
assert.throws(() => q.finish('other', other, 'x'.repeat(2049), history), /invalid or oversized/);
assert.throws(() => q.finish('other', other, '{"completion":true}', history), /invalid or oversized/);
assert.equal(q.finish('other', other, 'APPLY', [...history, user('new'), answer('new')]), undefined);
q.clear('other', other);
assert.equal(q.finish('other', other, 'APPLY', history), undefined);
assert.equal(snapshot([user('empty'), answer('')]), undefined);
assert.equal(snapshot([answer('unowned')]), undefined);
console.log('OpenCode v2 protocol tests passed (routing, isolation, exact body, replay, later user, stale, invalid, empty).');

const skipped = createProtocol('POLICY', 'BODY');
const first = skipped.begin('s', history);
assert.equal(skipped.finish('s', first, 'SKIP', history), undefined);
skipped.clear('s', first);
assert.equal(skipped.begin('s', history), undefined);
assert.ok(skipped.begin('s', [user('u1'), answer('New analysis after foreign continuation'.padEnd(301, '.'))]));
const wrapped = automaticPrompt('---\ndescription: operator only\n---\n\nSTANCE\n$ARGUMENTS\n', { request: 'TASK', draft: 'DRAFT' });
assert.ok(wrapped.startsWith('STANCE\n'));
assert.ok(!wrapped.includes('$ARGUMENTS'));
assert.ok(!wrapped.includes('operator only'));
assert.ok(wrapped.includes('TASK'));
console.log('SKIP changed-draft selection and canonical frontmatter/placeholder tests passed.');

p.dispose('s1');
assert.ok(p.begin('s1',history));
console.log('Stateless selector prompt and session disposal tests passed.');

const boundary = createProtocol('POLICY', 'BODY');
const shortCases = [
  'I found the logging issue. The logger was configured after the first request.',
  'a'.repeat(300),
  '😀'.repeat(300),
  'a'.repeat(149) + '\n' + 'b'.repeat(150),
];
for (const draft of shortCases) {
  assert.equal(boundary.begin('boundary', [user('same'), answer(draft)]), undefined);
}
const longDraft = '😀'.repeat(301);
const longHistory = [user('same'), answer(longDraft)];
const longEntry = boundary.begin('boundary', longHistory);
assert.ok(longEntry);
assert.ok(boundary.finish('boundary', longEntry, 'APPLY', longHistory));
const stale = createProtocol('POLICY', 'BODY');
const oldEntry = stale.begin('stale', history);
assert.equal(stale.finish('stale', oldEntry, 'APPLY', [user('u1'), answer('short')]), undefined);
assert.equal(stale.begin('stale', [user('u1'), answer('short')]), undefined);
assert.equal(stale.finish('stale', oldEntry, 'APPLY', history), undefined);
const replacement = stale.begin('stale', history);
assert.ok(replacement);
assert.ok(stale.finish('stale', replacement, 'APPLY', history));
assert.ok(createProtocol('POLICY', 'BODY').begin('multiline', [user('u1'), answer('a'.repeat(150) + '\n' + 'b'.repeat(150))]));
console.log('300/301 raw Unicode and multiline boundaries, short-to-long eligibility, and stale short-draft suppression passed.');

for (const draft of ['', ' ', '\n'.repeat(301)]) {
  const replacementHistory = [user('u1'), answer(draft)];
  for (const viaBegin of [true, false]) {
    const pending = createProtocol('POLICY', 'BODY');
    const obsolete = pending.begin('pending', history);
    if (viaBegin) assert.equal(pending.begin('pending', replacementHistory), undefined);
    else assert.equal(pending.finish('pending', obsolete, 'APPLY', replacementHistory), undefined);
    assert.equal(pending.finish('pending', obsolete, 'APPLY', history), undefined);
    const fresh = pending.begin('pending', history);
    assert.ok(fresh);
    assert.ok(pending.finish('pending', fresh, 'APPLY', history));
  }
}
console.log('Empty/whitespace replacement invalidates pending selection and preserves fresh eligibility.');
