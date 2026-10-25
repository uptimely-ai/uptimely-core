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

for (const filename of ['feature_graph.js', 'invocation_graph.js']) {
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
				function_id: id, operation: 'read', entity: 'test',
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
			assert.equal(object.material.color.value, '#ff9f43');
			assert.equal(object.children[1].text, id);
			assert.equal(object.children[1].position.y, 14);
		}
		assert.equal(element('entity-legend').children[0].textContent, 'test');
		const node = graph.properties.get('graphData').nodes[1];
		graph.properties.get('onNodeClick')(node);
		assert.deepEqual(
			[...graph.objects.values()].map(object => object.material.color.value),
			['#67e8f9', '#f8d66d', '#67e8f9', '#46545f'],
		);
		for (const link of graph.properties.get('graphData').links) {
			assert.equal(graph.properties.get('linkColor')(link), '#67e8f9');
			assert.equal(graph.properties.get('linkWidth')(link), 1.5);
		}
		const graph2D = graphs.get('2d');
		for (const link of graph2D.properties.get('graphData').links) {
			assert.equal(graph2D.properties.get('linkColor')(link), '#67e8f9');
		}
		buttons[0].listeners.click();
		assert.equal(buttons[0].attributes['aria-pressed'], 'true');
		buttons[1].listeners.click();
		assert.equal(graph.objects.get('selected').material.color.value, '#f8d66d');
		graph.properties.get('onNodeClick')(graph.properties.get('graphData').nodes[3]);
		assert.deepEqual(
			[...graph.objects.values()].map(object => object.material.color.value),
			['#46545f', '#46545f', '#46545f', '#f8d66d'],
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
			assert.ok([...graph.objects.values()].every(
				object => object.material.color.value === '#ff9f43'));
			const details = element(filename === 'feature_graph.js'
				? 'node-details' : 'invocation-node-details');
			assert.equal(details.rows.length, 0);
			buttons[1 - index].listeners.click();
			assert.ok([...graph.objects.values()].every(object => object.scale.value === undefined));
		}
	});
}
