const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const scriptDirectory = path.resolve(__dirname, '../../../src/uptimely/explorer/app/js');

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
		for (const script of ['graph_components.js', 'view_controller.js']) {
			vm.runInContext(fs.readFileSync(path.join(scriptDirectory, script), 'utf8'), context);
		}
		vm.runInContext(`
			ExplorerGraph.showDetails = (panel, title, rows) => { panel.rows = rows; };
		`, context);
		vm.runInContext(fs.readFileSync(path.join(scriptDirectory, filename), 'utf8'), context);
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
			vm.runInContext("ExplorerGraph.humanizeDatasetName('pump_telemetry_dataset')", context),
			'Pump Telemetry Dataset',
		);
		const node = graph.properties.get('graphData').nodes[1];
		graph.properties.get('onNodeClick')(node);
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
		if (filename === 'invocation_lineage.js') {
			assert.deepEqual([...nodes2D].map(node => node.x), [0, 360, 720, 1080]);
			assert.ok(nodes2D.every(node => node.y === 0));
			assert.equal(graph2D.fitCalls.at(-1)[1], 140);
		} else {
			assert.equal(graph2D.fitCalls.at(-1)[1], 80);
		}
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
		const selectedColor = filename === 'invocation_lineage.js'
			? '#abcdef'
			: '#fb7185';
		assert.deepEqual(strokes, [[selectedColor, 3]]);
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
			element('reset-graph').listeners.click();
			assert.equal(activeGraph.fitCalls.length, fitCount + 1);
			assert.equal(activeGraph.fitCalls.at(-1)[0], 600);
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
			buttons[1 - index].listeners.click();
			assert.ok([...graph.objects.values()].every(object => object.scale.value === undefined));
		}
	});
}

test('shared card sizing preserves width bounds', () => {
	const context = vm.createContext({});
	vm.runInContext(fs.readFileSync(path.join(scriptDirectory, 'graph_components.js'), 'utf8'), context);
	const dimensions = vm.runInContext(`
		['a', 'selected', 'x'.repeat(100)].map(label => {
			const node = {};
			ExplorerGraph.sizeCard(node, label);
			return [node.cardWidth, node.cardHeight];
		});
	`, context);
	assert.deepEqual(Array.from(dimensions, value => Array.from(value)), [
		[112, 38], [116, 38], [280, 38],
	]);
});
