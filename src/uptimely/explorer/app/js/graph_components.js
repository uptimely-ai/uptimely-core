const ExplorerGraph = (() => {
	function readPayload(id) {
		return JSON.parse(document.getElementById(id).textContent);
	}

	function tooltip(text) {
		const element = document.createElement('div');
		element.className = 'graph-tooltip';
		element.textContent = text;
		return element;
	}

	function showDetails(panel, title, rows, summary = '') {
		const heading = document.createElement('h2');
		heading.textContent = title;
		panel.replaceChildren(heading);
		for (const [label, value] of rows) {
			const row = document.createElement('div');
			row.className = 'meta';
			const name = document.createElement('strong');
			name.textContent = `${label}: `;
			row.append(name, document.createTextNode(value == null ? 'n/a' : String(value)));
			panel.append(row);
		}
		if (summary) {
			const text = document.createElement('div');
			text.className = 'summary';
			text.textContent = summary;
			panel.append(text);
		}
	}

	function appendLegend(container, entries) {
		for (const { label, color } of entries) {
			const item = document.createElement('span');
			item.style.setProperty('--color', color);
			item.textContent = label;
			container.append(item);
		}
	}

	function paintPointerArea(node, color, ctx) {
		ctx.fillStyle = color;
		ctx.fillRect(node.x - node.cardWidth / 2, node.y - node.cardHeight / 2,
			node.cardWidth, node.cardHeight);
	}

	function selectCard(graph, container, nodes, event, onSelect) {
		const bounds = container.getBoundingClientRect();
		const point = graph.screen2GraphCoords(
			event.clientX - bounds.left, event.clientY - bounds.top);
		const node = [...nodes].reverse().find(node =>
			Math.abs(point.x - node.x) <= node.cardWidth / 2 &&
			Math.abs(point.y - node.y) <= node.cardHeight / 2);
		if (node) onSelect(node);
	}

	function createDependencyHighlight(data) {
		const incoming = new Map(data.nodes.map(node => [node.id, []]));
		const outgoing = new Map(data.nodes.map(node => [node.id, []]));
		for (const link of data.links) {
			incoming.get(link.target)?.push(link);
			outgoing.get(link.source)?.push(link);
		}
		let selectedId = null;
		let highlightedNodes = new Set();
		let highlightedLinks = new Set();
		const endpointId = endpoint => typeof endpoint === 'object' ? endpoint.id : endpoint;
		return {
			select(node) {
				selectedId = node?.id ?? null;
				highlightedNodes = new Set();
				highlightedLinks = new Set();
				if (!selectedId) return;
				highlightedNodes.add(selectedId);
				for (const links of [incoming, outgoing]) {
					const visited = new Set([selectedId]);
					const pending = [selectedId];
					while (pending.length) {
						const current = pending.pop();
						for (const link of links.get(current) || []) {
							highlightedLinks.add(link);
							const next = links === incoming
								? endpointId(link.source)
								: endpointId(link.target);
							highlightedNodes.add(next);
							if (!visited.has(next)) {
								visited.add(next);
								pending.push(next);
							}
						}
					}
				}
			},
			hasSelection: () => selectedId !== null,
			isSelected: node => node.id === selectedId,
			isNodeHighlighted: node => highlightedNodes.has(node.id),
			isLinkHighlighted: link => highlightedLinks.has(link),
		};
	}

	function createView(graph, container, padding, dimension) {
		let initialFitComplete = false;
		graph.onEngineStop(() => {
			if (!initialFitComplete) {
				graph.zoomToFit(0, padding);
				initialFitComplete = true;
			}
		});
		const fit = () => graph.zoomToFit(600, padding);
		const resize = () => {
			graph.width(container.clientWidth).height(container.clientHeight);
			fit();
		};
		const zoom = factor => {
			if (dimension === '2d') {
				graph.zoom(graph.zoom() * factor, 250);
				return;
			}
			const position = graph.cameraPosition();
			const target = graph.controls().target;
			graph.cameraPosition({
				x: target.x + (position.x - target.x) / factor,
				y: target.y + (position.y - target.y) / factor,
				z: target.z + (position.z - target.z) / factor,
			}, target, 250);
		};
		return { graph, fit, resize, zoom };
	}

	function create3D(container, data, style, {
		label, color, object, onSelect, configure, highlight,
	}) {
		const nodeObjects = new Map();
		const graphColor = node => highlight && highlight.hasSelection()
			? highlight.isSelected(node)
				? '#f8d66d'
				: highlight.isNodeHighlighted(node)
					? '#67e8f9'
					: '#46545f'
			: color(node);
		const graph = ForceGraph3D()(container)
			.width(container.clientWidth)
			.height(container.clientHeight)
			.backgroundColor(style.background_color)
			.nodeLabel(node => tooltip(label(node)))
			.nodeColor(graphColor)
			.nodeRelSize(style.node_rel_size)
			.nodeResolution(style.node_resolution)
			.linkWidth(style.link_width)
			.linkColor(link => highlight?.isLinkHighlighted(link)
				? '#67e8f9'
				: highlight?.hasSelection() ? '#46545f' : style.link_color)
			.linkOpacity(link => highlight?.hasSelection()
				? highlight.isLinkHighlighted(link) ? 1 : 0.18
				: style.link_opacity)
			.linkDirectionalParticles(2)
			.linkDirectionalParticleWidth(2)
			.linkDirectionalParticleSpeed(0.003)
			.linkDirectionalParticleColor(link => highlight?.isLinkHighlighted(link)
				? '#f8d66d'
				: highlight?.hasSelection() ? '#46545f' : style.link_color)
			.onNodeClick(onSelect)
			.nodeThreeObject(node => {
				const nodeObject = object(node);
				nodeObjects.set(node.id, nodeObject);
				return nodeObject;
			});
		if (configure) configure(graph);
		graph.d3Force('charge').strength(style.charge_strength).distanceMax(style.charge_distance_max);
		graph.d3Force('link').distance(style.link_distance);
		const view = createView(graph, container, 60, '3d');
		if (highlight) {
			view.selectNode = id => {
				highlight.select(data.nodes.find(node => node.id === id) || null);
				for (const node of data.nodes) {
					const nodeObject = nodeObjects.get(node.id);
					if (!nodeObject) continue;
					const displayColor = graphColor(node);
					nodeObject.traverse(object3d => {
						if (object3d.isMesh && object3d.material?.color) {
							object3d.material.color.set(displayColor);
						}
					});
				}
				graph.refresh();
			};
		}
		graph.graphData(data);
		return view;
	}

	function labeledMesh(mesh, text, style, offset) {
		const group = new THREE.Group();
		group.add(mesh);
		const label = new SpriteText(text || '', 3.2, style.label_color);
		label.backgroundColor = 'rgba(16,24,32,0.72)';
		label.padding = 2;
		label.borderRadius = 2;
		label.position.set(0, offset, 0);
		group.add(label);
		return group;
	}

	return {
		readPayload, tooltip, showDetails, appendLegend, paintPointerArea, selectCard,
		createDependencyHighlight, createView, create3D, labeledMesh,
	};
})();
