const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const scriptDirectory = path.resolve(__dirname, '../../../src/uptimely/explorer/app/js');

function loadLineageScript(context, filename) {
	let source = fs.readFileSync(path.join(scriptDirectory, filename), 'utf8');
	if (filename === 'lineage_config.js') {
		const exports = [...source.matchAll(/^export const (\w+)/gm)]
			.map(([, name]) => name);
		source = source.replace(/^export /gm, '');
		source += `\nglobalThis.LineageConfig = { ${exports.join(', ')} };`;
	} else if (filename === 'lineage_layout.js') {
		source = source.replace(
			/^import \{([\s\S]*?)\} from '\.\/lineage_config\.js';/m,
			'const {$1} = globalThis.LineageConfig;',
		);
		source = source.replace(
			/export \{([\s\S]*?)\};\s*$/,
			'globalThis.LineageLayout = {$1};',
		);
	} else if (filename === 'lineage_components.js') {
		source = source.replace(
			/^import \* as LineageConfig from '\.\/lineage_config\.js';\nimport \* as LineageLayout from '\.\/lineage_layout\.js';/m,
			'const LineageConfig = globalThis.LineageConfig;\nconst LineageLayout = globalThis.LineageLayout;',
		);
		source = source.replace(
			/export \{ ExplorerLineage \};/,
			'globalThis.ExplorerLineage = ExplorerLineage;',
		);
	} else if (filename === 'lineage_view_controller.js') {
		source = source.replace(/^export function /gm, 'function ');
		source += '\nglobalThis.mountLineageViews = mountLineageViews;';
	} else {
		source = source.replace(
			/^import \{ (?:ExplorerLineage|mountLineageViews) \} from '\.\/[^']+';\n/gm,
			'',
		);
	}
	vm.runInContext(`{\n${source}\n}`, context, { filename });
}

function loadLineageDependencies(context) {
	for (const script of ['lineage_config.js', 'lineage_layout.js', 'lineage_components.js']) {
		loadLineageScript(context, script);
	}
}

function createElement() {
	return {
		clientWidth: 1200, clientHeight: 800, hidden: false, textContent: '',
		children: [],
		listeners: {}, attributes: {}, dataset: {},
		classList: { toggle() {} }, style: { setProperty() {} },
		addEventListener(name, callback) { this.listeners[name] = callback; },
		setAttribute(name, value) { this.attributes[name] = value; },
		append(child) { this.children.push(child); }, replaceChildren() {},
	};
}

function createGraph(dimension) {
	const properties = new Map();
	const objects = new Map();
	const fitCalls = [];
	const forces = new Map();
	let graph;
	const render = () => {
		objects.clear();
		for (const node of properties.get('graphData')?.nodes || []) {
			if (dimension === '3d') objects.set(node.id, properties.get('nodeThreeObject')(node));
		}
	};
	graph = new Proxy({ properties, objects, fitCalls, forces }, {
		get(target, key) {
			if (key in target) return target[key];
			// force-graph 1.52 has no refresh method; 3d-force-graph does.
			if (key === 'refresh') return dimension === '3d' ? render : undefined;
			if (key === 'zoomToFit') return (...args) => {
				fitCalls.push(args);
				return graph;
			};
			if (key === 'd3Force') return name => {
				if (!forces.has(name)) forces.set(name, {
					strength(value) { this.strengthValue = value; return this; },
					distanceMax(value) { this.distanceMaxValue = value; return this; },
					distance(value) { this.distanceValue = value; return this; },
				});
				return forces.get(name);
			};
			return (...args) => {
				if (!args.length) return properties.get(key);
				properties.set(key, args[0]);
				properties.set(`${key}Arguments`, args);
				if (key === 'graphData') {
					const data = args[0];
					for (const link of data.links) {
						link.source = data.nodes.find(node => node.id === link.source);
						link.target = data.nodes.find(node => node.id === link.target);
					}
					render();
				}
				return graph;
			};
		},
	});
	return graph;
}

