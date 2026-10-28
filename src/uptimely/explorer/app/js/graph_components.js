const ExplorerGraph = (() => {
	const DATASET_PALETTE = Object.freeze([
		'#ff9f43', '#2dd4bf', '#fb7185', '#a78bfa',
		'#facc15', '#60a5fa', '#f472b6', '#a3e635',
		'#22d3ee', '#c084fc', '#4ade80', '#f87171',
	]);
	const UNASSIGNED_DATASET = 'Unassigned';
	const CARD_STYLE = Object.freeze({
		minWidth: 112, maxWidth: 280, characterWidth: 8, horizontalPadding: 52,
		height: 38, cornerRadius: 12,
		shadowColor: 'rgba(0, 0, 0, .36)', shadowBlur: 14, shadowOffsetY: 4,
		background: '#1a2732', featureBackground: '#172a35', dimmedBackground: '#121c24',
		textColor: '#e8edf2', dimmedTextColor: 'rgba(232, 237, 242, .3)',
		font: '600 12px "DM Sans", sans-serif',
		borderWidth: 1.5, selectedBorderWidth: 3,
		iconLeft: 12, iconSize: 12, iconRadius: 3,
		featureIconLeft: 13, featureIconWidth: 4, featureIconHeight: 18, featureIconRadius: 2,
		labelLeft: 34, labelHorizontalPadding: 46,
	});
	const LINK_STYLE = Object.freeze({
		highlightColor: '#67e8f9', dimmedColor: 'rgba(70, 84, 95, .35)',
		highlightWidth: 3, highlightWidthMultiplier3D: 3, width2D: 1.5,
		particleCount: 2, particleWidth: 2, particleSpeed: 0.003,
		highlightParticleColor: '#f8d66d',
	});
	const DIMMED_COLOR = '#46545f';
	const MIN_RENDER_SCALE = 0.01;
	const STATIC_LAYOUT_COOLDOWN_TICKS = 1;
	const VIEW_TIMING = Object.freeze({ initialFit: 0, fit: 600, zoom: 250 });
	const NODE_STYLE_3D = Object.freeze({
		sphereWidthSegments: 16, sphereHeightSegments: 12, labelOffset: 14,
		selectedScale: 1.4, highlightedScale: 1.15, dimmedScale: 0.75,
		fitPadding: 60, labelHeight: 3.2, labelBackground: 'rgba(16,24,32,0.72)',
		labelPadding: 2, labelBorderRadius: 2,
	});

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

	function humanizeDatasetName(dataset) {
		return dataset.replaceAll('_', ' ')
			.replace(/\b\w/g, character => character.toUpperCase());
	}

	function prepareDatasetColors(data, container) {
		const names = [...new Set(data.nodes
			.filter(node => !node.is_action)
			.map(node => node.dataset_id || UNASSIGNED_DATASET))]
			.sort((a, b) => a.localeCompare(b));
		const colors = new Map(names.map(
			(dataset, index) => [dataset, DATASET_PALETTE[index % DATASET_PALETTE.length]]
		));
		appendLegend(container, names.map(dataset => ({
			label: humanizeDatasetName(dataset), color: colors.get(dataset),
		})));
		for (const node of data.nodes) {
			node.dataset_id = node.dataset_id || UNASSIGNED_DATASET;
			node.datasetColor = colors.get(node.dataset_id);
		}
	}

	function datasetNodeObject(node, text, style) {
		const mesh = new THREE.Mesh(
			new THREE.SphereGeometry(style.feature_node_size,
				NODE_STYLE_3D.sphereWidthSegments, NODE_STYLE_3D.sphereHeightSegments),
			new THREE.MeshLambertMaterial({ color: node.datasetColor }),
		);
		return labeledMesh(mesh, text, style, NODE_STYLE_3D.labelOffset);
	}

	function sizeCard(node, label) {
		node.cardWidth = Math.min(CARD_STYLE.maxWidth,
			Math.max(CARD_STYLE.minWidth, label.length * CARD_STYLE.characterWidth + CARD_STYLE.horizontalPadding));
		node.cardHeight = CARD_STYLE.height;
	}

	function drawCard(node, ctx, label, color, highlight, isFeature = false) {
		const dimmed = highlight.hasSelection() && !highlight.isNodeHighlighted(node);
		const left = node.x - node.cardWidth / 2;
		ctx.save();
		ctx.shadowColor = CARD_STYLE.shadowColor;
		ctx.shadowBlur = CARD_STYLE.shadowBlur;
		ctx.shadowOffsetY = CARD_STYLE.shadowOffsetY;
		ctx.beginPath();
		ctx.roundRect(left, node.y - node.cardHeight / 2,
			node.cardWidth, node.cardHeight, CARD_STYLE.cornerRadius);
		ctx.fillStyle = dimmed ? CARD_STYLE.dimmedBackground
			: isFeature ? CARD_STYLE.featureBackground : CARD_STYLE.background;
		ctx.fill();
		ctx.shadowColor = 'transparent';
		ctx.lineWidth = highlight.isSelected(node) ? CARD_STYLE.selectedBorderWidth : CARD_STYLE.borderWidth;
		ctx.strokeStyle = dimmed ? DIMMED_COLOR : color;
		ctx.stroke();
		ctx.beginPath();
		if (isFeature) {
			ctx.roundRect(left + CARD_STYLE.featureIconLeft, node.y - CARD_STYLE.featureIconHeight / 2,
				CARD_STYLE.featureIconWidth, CARD_STYLE.featureIconHeight, CARD_STYLE.featureIconRadius);
		} else {
			ctx.roundRect(left + CARD_STYLE.iconLeft, node.y - CARD_STYLE.iconSize / 2,
				CARD_STYLE.iconSize, CARD_STYLE.iconSize, CARD_STYLE.iconRadius);
		}
		ctx.fillStyle = dimmed ? DIMMED_COLOR : color;
		ctx.fill();
		ctx.textAlign = 'left';
		ctx.fillStyle = dimmed ? CARD_STYLE.dimmedTextColor : CARD_STYLE.textColor;
		ctx.font = CARD_STYLE.font;
		ctx.textAlign = 'left';
		ctx.textBaseline = 'middle';
		ctx.fillText(label, left + CARD_STYLE.labelLeft, node.y,
			node.cardWidth - CARD_STYLE.labelHorizontalPadding);
		ctx.restore();
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
				graph.zoomToFit(VIEW_TIMING.initialFit, padding);
				initialFitComplete = true;
			}
		});
		const fit = () => graph.zoomToFit(VIEW_TIMING.fit, padding);
		const resize = () => {
			graph.width(container.clientWidth).height(container.clientHeight);
			fit();
		};
		const zoom = factor => {
			if (dimension === '2d') {
				graph.zoom(graph.zoom() * factor, VIEW_TIMING.zoom);
				return;
			}
			const position = graph.cameraPosition();
			const target = graph.controls().target;
			graph.cameraPosition({
				x: target.x + (position.x - target.x) / factor,
				y: target.y + (position.y - target.y) / factor,
				z: target.z + (position.z - target.z) / factor,
			}, target, VIEW_TIMING.zoom);
		};
		return { graph, fit, resize, zoom };
	}

	function create3D(container, data, style, {
		label, color, object, onSelect, configure, highlight,
	}) {
		const nodeColor = node => highlight?.hasSelection() && !highlight.isNodeHighlighted(node)
			? DIMMED_COLOR
			: color(node);
		const createNodeObject = node => {
			const nodeObject = object(node);
			if (highlight?.hasSelection()) {
				const colorValue = nodeColor(node);
				nodeObject.traverse(object3d => {
					if (!object3d.isMesh) return;
					if (object3d.material?.color) object3d.material.color.set(colorValue);
					object3d.scale.setScalar(
						highlight.isSelected(node)
							? NODE_STYLE_3D.selectedScale
							: highlight.isNodeHighlighted(node) ? NODE_STYLE_3D.highlightedScale : NODE_STYLE_3D.dimmedScale,
					);
				});
			}
			return nodeObject;
		};
		const graph = ForceGraph3D()(container)
			.width(container.clientWidth)
			.height(container.clientHeight)
			.backgroundColor(style.background_color)
			.nodeLabel(node => tooltip(label(node)))
			.nodeColor(nodeColor)
			.nodeRelSize(style.node_rel_size)
			.nodeResolution(style.node_resolution)
			.linkWidth(link => highlight?.isLinkHighlighted(link)
				? style.link_width * LINK_STYLE.highlightWidthMultiplier3D
				: style.link_width)
			.linkColor(link => highlight?.isLinkHighlighted(link)
				? LINK_STYLE.highlightColor
				: highlight?.hasSelection() ? DIMMED_COLOR : style.link_color)
			.linkOpacity(style.link_opacity)
			.linkDirectionalParticles(LINK_STYLE.particleCount)
			.linkDirectionalParticleWidth(LINK_STYLE.particleWidth)
			.linkDirectionalParticleSpeed(LINK_STYLE.particleSpeed)
			.linkDirectionalParticleColor(link => highlight?.isLinkHighlighted(link)
				? LINK_STYLE.highlightParticleColor
				: highlight?.hasSelection() ? DIMMED_COLOR : style.link_color)
			.onNodeClick(onSelect)
			.nodeThreeObject(createNodeObject);
		if (configure) configure(graph);
		graph.d3Force('charge').strength(style.charge_strength).distanceMax(style.charge_distance_max);
		graph.d3Force('link').distance(style.link_distance);
		const view = createView(graph, container, NODE_STYLE_3D.fitPadding, '3d');
		if (highlight) {
			view.selectNode = id => {
				highlight.select(data.nodes.find(node => node.id === id) || null);
				graph.refresh();
			};
		}
		graph.graphData(data);
		return view;
	}

	function labeledMesh(mesh, text, style, offset) {
		const group = new THREE.Group();
		group.add(mesh);
		const label = new SpriteText(text || '', NODE_STYLE_3D.labelHeight, style.label_color);
		label.backgroundColor = NODE_STYLE_3D.labelBackground;
		label.padding = NODE_STYLE_3D.labelPadding;
		label.borderRadius = NODE_STYLE_3D.labelBorderRadius;
		label.position.set(0, offset, 0);
		group.add(label);
		return group;
	}

	return {
		LINK_STYLE, DIMMED_COLOR, MIN_RENDER_SCALE, STATIC_LAYOUT_COOLDOWN_TICKS,
		sizeCard, drawCard,
		readPayload, tooltip, showDetails, appendLegend, paintPointerArea, selectCard,
		prepareDatasetColors, humanizeDatasetName, datasetNodeObject,
		createDependencyHighlight, createView, create3D, labeledMesh,
	};
})();
