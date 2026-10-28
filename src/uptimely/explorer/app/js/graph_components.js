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
		borderWidth: 1.5, selectedBorderWidth: 3, selectedBorderColor: '#f8d66d',
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
	const DATASET_LAYOUT = Object.freeze({
		rankGap: 100, nodeSpacing: 70, fitPadding: 80,
		lanePadding: 32, laneHeaderHeight: 36, laneGap: 16,
		labelFont: '600 14px "DM Sans", sans-serif', labelColor: '#9fb3c3',
		evenBackground: 'rgba(143, 163, 181, .07)', oddBackground: 'rgba(143, 163, 181, .03)',
		borderColor: 'rgba(143, 163, 181, .3)', orderingPasses: 4,
	});
	const LINK_ROUTE = Object.freeze({
		straightTolerance: 1, cornerRadius: 14, curveSteps: 8,
		arrowLength: 8, arrowHalfAngle: Math.PI / 6,
		flowDurationMs: 2200, particleRadius: 2.5, particleColor: '#e6f4ff',
		// Keep the renderer active while custom canvas particles animate.
		particleCount: 1, particleWidth: 0.1, invisibleParticleColor: 'rgba(0, 0, 0, 0)',
	});
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
		const selected = highlight.isSelected(node);
		ctx.lineWidth = selected ? CARD_STYLE.selectedBorderWidth : CARD_STYLE.borderWidth;
		ctx.strokeStyle = selected ? CARD_STYLE.selectedBorderColor : dimmed ? DIMMED_COLOR : color;
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

	function prepareDatasetLayout(graphData, rankForNode, labelForNode) {
		const rankGroups = new Map();
		const lanes = new Map();
		const nodesById = new Map(graphData.nodes.map(node => [node.id, node]));
		const neighbors = new Map(graphData.nodes.map(node => [node.id, []]));
		const compareNodes = (a, b) =>
			labelForNode(a).localeCompare(labelForNode(b)) || a.id.localeCompare(b.id);
		for (const node of graphData.nodes) {
			node.rank = rankForNode(node);
			sizeCard(node, labelForNode(node));
			if (!rankGroups.has(node.rank)) rankGroups.set(node.rank, []);
			rankGroups.get(node.rank).push(node);
			if (!lanes.has(node.dataset_id)) {
				lanes.set(node.dataset_id, {
					id: node.dataset_id, ranks: new Map(), connections: new Map(),
				});
			}
			const lane = lanes.get(node.dataset_id);
			if (!lane.ranks.has(node.rank)) lane.ranks.set(node.rank, []);
			lane.ranks.get(node.rank).push(node);
		}
		for (const link of graphData.links) {
			const source = nodesById.get(link.source);
			const target = nodesById.get(link.target);
			neighbors.get(source.id).push(target);
			neighbors.get(target.id).push(source);
			if (source.dataset_id === target.dataset_id) continue;
			for (const [from, to] of [[source, target], [target, source]]) {
				const connections = lanes.get(from.dataset_id).connections;
				connections.set(to.dataset_id, (connections.get(to.dataset_id) || 0) + 1);
			}
		}
		// Keep strongly connected datasets adjacent, without assuming a dataset DAG.
		const remaining = [...lanes.values()].sort((a, b) => a.id.localeCompare(b.id));
		const orderedLanes = [];
		while (remaining.length) {
			const previous = orderedLanes.at(-1);
			if (previous) remaining.sort((a, b) =>
				(previous.connections.get(b.id) || 0) - (previous.connections.get(a.id) || 0)
					|| a.id.localeCompare(b.id));
			orderedLanes.push(remaining.shift());
		}
		let graphHeight = 0;
		for (const lane of orderedLanes) {
			const stackHeight = Math.max(...[...lane.ranks.values()].map(nodes =>
				(nodes.length - 1) * DATASET_LAYOUT.nodeSpacing + nodes[0].cardHeight));
			lane.top = graphHeight;
			lane.height = DATASET_LAYOUT.laneHeaderHeight + 2 * DATASET_LAYOUT.lanePadding + stackHeight;
			lane.center = lane.top + DATASET_LAYOUT.laneHeaderHeight
				+ DATASET_LAYOUT.lanePadding + stackHeight / 2;
			graphHeight += lane.height + DATASET_LAYOUT.laneGap;
			for (const nodes of lane.ranks.values()) nodes.sort(compareNodes);
		}
		graphHeight = Math.max(0, graphHeight - DATASET_LAYOUT.laneGap);
		const positionRows = (rank = null) => {
			for (const lane of orderedLanes) {
				const groups = rank === null ? lane.ranks.values() : [lane.ranks.get(rank) || []];
				for (const nodes of groups) {
					nodes.forEach((node, index) => {
						node.fy = lane.center - graphHeight / 2
							+ (index - (nodes.length - 1) / 2) * DATASET_LAYOUT.nodeSpacing;
						node.y = node.fy;
					});
				}
			}
		};
		positionRows();
		const ranksInOrder = [...rankGroups.keys()].sort((a, b) => a - b);
		// Alternate predecessor/successor sweeps to reduce crossings within lanes.
		for (let pass = 0; pass < DATASET_LAYOUT.orderingPasses; pass++) {
			const forward = pass % 2 === 0;
			for (const rank of forward ? ranksInOrder : [...ranksInOrder].reverse()) {
				const scores = new Map(rankGroups.get(rank).map(node => {
					const adjacent = neighbors.get(node.id).filter(other =>
						forward ? other.rank < rank : other.rank > rank);
					return [node.id, adjacent.length
						? adjacent.reduce((sum, other) => sum + other.y, 0) / adjacent.length
						: node.y];
				}));
				for (const lane of orderedLanes) {
					lane.ranks.get(rank)?.sort((a, b) =>
						scores.get(a.id) - scores.get(b.id));
				}
				positionRows(rank);
			}
		}
		const rankWidths = new Map(ranksInOrder.map(rank => [
			rank, Math.max(...rankGroups.get(rank).map(node => node.cardWidth))
		]));
		const rankOffsets = new Map();
		let graphWidth = 0;
		for (const rank of ranksInOrder) {
			rankOffsets.set(rank, graphWidth + rankWidths.get(rank) / 2);
			graphWidth += rankWidths.get(rank) + DATASET_LAYOUT.rankGap;
		}
		graphWidth = Math.max(0, graphWidth - DATASET_LAYOUT.rankGap);
		for (const rank of ranksInOrder) {
			for (const node of rankGroups.get(rank)) {
				node.fx = rankOffsets.get(rank) - graphWidth / 2;
				node.x = node.fx;
				node.rankLeft = node.x - rankWidths.get(rank) / 2;
				node.rankRight = node.x + rankWidths.get(rank) / 2;
				const lane = lanes.get(node.dataset_id);
				node.routeY = lane.top + lane.height - DATASET_LAYOUT.lanePadding / 2 - graphHeight / 2;
			}
		}
		return {
			lanes: orderedLanes, width: graphWidth, height: graphHeight,
			columns: ranksInOrder.map(rank => ({
				rank,
				x: rankOffsets.get(rank) - graphWidth / 2,
				width: rankWidths.get(rank) + DATASET_LAYOUT.rankGap,
			})),
			bounds: {
				x: 0, y: 0,
				width: graphWidth + 2 * DATASET_LAYOUT.lanePadding,
				height: Math.max(1, graphHeight),
			},
		};
	}

	function drawDatasetLanes(layout, ctx, globalScale) {
		ctx.save();
		layout.lanes.forEach((lane, index) => {
			const left = -layout.width / 2 - DATASET_LAYOUT.lanePadding;
			const top = lane.top - layout.height / 2;
			const width = layout.width + 2 * DATASET_LAYOUT.lanePadding;
			ctx.fillStyle = index % 2 === 0
				? DATASET_LAYOUT.evenBackground : DATASET_LAYOUT.oddBackground;
			ctx.fillRect(left, top, width, lane.height);
			ctx.strokeStyle = DATASET_LAYOUT.borderColor;
			ctx.lineWidth = 1 / Math.max(globalScale, MIN_RENDER_SCALE);
			ctx.beginPath();
			ctx.moveTo(left, top);
			ctx.lineTo(left + width, top);
			ctx.stroke();
		});
		ctx.restore();
	}

	function datasetLinkRoute(link) {
		const source = link.source;
		const target = link.target;
		const direction = target.x >= source.x ? 1 : -1;
		const start = [source.x + direction * source.cardWidth / 2, source.y];
		const end = [target.x - direction * target.cardWidth / 2, target.y];
		const skipsRanks = target.rankRight > source.rankRight
			&& target.rankLeft - source.rankRight > DATASET_LAYOUT.rankGap;
		if (!skipsRanks && Math.abs(start[1] - end[1]) < LINK_ROUTE.straightTolerance) return [start, end];
		// Use column gaps and a lane gutter so long edges do not run through cards.
		const exitX = source.rankRight + DATASET_LAYOUT.rankGap / 2;
		const entryX = target.rankLeft - DATASET_LAYOUT.rankGap / 2;
		const corners = skipsRanks
			? [[exitX, start[1]], [exitX, source.routeY], [entryX, source.routeY], [entryX, end[1]]]
			: [[exitX, start[1]], [exitX, end[1]]];
		const points = [start];
		let current = start;
		for (let index = 0; index < corners.length; index++) {
			const corner = corners[index];
			const next = corners[index + 1] || end;
			const incomingLength = Math.hypot(corner[0] - current[0], corner[1] - current[1]);
			const outgoingLength = Math.hypot(next[0] - corner[0], next[1] - corner[1]);
			const radius = Math.min(LINK_ROUTE.cornerRadius, incomingLength / 2, outgoingLength / 2);
			const incoming = [
				(corner[0] - current[0]) / incomingLength,
				(corner[1] - current[1]) / incomingLength,
			];
			const outgoing = [
				(next[0] - corner[0]) / outgoingLength,
				(next[1] - corner[1]) / outgoingLength,
			];
			const before = [corner[0] - incoming[0] * radius, corner[1] - incoming[1] * radius];
			const after = [corner[0] + outgoing[0] * radius, corner[1] + outgoing[1] * radius];
			points.push(before);
			for (let step = 1; step <= LINK_ROUTE.curveSteps; step++) {
				const t = step / LINK_ROUTE.curveSteps;
				const inverse = 1 - t;
				points.push([
					inverse * inverse * before[0] + 2 * inverse * t * corner[0] + t * t * after[0],
					inverse * inverse * before[1] + 2 * inverse * t * corner[1] + t * t * after[1],
				]);
			}
			current = after;
		}
		points.push(end);
		return points;
	}

	function createDatasetLinkRenderer(data, style, highlight) {
		data.links.forEach((link, index) => {
			link.flowOffset = index / Math.max(1, data.links.length);
		});
		return (link, ctx, globalScale) => {
			const points = datasetLinkRoute(link);
			const scale = Math.max(globalScale, MIN_RENDER_SCALE);
			ctx.save();
			ctx.strokeStyle = highlight.isLinkHighlighted(link)
				? LINK_STYLE.highlightColor
				: highlight.hasSelection() ? LINK_STYLE.dimmedColor : style.link_color;
			ctx.lineWidth = (highlight.isLinkHighlighted(link) ? LINK_STYLE.highlightWidth : LINK_STYLE.width2D) / scale;
			ctx.lineCap = 'round';
			ctx.lineJoin = 'round';
			ctx.beginPath();
			ctx.moveTo(points[0][0], points[0][1]);
			for (const [x, y] of points.slice(1)) ctx.lineTo(x, y);
			ctx.stroke();

			const end = points[points.length - 1];
			const previous = points[points.length - 2];
			const angle = Math.atan2(end[1] - previous[1], end[0] - previous[0]);
			const arrowLength = LINK_ROUTE.arrowLength / scale;
			ctx.fillStyle = ctx.strokeStyle;
			ctx.beginPath();
			ctx.moveTo(end[0], end[1]);
			ctx.lineTo(
				end[0] - arrowLength * Math.cos(angle - LINK_ROUTE.arrowHalfAngle),
				end[1] - arrowLength * Math.sin(angle - LINK_ROUTE.arrowHalfAngle),
			);
			ctx.lineTo(
				end[0] - arrowLength * Math.cos(angle + LINK_ROUTE.arrowHalfAngle),
				end[1] - arrowLength * Math.sin(angle + LINK_ROUTE.arrowHalfAngle),
			);
			ctx.closePath();
			ctx.fill();

			const segmentLengths = points.slice(1).map((point, index) =>
				Math.hypot(point[0] - points[index][0], point[1] - points[index][1])
			);
			const totalLength = segmentLengths.reduce((sum, length) => sum + length, 0);
			const phase = (performance.now() / LINK_ROUTE.flowDurationMs + link.flowOffset) % 1;
			let distance = phase * totalLength;
			let segmentIndex = 0;
			while (segmentIndex < segmentLengths.length - 1 && distance > segmentLengths[segmentIndex]) {
				distance -= segmentLengths[segmentIndex++];
			}
			const segmentStart = points[segmentIndex];
			const segmentEnd = points[segmentIndex + 1];
			const progress = distance / segmentLengths[segmentIndex];
			ctx.fillStyle = highlight.isLinkHighlighted(link)
				? LINK_STYLE.highlightParticleColor
				: highlight.hasSelection() ? LINK_STYLE.dimmedColor : LINK_ROUTE.particleColor;
			ctx.beginPath();
			ctx.arc(
				segmentStart[0] + (segmentEnd[0] - segmentStart[0]) * progress,
				segmentStart[1] + (segmentEnd[1] - segmentStart[1]) * progress,
				LINK_ROUTE.particleRadius / scale, 0, 2 * Math.PI,
			);
			ctx.fill();
			ctx.restore();
		};
	}

	function createView(graph, container, padding, dimension, bounds = null) {
		const fitGraph = duration => {
			if (dimension === '2d' && bounds) {
				graph.centerAt(bounds.x, bounds.y, duration);
				graph.zoom(Math.min(
					Math.max(1, container.clientWidth - 2 * padding) / bounds.width,
					Math.max(1, container.clientHeight - 2 * padding) / bounds.height,
				), duration);
				return;
			}
			graph.zoomToFit(duration, padding);
		};
		let initialFitComplete = false;
		graph.onEngineStop(() => {
			if (!initialFitComplete) {
				fitGraph(VIEW_TIMING.initialFit);
				initialFitComplete = true;
			}
		});
		const fit = () => fitGraph(VIEW_TIMING.fit);
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
		DATASET_LAYOUT, LINK_ROUTE, prepareDatasetLayout, drawDatasetLanes, createDatasetLinkRenderer,
		sizeCard, drawCard,
		readPayload, tooltip, showDetails, appendLegend, paintPointerArea, selectCard,
		prepareDatasetColors, humanizeDatasetName, datasetNodeObject,
		createDependencyHighlight, createView, create3D, labeledMesh,
	};
})();