for (const filename of ['feature_lineage.js', 'invocation_lineage.js']) {
	test(`${filename}: 3D clicks highlight both directions after creating the 2D view`, () => {
		const elements = new Map();
		const element = id => {
			if (!elements.has(id)) elements.set(id, createElement());
			return elements.get(id);
		};
		const buttons = ['2d', '3d'].map(dimension => {
			const button = createElement();
			button.dataset.dimension = dimension;
			return button;
		});
		element('graph-data').textContent = JSON.stringify({
			nodes: ['before', 'selected', 'after', 'unrelated'].map((id, index) => ({
				id, label: id, label_lines: [id], stage: index + 1,
				function_id: id, function_kind: 'read', entity: 'test', dataset_id: id,
			})),
			links: [
				{ source: 'before', target: 'selected' },
				{ source: 'selected', target: 'after' },
			],
		});
		element('graph-style').textContent = JSON.stringify({
			function_colors: { read: '#abcdef' }, link_width: 0.5, link_color: '#8fa3b5',
			feature_node_size: 5, function_node_size: 12, node_rel_size: 5, node_resolution: 12,
			link_distance: 30, charge_strength: -75, charge_distance_max: 110,
			arrow_length: 4, arrow_rel_pos: 1,
		});
		const graphs = new Map();
		const context = vm.createContext({
			document: {
				getElementById: element, createElement,
				querySelectorAll: selector => selector === '[data-dimension]' ? buttons : [],
			},
			window: { addEventListener() {} },
			ResizeObserver: class { observe() {} },
			console,
			SpriteText: class {
				constructor(text) {
					this.text = text;
					this.position = { set(x, y, z) { this.x = x; this.y = y; this.z = z; } };
				}
			},
			ForceGraph: () => () => {
				const graph = createGraph('2d');
				graphs.set('2d', graph);
				return graph;
			},
			ForceGraph3D: () => () => {
				const graph = createGraph('3d');
				graphs.set('3d', graph);
				return graph;
			},
			THREE: {
				Group: class {
					constructor() { this.children = []; }
					add(child) {
						this.children.push(child);
						if (child.isMesh) {
							this.material = child.material;
							this.geometry = child.geometry;
							this.scale = child.scale;
						}
					}
					traverse(callback) { this.children.forEach(child => callback(child)); }
				},
				MeshLambertMaterial: class {
					constructor({ color }) {
						this.color = { value: color, set(value) { this.value = value; } };
					}
				},
				SphereGeometry: class {
					constructor(radius, widthSegments, heightSegments) {
						this.parameters = { radius, widthSegments, heightSegments };
					}
				},
				OctahedronGeometry: class {},
				Mesh: class {
					constructor(geometry, material) {
						this.isMesh = true;
						this.geometry = geometry;
						this.material = material;
						this.scale = { setScalar(value) { this.value = value; } };
					}
					traverse(callback) { callback(this); }
				},
			},
		});
		loadLineageDependencies(context);
		loadLineageScript(context, 'lineage_view_controller.js');
		vm.runInContext(`
			ExplorerLineage.showDetails = (panel, title, rows) => { panel.rows = rows; };
		`, context);
		loadLineageScript(context, filename);
		buttons[1].listeners.click();
		assert.equal(buttons[1].attributes['aria-pressed'], 'true');
		const graph = graphs.get('3d');
		assert.equal(graph.forces.get('link').distanceValue, 30);
		assert.equal(graph.forces.get('charge').strengthValue, -75);
		assert.equal(graph.forces.get('charge').distanceMaxValue, 110);
		assert.equal(graph.properties.get('nodeRelSize'), 5);
		assert.equal(graph.properties.get('nodeResolution'), 12);
		assert.equal(graph.properties.get('linkDirectionalArrowLength'), 4);
		assert.equal(graph.properties.get('linkDirectionalArrowRelPos'), 1);
		for (const [id, object] of graph.objects) {
			assert.deepEqual(object.geometry.parameters, {
				radius: 5, widthSegments: 16, heightSegments: 12,
			});
			assert.equal(object.children[1].text, id);
			assert.equal(object.children[1].position.y, 14);
			assert.equal(object.material.color.value, {
				before: '#2dd4bf', selected: '#fb7185', after: '#ff9f43', unrelated: '#a78bfa',
			}[id]);
		}
		assert.equal(element('dataset-legend').children[0].textContent, 'After');
		assert.equal(
			vm.runInContext("ExplorerLineage.humanizeDatasetName('pump_telemetry_dataset')", context),
			'Pump Telemetry Dataset',
		);
		const node = graph.properties.get('graphData').nodes[1];
		graph.properties.get('onNodeClick')(node);
		if (filename === 'invocation_lineage.js') {
			assert.deepEqual(
				Array.from(element('invocation-node-details').rows.slice(0, 2), row => Array.from(row)),
				[['Dataset', 'selected'], ['Stage', 2]],
			);
		}
		assert.deepEqual(
			[...graph.properties.get('graphData').nodes].map(graph.properties.get('nodeColor')),
			['#2dd4bf', '#fb7185', '#ff9f43', '#46545f'],
		);
		assert.deepEqual(
			[...graph.objects.values()].map(object => object.material.color.value),
			['#2dd4bf', '#fb7185', '#ff9f43', '#46545f'],
		);
		for (const link of graph.properties.get('graphData').links) {
			assert.equal(graph.properties.get('linkColor')(link), '#67e8f9');
			assert.equal(graph.properties.get('linkWidth')(link), 1.5);
		}
		const graph2D = graphs.get('2d');
		const nodes2D = graph2D.properties.get('graphData').nodes;
		assert.deepEqual([...nodes2D].map(node => node.cardWidth), [112, 116, 112, 124]);
		assert.ok(nodes2D.every(node => node.cardHeight === 38));
		assert.ok(nodes2D[0].x < nodes2D[1].x && nodes2D[1].x < nodes2D[2].x);
		assert.equal(new Set(nodes2D.map(node => node.y)).size, 4);
		assert.deepEqual(graph2D.properties.get('centerAtArguments'),
			[0, filename === 'invocation_lineage.js' ? -24 : 0, 600]);
		assert.ok(graph2D.properties.get('zoom') > 0);
		const rectangles = [];
		const labels = [];
		const fills = [];
		const strokes = [];
		const canvas = {
			save() {}, restore() {}, beginPath() {},
			roundRect(...args) { rectangles.push(args); },
			fill() { fills.push(this.fillStyle); },
			stroke() { strokes.push([this.strokeStyle, this.lineWidth]); },
			fillText(...args) { labels.push([...args, this.fillStyle, this.font]); },
		};
		const selected2D = nodes2D[1];
		graph2D.properties.get('nodeCanvasObject')(selected2D, canvas);
		const left = selected2D.x - selected2D.cardWidth / 2;
		assert.deepEqual(rectangles[0], [
			left,
			selected2D.y - selected2D.cardHeight / 2,
			selected2D.cardWidth,
			selected2D.cardHeight,
			12,
		]);
		assert.deepEqual(rectangles[1], filename === 'invocation_lineage.js'
			? [left + 12, selected2D.y - 6, 12, 12, 3]
			: [left + 13, selected2D.y - 9, 4, 18, 2]);
		const selectedColor = '#fb7185';
		assert.deepEqual(strokes, [['#f8d66d', 3]]);
		assert.deepEqual(fills, [
			filename === 'invocation_lineage.js' ? '#1a2732' : '#172a35', selectedColor,
		]);
		assert.deepEqual(labels, [[
			'selected', left + 34, selected2D.y, 70, '#e8edf2', '600 12px "DM Sans", sans-serif',
		]]);
		rectangles.length = labels.length = fills.length = strokes.length = 0;
		graph2D.properties.get('nodeCanvasObject')(nodes2D[3], canvas);
		assert.deepEqual(strokes, [['#46545f', 1.5]]);
		assert.deepEqual(fills, ['#121c24', '#46545f']);
		assert.equal(labels[0][4], 'rgba(232, 237, 242, .3)');
		for (const link of graph2D.properties.get('graphData').links) {
			assert.equal(graph2D.properties.get('linkColor')(link), '#67e8f9');
		}

		buttons[0].listeners.click();
		assert.equal(buttons[0].attributes['aria-pressed'], 'true');
		buttons[1].listeners.click();
		assert.equal(graph.objects.get('selected').material.color.value, '#fb7185');
		graph.properties.get('onNodeClick')(graph.properties.get('graphData').nodes[3]);
		assert.deepEqual(
			[...graph.objects.values()].map(object => object.material.color.value),
			['#46545f', '#46545f', '#46545f', '#a78bfa'],
		);
		for (const link of graph.properties.get('graphData').links) {
			assert.equal(graph.properties.get('linkColor')(link), '#46545f');
			assert.equal(graph.properties.get('linkWidth')(link), 0.5);
		}
		for (const [index, dimension] of ['2d', '3d'].entries()) {
			graph.properties.get('onNodeClick')(node);
			buttons[index].listeners.click();
			const activeGraph = graphs.get(dimension);
			const fitCount = activeGraph.fitCalls.length;
			element('reset-lineage').listeners.click();
			if (dimension === '2d') {
				assert.deepEqual(activeGraph.properties.get('centerAtArguments'),
					[0, filename === 'invocation_lineage.js' ? -24 : 0, 600]);
			} else {
				assert.equal(activeGraph.fitCalls.length, fitCount + 1);
				assert.equal(activeGraph.fitCalls.at(-1)[0], 600);
			}
			assert.equal(buttons[index].attributes['aria-pressed'], 'true');
			for (const viewGraph of graphs.values()) {
				for (const link of viewGraph.properties.get('graphData').links) {
					assert.equal(viewGraph.properties.get('linkColor')(link), '#8fa3b5');
					assert.equal(viewGraph.properties.get('linkWidth')(link), 0.5);
				}
			}
			assert.ok([...graph.objects.values()].every(object => object.scale.value === undefined));
			assert.deepEqual([...graph.objects.values()].map(object => object.material.color.value),
				['#2dd4bf', '#fb7185', '#ff9f43', '#a78bfa']);
			const details = element(filename === 'feature_lineage.js'
				? 'node-details' : 'invocation-node-details');
			assert.equal(details.rows.length, 0);
			for (const node2D of nodes2D) {
				strokes.length = 0;
				graph2D.properties.get('nodeCanvasObject')(node2D, canvas);
				assert.equal(strokes[0][0], node2D.datasetColor);
				assert.equal(strokes[0][0], graph.objects.get(node2D.id).material.color.value);
			}
			buttons[1 - index].listeners.click();
			assert.ok([...graph.objects.values()].every(object => object.scale.value === undefined));
		}
	});
}

