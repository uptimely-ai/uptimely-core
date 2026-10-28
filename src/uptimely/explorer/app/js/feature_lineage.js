{
	const DETAIL_VALUE_MAX_LENGTH = 220;
	const FEATURE_LAYOUT = Object.freeze({ rankGap: 100, nodeSpacing: 70, fitPadding: 80 });
	const LINK_ROUTE = Object.freeze({
		straightTolerance: 1, cornerRadius: 14, curveSteps: 8,
		arrowLength: 8, arrowHalfAngle: Math.PI / 6,
		flowDurationMs: 2200, particleRadius: 2.5, particleColor: '#e6f4ff',
	});
	const FORCE_GRAPH_2D = Object.freeze({
		nodeRelativeSize: 6, functionValue: 7, featureValue: 5,
		// Keep the renderer active while custom canvas particles animate.
		particleCount: 1, particleWidth: 0.1, particleColor: 'rgba(0, 0, 0, 0)',
	});
	const { LINK_STYLE, MIN_RENDER_SCALE, STATIC_LAYOUT_COOLDOWN_TICKS } = ExplorerGraph;
	const data = ExplorerGraph.readPayload('graph-data');
	const style = ExplorerGraph.readPayload('graph-style');
	const functionColor = style.function_color;
	ExplorerGraph.prepareDatasetColors(data, document.getElementById('dataset-legend'));
	const nodeDetails = document.getElementById('node-details');
	const formatDetailValue = (value) => value == null ? 'n/a' : String(value).slice(0, DETAIL_VALUE_MAX_LENGTH);
	const updateDetails = (node) => {
		if (!node) {
			ExplorerGraph.showDetails(nodeDetails, 'Selected item', [],
				'Select any feature in the graph to see its identifier and details.');
			return;
		}
		const label = node.label || node.id || 'Unknown';
		const isAction = node.is_action === true;
		if (isAction) {
			const entrypoint = node.entrypoint || null;
			const features = Array.isArray(node.features) ? node.features : [];
			const outputLabel = node.function_kind === 'escape'
				? 'Declares external outputs'
				: 'Produces';
			const rows = [
				['Node type', 'Action'],
				['Action', node.action_id || label],
				['Function', node.function_id || 'n/a'],
				['Function kind', node.function_kind || 'n/a'],
			];
			if (features.length) rows.push([outputLabel, formatDetailValue(features.join(', '))]);
			if (entrypoint) rows.push(['Entrypoint', formatDetailValue(entrypoint)]);
			ExplorerGraph.showDetails(nodeDetails, 'Selected item', rows);
			return;
		}
		const dataType = node.data_type || node.type || 'unknown';
		const entity = node.entity || 'n/a';
		ExplorerGraph.showDetails(nodeDetails, 'Selected item', [
			['Node type', 'Feature'], ['Feature', label],
			['Entity', formatDetailValue(entity)], ['Data type', formatDetailValue(dataType)],
		]);
	};

	function create2D(graphContainer, data, updateDetails) {
		const highlight = ExplorerGraph.createDependencyHighlight(data);
		function rankNodes(graphData) {
			const children = new Map(graphData.nodes.map(node => [node.id, []]));
			const indegree = new Map(graphData.nodes.map(node => [node.id, 0]));
			for (const link of graphData.links) {
				children.get(link.source)?.push(link.target);
				indegree.set(link.target, (indegree.get(link.target) || 0) + 1);
			}
			const ranks = new Map(graphData.nodes.map(node => [node.id, 0]));
			const queue = graphData.nodes
				.filter(node => indegree.get(node.id) === 0)
				.map(node => node.id)
				.sort();
			for (let index = 0; index < queue.length; index++) {
				const source = queue[index];
				for (const target of children.get(source) || []) {
					ranks.set(target, Math.max(ranks.get(target), ranks.get(source) + 1));
					indegree.set(target, indegree.get(target) - 1);
					if (indegree.get(target) === 0) queue.push(target);
				}
			}
			const maxRank = Math.max(0, ...ranks.values());
			const unresolved = graphData.nodes
				.filter(node => indegree.get(node.id) > 0)
				.sort((a, b) => a.id.localeCompare(b.id));
			for (const node of unresolved) ranks.set(node.id, maxRank + 1);
			return ranks;
		}

		function prepareGraphLayout(graphData) {
			const nodeRanks = rankNodes(graphData);
			const rankGroups = new Map();
			for (const node of graphData.nodes) {
				node.rank = nodeRanks.get(node.id);
				ExplorerGraph.sizeCard(node, node.label || node.id);
				if (!rankGroups.has(node.rank)) rankGroups.set(node.rank, []);
				rankGroups.get(node.rank).push(node);
			}
			for (const nodes of rankGroups.values()) {
				nodes.sort((a, b) => a.label.localeCompare(b.label) || a.id.localeCompare(b.id));
			}
			const ranksInOrder = [...rankGroups.keys()].sort((a, b) => a - b);
			const rankWidths = new Map(ranksInOrder.map(rank => [
				rank,
				Math.max(...rankGroups.get(rank).map(node => node.cardWidth))
			]));
			const rankOffsets = new Map();
			let graphWidth = 0;
			for (const rank of ranksInOrder) {
				rankOffsets.set(rank, graphWidth + rankWidths.get(rank) / 2);
				graphWidth += rankWidths.get(rank) + FEATURE_LAYOUT.rankGap;
			}
			for (const rank of ranksInOrder) {
				const nodes = rankGroups.get(rank);
				nodes.forEach((node, index) => {
					node.fx = rankOffsets.get(rank) - graphWidth / 2;
					node.fy = (index - (nodes.length - 1) / 2) * FEATURE_LAYOUT.nodeSpacing;
					node.x = node.fx;
					node.y = node.fy;
				});
			}
		}

		prepareGraphLayout(data);
		const selectAtPointer = event =>
			ExplorerGraph.selectCard(graph, graphContainer, data.nodes, event, updateDetails);

		function drawNode(node, ctx) {
			const isAction = node.is_action === true;
			const baseColor = isAction ? functionColor : node.datasetColor;
			ExplorerGraph.drawCard(node, ctx, node.label || node.id, baseColor, highlight, !isAction);
		}

		function linkRoute(link) {
			const source = link.source;
			const target = link.target;
			const direction = target.x >= source.x ? 1 : -1;
			const start = [source.x + direction * source.cardWidth / 2, source.y];
			const end = [target.x - direction * target.cardWidth / 2, target.y];
			if (Math.abs(start[1] - end[1]) < LINK_ROUTE.straightTolerance) return [start, end];
			const bendX = (start[0] + end[0]) / 2;
			const corners = [[bendX, start[1]], [bendX, end[1]]];
			const points = [start];
			let current = start;
			for (let index = 0; index < corners.length; index++) {
				const corner = corners[index];
				const next = index === 0 ? corners[1] : end;
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

		function drawLink(link, ctx, globalScale) {
			const points = linkRoute(link);
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
				LINK_ROUTE.particleRadius / scale,
				0,
				2 * Math.PI,
			);
			ctx.fill();
			ctx.restore();
		}

		data.links.forEach((link, index) => {
			link.flowOffset = index / Math.max(1, data.links.length);
		});

		const graph = ForceGraph()(graphContainer)
			.width(graphContainer.clientWidth)
			.height(graphContainer.clientHeight)
			.backgroundColor(style.background_color)
			.nodeLabel(node => ExplorerGraph.tooltip(`${node.is_action ? 'action' : 'feature'}: ${node.label}\nentity: ${node.entity || 'n/a'}`))
			.nodeRelSize(FORCE_GRAPH_2D.nodeRelativeSize)
			.nodeVal(node => node.is_action ? FORCE_GRAPH_2D.functionValue : FORCE_GRAPH_2D.featureValue)
			.nodeColor(node => node.is_action ? functionColor : node.datasetColor)
			.nodeCanvasObjectMode(() => 'replace')
			.nodeCanvasObject(drawNode)
			.nodePointerAreaPaint(ExplorerGraph.paintPointerArea)
			.linkColor(link => highlight.isLinkHighlighted(link)
				? LINK_STYLE.highlightColor
				: highlight.hasSelection() ? LINK_STYLE.dimmedColor : style.link_color)
			.linkWidth(link => highlight.isLinkHighlighted(link) ? LINK_STYLE.highlightWidth : style.link_width)
			.linkCanvasObjectMode(() => 'replace')
			.linkCanvasObject(drawLink)
			.linkDirectionalParticles(FORCE_GRAPH_2D.particleCount)
			.linkDirectionalParticleWidth(FORCE_GRAPH_2D.particleWidth)
			.linkDirectionalParticleColor(() => FORCE_GRAPH_2D.particleColor)
			.linkDirectionalArrowLength(0)
			.onNodeClick((_node, event) => selectAtPointer(event))
			.onLinkClick((_link, event) => selectAtPointer(event))
			.onBackgroundClick(event => selectAtPointer(event))
			.cooldownTicks(STATIC_LAYOUT_COOLDOWN_TICKS);
		const view = ExplorerGraph.createView(graph, graphContainer, FEATURE_LAYOUT.fitPadding, '2d');
		view.selectNode = id => {
			highlight.select(data.nodes.find(node => node.id === id) || null);
		};
		graph.graphData(data);
		return view;
	}

	function create3D(graphContainer, data, updateDetails) {
		const highlight = ExplorerGraph.createDependencyHighlight(data);
		return ExplorerGraph.create3D(graphContainer, data, style, {
			label: node => `${node.is_action ? 'function' : 'feature'}: ${node.label}\nentity: ${node.entity || 'n/a'}`,
			color: node => node.is_action ? functionColor : node.datasetColor,
			onSelect: updateDetails,
			highlight,
			configure: graph => graph.linkDirectionalArrowLength(style.arrow_length)
				.linkDirectionalArrowRelPos(style.arrow_rel_pos),
			object: node => {
				if (!node.is_action) {
					return ExplorerGraph.datasetNodeObject(node, node.label, style);
				}
				const mesh = new THREE.Mesh(
					new THREE.OctahedronGeometry(style.function_node_size, 0),
					new THREE.MeshLambertMaterial({ color: functionColor }),
				);
				return ExplorerGraph.labeledMesh(mesh, node.label, style, 14);
			},
		});
	}

	mountGraphViews(data, create2D, create3D, updateDetails, document.getElementById('node-details'));
}
