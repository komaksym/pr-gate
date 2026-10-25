const assert = require('node:assert/strict');
const fs = require('node:fs');
const test = require('node:test');

const workflow = fs.readFileSync('.github/workflows/pr-visual.yml', 'utf8');
const source = workflow.split('          script: |\n')[1].split('\n').map(line => line.slice(12)).join('\n');
const execute = new (Object.getPrototypeOf(async function () {}).constructor)('github', 'context', 'core', source);
const sha = 'a'.repeat(40);
const image = '![Infographic](https://github.com/owner/repo/blob/topic/visual/infographic.png?raw=true)';

async function check(body, options = {}) {
  const failures = [];
  const requests = [];
  const github = { rest: {
    pulls: { get: async () => ({ data: { body, head: { sha, ref: 'topic', repo: { full_name: 'owner/repo' } } } }) },
    repos: { getContent: async (request) => {
      requests.push(request);
      if (options.missing) throw new Error('Not Found');
      return { data: { type: 'file', encoding: 'base64', content: Buffer.from(options.invalid ? 'text' : '\x89PNG\r\n\x1a\n', 'latin1').toString('base64') } };
    } },
  } };
  await execute(github, { repo: { owner: 'owner', repo: 'repo' }, payload: { pull_request: { number: 1, body: image } } }, {
    setFailed: message => failures.push(message), info: () => {},
  });
  return { failures, requests };
}

test('fetches the current body and rejects a removed image', async () => {
  assert.equal((await check('No image')).failures.length, 1);
});
test('accepts a PNG that exists on the current PR head', async () => {
  const result = await check(image);
  assert.deepEqual(result.failures, []);
  assert.equal(result.requests[0].ref, sha);
});
test('rejects stale branches, foreign repositories, and forged hosts', async () => {
  for (const url of [image.replace('/topic/', '/old/'), image.replace('owner/repo', 'other/repo'), image.replace('github.com/', 'github.com.evil/')]) {
    assert.equal((await check(url)).failures.length, 1);
  }
});
test('rejects missing files and text disguised as a PNG', async () => {
  assert.equal((await check(image, { missing: true })).failures.length, 1);
  assert.equal((await check(image, { invalid: true })).failures.length, 1);
});
test('ignores Markdown inside code fences and comments', async () => {
  for (const body of ['```md\n' + image + '\n```', '<!-- ' + image + ' -->']) {
    assert.equal((await check(body)).failures.length, 1);
  }
});