test('shared card sizing preserves width bounds', () => {
	const context = vm.createContext({});
	loadLineageDependencies(context);
	const dimensions = vm.runInContext(`
		const nodes = ['a', 'selected', 'x'.repeat(100)]
			.map((label, index) => ({ id: String(index), label, dataset_id: 'test' }));
		ExplorerLineage.prepareDatasetLayout({ nodes, links: [] }, () => 0, node => node.label);
		nodes.map(node => [node.cardWidth, node.cardHeight]);
	`, context);
	assert.deepEqual(Array.from(dimensions, value => Array.from(value)), [
		[112, 38], [116, 38], [280, 38],
	]);
});

function datasetLayout(filename, nodes, links) {
	const graph = createGraph('2d');
	let view;
	const container = createElement();
	const elements = new Map();
	const element = id => {
		if (!elements.has(id)) elements.set(id, createElement());
		return elements.get(id);
	};
	element('graph-data').textContent = JSON.stringify({ nodes, links });
	element('graph-style').textContent = JSON.stringify({
		link_color: '#8fa3b5', function_color: '#abcdef',
		function_colors: { read: '#abcdef' },
	});
	const context = vm.createContext({
		document: { getElementById: element, createElement },
		ForceGraph: () => () => graph,
		performance: { now: () => 1100 },
		mountLineageViews(data, create2D) { view = create2D(container, data, () => {}); },
	});
	loadLineageDependencies(context);
	loadLineageScript(context, filename);
	const rectangles = [];
	const labels = [];
	const paths = [];
	const canvas = {
		save() {}, restore() {}, fill() {}, stroke() {}, closePath() {},
		beginPath() { paths.push([]); },
		moveTo(x, y) { paths.at(-1).push([x, y]); },
		lineTo(x, y) { paths.at(-1).push([x, y]); },
		arc(...values) { assert.ok(values.every(Number.isFinite)); },
		fillRect(...values) { rectangles.push(values); },
		fillText(...values) { labels.push(values); },
	};
	graph.properties.get('onRenderFramePre')(canvas, 1);
	return {
		graph, view, container, nodes: graph.properties.get('graphData').nodes,
		rectangles, labels: labels.filter(label => !/^Stage \d+$/.test(label[0])),
		stageLabels: labels.filter(label => /^Stage \d+$/.test(label[0])), paths, canvas,
	};
}

