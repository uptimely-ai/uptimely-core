const assert = require('node:assert/strict');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const test = require('node:test');

class MockNode {
  constructor() {
    this.children = [];
    this.textContent = '';
  }
}

class MockElement extends MockNode {
  constructor(tagName) {
    super();
    this.tagName = tagName;
    this.children = [];
    this.attributes = {};
    this.listeners = {};
    this.hidden = false;
    this.dataset = {};
    this.text = '';
  }

  set textContent(value) {
    this.text = String(value);
    this.children = [];
  }

  get textContent() {
    return this.text + this.children.map(child => child.textContent).join('');
  }

  append(...children) {
    this.children.push(...children);
  }

  appendChild(child) {
    this.append(child);
  }

  replaceChildren(...children) {
    this.text = '';
    this.children = children;
  }

  addEventListener(name, callback) {
    this.listeners[name] = callback;
  }

  setAttribute(name, value) {
    this.attributes[name] = String(value);
  }

  querySelectorAll(selector) {
    const matches = [];
    const visit = node => {
      for (const child of node.children) {
        if (selector === child.tagName) matches.push(child);
        visit(child);
      }
    };
    visit(this);
    return matches;
  }

  get childElementCount() {
    return this.children.filter(child => child instanceof MockElement).length;
  }

  click() {
    this.listeners.click?.({ preventDefault() {}, button: 0 });
  }
}

function createDocument() {
  const elements = new Map(
    ['navigation', 'content', 'load-status', 'error-status', 'scope-badge'].map(id => [
      id,
      new MockElement('div'),
    ]),
  );
  return {
    title: '',
    getElementById(id) {
      return elements.get(id);
    },
    createElement(tagName) {
      return new MockElement(tagName);
    },
    createTextNode(value) {
      const node = new MockNode();
      node.textContent = String(value);
      return node;
    },
  };
}

function sampleData() {
  return {
    format_version: 1,
    project: { name: 'Test project', spec_version: 3 },
    scope: { label: 'all features', is_scoped: false },
    catalogs: {
      configuration: {
        entities: {
          asset: {
            name: '<Asset>',
            dimensions: ['id'],
            datasets: { readings: { name: 'Readings', features: { value: {} } } },
          },
        },
        dimensions: {},
        functions: {},
      },
      summary: {
        entity_count: 1,
        dataset_count: 1,
        dimension_count: 1,
        feature_count: 1,
        function_count: 1,
      },
    },
    graphs: {
      feature_lineage: {
        nodes: [{ id: 'value', label: '<Value>', data_type: 'float' }],
        links: [],
      },
      invocation_lineage: { nodes: [], links: [] },
    },
    plan: {
      stage_count: 1,
      invocation_count: 1,
      plan_version: 1,
      function_count: 1,
      entity_count: 1,
      feature_count: 1,
      dependency_count: 0,
      max_parallel_invocations: 1,
    },
    stages: [
      {
        stage: 1,
        steps: [
          {
            position: 1,
            title: 'Calculate',
            function: 'calculate',
            function_kind: 'vectorize',
            entity: 'asset',
            dataset: 'readings',
            input_features: [],
            output_features: ['value'],
          },
        ],
      },
    ],
    animation: {
      stages: [
        [
          {
            function_label: 'Calculate',
            function: 'calculate',
            entity: 'asset',
            dataset: 'readings',
            dataset_label: 'Readings',
            action: 'calculate',
            grain: 'one row',
            dependencies: [],
            columns: [{ label: 'Value', name: 'value', role: 'Output', type: 'float' }],
          },
          {
            function_label: 'Write',
            function: 'write',
            entity: 'asset',
            dataset: 'readings',
            dataset_label: 'Readings',
            action: 'write',
            grain: 'one row',
            dependencies: ['1'],
            columns: [],
          },
        ],
      ],
    },
  };
}

async function loadFrontend(initialHash = '#overview') {
  const document = createDocument();
  const listeners = {};
  const location = { hash: initialHash };
  const window = {
    UTIMELY_EXPLORER_CONFIG: { dataUrl: '/api/explorer' },
    addEventListener(name, callback) {
      listeners[name] = callback;
    },
    clearInterval() {},
    setInterval() {
      return 1;
    },
  };
  const previousGlobals = {
    document: globalThis.document,
    fetch: globalThis.fetch,
    location: globalThis.location,
    Node: globalThis.Node,
    window: globalThis.window,
  };
  globalThis.document = document;
  globalThis.fetch = async (url, options) => {
    assert.equal(url, '/api/explorer');
    assert.deepEqual(options, { cache: 'no-store' });
    return { ok: true, json: async () => sampleData() };
  };
  globalThis.location = location;
  globalThis.Node = MockNode;
  globalThis.window = window;

  const moduleUrl = pathToFileURL(
    path.resolve(__dirname, '../../../src/uptimely/explorer/app/static/js/app.js'),
  );
  moduleUrl.searchParams.set('test', String(Math.random()));
  await import(moduleUrl.href);

  return {
    document,
    location,
    navigate(section) {
      location.hash = `#${section}`;
      listeners.hashchange();
    },
    restore() {
      for (const [name, value] of Object.entries(previousGlobals)) {
        if (value === undefined) delete globalThis[name];
        else globalThis[name] = value;
      }
    },
  };
}

test('loads the snapshot and routes between overview and plan', async () => {
  const app = await loadFrontend();
  try {
    assert.equal(app.document.title, 'Test project | Explorer');
    assert.equal(app.document.getElementById('load-status').hidden, true);
    assert.match(app.document.getElementById('content').textContent, /Plan stages/);
    assert.equal(app.document.getElementById('scope-badge').textContent, 'all features');

    app.navigate('plan');
    assert.match(app.document.getElementById('content').textContent, /Execution plan/);
    assert.match(app.document.getElementById('content').textContent, /Calculate/);
  } finally {
    app.restore();
  }
});

test('renders catalog and graph labels as text and exposes selected node details', async () => {
  const app = await loadFrontend();
  try {
    app.navigate('catalogs');
    const catalogs = app.document.getElementById('content');
    assert.match(catalogs.textContent, /<Asset>/);
    assert.equal(catalogs.querySelectorAll('script').length, 0);

    app.navigate('feature-lineage');
    const graph = app.document.getElementById('content');
    const selectNode = graph.querySelectorAll('button')[0];
    selectNode.click();
    assert.match(graph.textContent, /<Value>/);
    assert.match(graph.textContent, /Selected node/);
  } finally {
    app.restore();
  }
});

test('animation controls advance through the declared steps', async () => {
  const app = await loadFrontend();
  try {
    app.navigate('animation');
    const content = app.document.getElementById('content');
    const buttons = content.querySelectorAll('button');
    assert.match(content.textContent, /Step 1 of 2/);

    buttons[2].click();

    assert.match(content.textContent, /Step 2 of 2/);
    assert.match(content.textContent, /Write/);
  } finally {
    app.restore();
  }
});