for (const filename of ['feature_lineage.js', 'invocation_lineage.js']) {
	test(`${filename}: dataset lanes preserve global ranks and deterministic connectivity ordering`, () => {
		const nodes = [
			{ id: 'a', dataset_id: 'a_source', stage: 1 },
			{ id: 'z', dataset_id: 'a_source', stage: 1 },
			{ id: 'a_action', dataset_id: 'z_output', stage: 2 },
			{ id: 'z_action', dataset_id: 'z_output', stage: 2 },
			{ id: 'result', dataset_id: 'a_source', stage: 3 },
			{ id: 'other', dataset_id: 'b_isolated', stage: 1 },
			{ id: 'missing', stage: 1 },
		].map(node => ({ ...node, label: node.id, function_id: node.id, function_kind: 'read' }));
		const links = [
			{ source: 'a', target: 'z_action' },
			{ source: 'z', target: 'a_action' },
			{ source: 'a_action', target: 'result' },
			{ source: 'z_action', target: 'result' },
		];
		const layout = datasetLayout(filename, nodes, links);
		assert.deepEqual(layout.labels, []);
		const datasetOrder = ['a_source', 'z_output', 'b_isolated', 'Unassigned'];
		const byId = new Map(layout.nodes.map(node => [node.id, node]));
		assert.equal(byId.get('a').rank, 0);
		assert.equal(byId.get('z_action').rank, 1);
		assert.equal(byId.get('result').rank, 2);
		assert.equal(byId.get('missing').x, byId.get('a').x);
		assert.ok(byId.get('z_action').y < byId.get('a_action').y);
		for (const link of layout.graph.properties.get('graphData').links) {
			assert.ok(link.source.x + link.source.cardWidth / 2 < link.target.x - link.target.cardWidth / 2);
			layout.paths.length = 0;
			layout.graph.properties.get('linkCanvasObject')(link, layout.canvas, 1);
			assert.ok(layout.paths[0].flat().every(Number.isFinite));
		}
		for (const node of layout.nodes) {
			const laneIndex = datasetOrder.indexOf(node.dataset_id);
			const [left, top, width, height] = layout.rectangles[laneIndex];
			assert.ok(node.x - node.cardWidth / 2 >= left);
			assert.ok(node.x + node.cardWidth / 2 <= left + width);
			assert.ok(node.y - node.cardHeight / 2 > top + 36);
			assert.ok(node.y + node.cardHeight / 2 < top + height);
			assert.equal(node.x, node.fx);
			assert.equal(node.y, node.fy);
		}
		const shuffled = datasetLayout(filename, [...nodes].reverse(), [...links].reverse());
		assert.deepEqual(
			[...layout.nodes].map(node => [node.id, node.x, node.y]).sort(),
			[...shuffled.nodes].map(node => [node.id, node.x, node.y]).sort(),
		);
	});

	test(`${filename}: long-edge routes avoid intervening cards`, () => {
		const nodes = ['start', 'middle', 'end'].map((id, index) => ({
			id, label: id, function_id: id, stage: index + 1, dataset_id: 'shared',
		}));
		const layout = datasetLayout(filename, nodes, [
			{ source: 'start', target: 'middle' },
			{ source: 'middle', target: 'end' },
			{ source: 'start', target: 'end' },
		]);
		for (const link of layout.graph.properties.get('graphData').links) {
			layout.paths.length = 0;
			layout.graph.properties.get('linkCanvasObject')(link, layout.canvas, 1);
			const route = layout.paths[0];
			assert.ok(route.flat().every(Number.isFinite));
			if (link.target.rank - link.source.rank === 1) {
				assert.equal(route.length, 2);
				continue;
			}
			assert.ok(route.length > 2);
			const middle = layout.nodes.find(node => node.id === 'middle');
			for (let index = 1; index < route.length; index++) {
				for (let step = 0; step <= 100; step++) {
					const t = step / 100;
					const x = route[index - 1][0] * (1 - t) + route[index][0] * t;
					const y = route[index - 1][1] * (1 - t) + route[index][1] * t;
					assert.equal(
						x > middle.x - middle.cardWidth / 2 && x < middle.x + middle.cardWidth / 2
							&& y > middle.y - middle.cardHeight / 2 && y < middle.y + middle.cardHeight / 2,
						false,
					);
				}
			}
		}
	});

	test(`${filename}: empty and unassigned graphs fit headers and gutters`, () => {
		const empty = datasetLayout(filename, [], []);
		assert.deepEqual(empty.rectangles, []);
		empty.view.fit();
		assert.ok(Number.isFinite(empty.graph.properties.get('zoom')));
		const layout = datasetLayout(filename, [{
			id: 'one', label: 'One', function_id: 'One', stage: 1,
		}], []);
		assert.deepEqual(layout.labels, []);
		assert.equal(layout.nodes[0].dataset_id, 'Unassigned');
		const [left, top, width, height] = layout.rectangles[0];
		const assertFits = () => {
			const zoom = layout.graph.properties.get('zoom');
			const headerHeight = filename === 'invocation_lineage.js' ? 48 : 0;
			assert.ok(zoom > 0);
			assert.ok(width * zoom <= layout.container.clientWidth - 160);
			assert.ok((height + headerHeight) * zoom <= layout.container.clientHeight - 160);
			assert.equal(left + width / 2, 0);
			assert.equal(top + height / 2, 0);
		};
		layout.graph.properties.get('onEngineStop')();
		assertFits();
		assert.equal(layout.graph.properties.get('centerAtArguments')[2], 0);
		layout.view.fit();
		assertFits();
		assert.equal(layout.graph.properties.get('centerAtArguments')[2], 600);
		layout.container.clientWidth = 640;
		layout.container.clientHeight = 480;
		layout.view.resize();
		assertFits();
	});
}

test('invocation lanes use execution stages, not inferred dependency depths', () => {
	const layout = datasetLayout('invocation_lineage.js', [
		{ id: 'first', function_id: 'same_function', dataset_id: 'a', stage: 1 },
		{ id: 'later', function_id: 'same_function', dataset_id: 'b', stage: 4 },
		{ id: 'last', function_id: 'last', dataset_id: 'a', stage: 7 },
	], [
		{ source: 'first', target: 'later' },
		{ source: 'later', target: 'last' },
	]);
	assert.deepEqual([...layout.nodes].map(node => node.rank), [0, 3, 6]);
	assert.deepEqual(layout.stageLabels.map(label => label[0]), ['Stage 1', 'Stage 4', 'Stage 7']);
	layout.stageLabels.forEach((label, index) => {
		assert.equal(label[1], layout.nodes[index].x);
		assert.ok(label[2] < layout.rectangles[0][1]);
	});
	assert.ok(layout.nodes[0].x < layout.nodes[1].x && layout.nodes[1].x < layout.nodes[2].x);
	for (const link of layout.graph.properties.get('graphData').links) {
		layout.graph.properties.get('linkCanvasObject')(link, layout.canvas, 1);
		assert.ok(layout.paths.every(route => route.flat().every(Number.isFinite)));
	}
});

test('invocation stage columns span dataset rows and contain their cards', () => {
	const layout = datasetLayout('invocation_lineage.js', [
		{ id: 'a', function_id: 'a', dataset_id: 'first', stage: 1 },
		{ id: 'b', function_id: 'long_function_name', dataset_id: 'second', stage: 1 },
		{ id: 'c', function_id: 'c', dataset_id: 'second', stage: 2 },
	], [{ source: 'a', target: 'c' }, { source: 'b', target: 'c' }]);
	assert.deepEqual(layout.stageLabels.map(label => label[0]), ['Stage 1', 'Stage 2']);
	assert.equal(layout.nodes[0].x, layout.nodes[1].x);
	assert.notEqual(layout.nodes[0].y, layout.nodes[1].y);
	const verticals = layout.paths.flatMap(route => {
		const lines = [];
		for (let index = 1; index < route.length; index += 2) {
			if (route[index - 1][0] === route[index][0]) {
				lines.push([route[index][0], route[index - 1][1], route[index][1]]);
			}
		}
		return lines;
	});
	assert.equal(verticals.length, 3);
	const boundaries = verticals.map(line => line[0]);
	for (const node of layout.nodes) {
		const stage = node.stage - 1;
		assert.ok(node.x - node.cardWidth / 2 > boundaries[stage]);
		assert.ok(node.x + node.cardWidth / 2 < boundaries[stage + 1]);
	}
	const [, firstTop] = layout.rectangles[0];
	const [, lastTop, , lastHeight] = layout.rectangles[1];
	for (const [, top, bottom] of verticals) {
		assert.equal(top, firstTop - 48);
		assert.equal(bottom, lastTop + lastHeight);
	}
	assert.equal(layout.rectangles.length, 3);
});
