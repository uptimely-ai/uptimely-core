{
	const data = JSON.parse(document.getElementById('graph-data').textContent);
	const style = JSON.parse(document.getElementById('graph-style').textContent);
	const functionColor = style.function_color;
	const entityNames = [...new Set(data.nodes.map(node => node.entity || 'Unassigned'))]
		.sort((a, b) => a.localeCompare(b));
	const entityPalette = [
		'#ff9f43', '#2dd4bf', '#fb7185', '#a78bfa',
		'#facc15', '#60a5fa', '#f472b6', '#a3e635',
		'#22d3ee', '#c084fc', '#4ade80', '#f87171',
	];
	const entityColors = new Map(entityNames.map(
		(entity, index) => [entity, entityPalette[index % entityPalette.length]]
	));
	const entityLegend = document.getElementById('entity-legend');
	for (const entity of entityNames) {
		const item = document.createElement('span');
		item.style.setProperty('--color', entityColors.get(entity));
		item.textContent = entity;
		entityLegend.append(item);
	}
	for (const node of data.nodes) {
		node.entity = node.entity || 'Unassigned';
		node.entityColor = entityColors.get(node.entity);
	}
	const nodeDetails = document.getElementById('node-details');
	const formatDetailValue = (value) => value == null ? 'n/a' : String(value).slice(0, 220);
	const updateDetails = (node) => {
		if (!node) {
			nodeDetails.innerHTML = `
				<h2>Selected item</h2>
				<div class="meta">Click a node</div>
				<div class="summary">Select any feature in the graph to see its identifier and details.</div>
			`;
			return;
		}
		const label = node.label || node.id || 'Unknown';
		const isFunction = node.is_function === true;
		if (isFunction) {
			const entrypoint = node.entrypoint || null;
			const features = Array.isArray(node.features) ? node.features : [];
			const outputLabel = node.function_type === 'escape'
				? 'Declares external outputs:'
				: 'Produces:';
			const detailParts = [
				`<div class="meta"><strong>Node type:</strong> Function</div>`,
				`<div class="meta"><strong>Function:</strong> ${label}</div>`,
				`<div class="meta"><strong>Function type:</strong> ${node.function_type || 'n/a'}</div>`,
				features.length ? `<div class="meta"><strong>${outputLabel}</strong> ${formatDetailValue(features.join(', '))}</div>` : '',
				entrypoint ? `<div class="meta"><strong>Entrypoint:</strong> ${formatDetailValue(entrypoint)}</div>` : '',
			].filter(Boolean).join('');
			nodeDetails.innerHTML = `
				<h2>Selected item</h2>
				${detailParts || '<div class="meta">No function metadata available.</div>'}
			`;
			return;
		}
		const dataType = node.data_type || node.type || 'unknown';
		const entity = node.entity || 'n/a';
		nodeDetails.innerHTML = `
			<h2>Selected item</h2>
			<div class="meta"><strong>Node type:</strong> Feature</div>
			<div class="meta"><strong>Feature:</strong> ${label}</div>
			<div class="meta"><strong>Entity:</strong> ${formatDetailValue(entity)}</div>
			<div class="meta"><strong>Data type:</strong> ${formatDetailValue(dataType)}</div>
		`;
	};

	function create2D(graphContainer, data, updateDetails) {
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
				node.cardWidth = Math.min(280, Math.max(112, (node.label || node.id).length * 8 + 52));
				node.cardHeight = 38;
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
				graphWidth += rankWidths.get(rank) + 100;
			}
			for (const rank of ranksInOrder) {
				const nodes = rankGroups.get(rank);
				nodes.forEach((node, index) => {
					node.fx = rankOffsets.get(rank) - graphWidth / 2;
					node.fy = (index - (nodes.length - 1) / 2) * 70;
					node.x = node.fx;
					node.y = node.fy;
				});
			}
		}

		prepareGraphLayout(data);
		function selectAtPointer(event) {
			const bounds = graphContainer.getBoundingClientRect();
			const point = graph.screen2GraphCoords(
				event.clientX - bounds.left, event.clientY - bounds.top);
			const node = [...data.nodes].reverse().find(node =>
				Math.abs(point.x - node.x) <= node.cardWidth / 2 &&
				Math.abs(point.y - node.y) <= node.cardHeight / 2);
			if (node) updateDetails(node);
		}

		function drawNode(node, ctx) {
			const label = node.label || node.id;
			const isFunction = node.is_function === true;
			const color = isFunction ? functionColor : node.entityColor;
			const width = node.cardWidth;
			const left = node.x - width / 2;
			ctx.save();
			ctx.shadowColor = 'rgba(0, 0, 0, .36)';
			ctx.shadowBlur = 14;
			ctx.shadowOffsetY = 4;
			ctx.beginPath();
			ctx.roundRect(left, node.y - node.cardHeight / 2, width, node.cardHeight, 12);
			ctx.fillStyle = isFunction ? '#1a2732' : '#172a35';
			ctx.fill();
			ctx.shadowColor = 'transparent';
			ctx.lineWidth = 1.5;
			ctx.strokeStyle = color;
			ctx.stroke();
			ctx.beginPath();
			if (isFunction) {
				ctx.roundRect(left + 12, node.y - 6, 12, 12, 3);
			} else {
				ctx.roundRect(left + 13, node.y - 9, 4, 18, 2);
			}
			ctx.fillStyle = color;
			ctx.fill();
			ctx.fillStyle = '#e8edf2';
			ctx.font = '600 12px "DM Sans", sans-serif';
			ctx.textAlign = 'left';
			ctx.textBaseline = 'middle';
			ctx.fillText(label, left + 34, node.y, width - 46);
			ctx.restore();
		}

		function linkRoute(link) {
			const source = link.source;
			const target = link.target;
			const direction = target.x >= source.x ? 1 : -1;
			const start = [source.x + direction * source.cardWidth / 2, source.y];
			const end = [target.x - direction * target.cardWidth / 2, target.y];
			if (Math.abs(start[1] - end[1]) < 1) return [start, end];
			const bendX = (start[0] + end[0]) / 2;
			const corners = [[bendX, start[1]], [bendX, end[1]]];
			const points = [start];
			let current = start;
			for (let index = 0; index < corners.length; index++) {
				const corner = corners[index];
				const next = index === 0 ? corners[1] : end;
				const incomingLength = Math.hypot(corner[0] - current[0], corner[1] - current[1]);
				const outgoingLength = Math.hypot(next[0] - corner[0], next[1] - corner[1]);
				const radius = Math.min(14, incomingLength / 2, outgoingLength / 2);
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
				for (let step = 1; step <= 8; step++) {
					const t = step / 8;
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
			const scale = Math.max(globalScale, 0.01);
			ctx.save();
			ctx.strokeStyle = style.link_color;
			ctx.lineWidth = 1.5 / scale;
			ctx.lineCap = 'round';
			ctx.lineJoin = 'round';
			ctx.beginPath();
			ctx.moveTo(points[0][0], points[0][1]);
			for (const [x, y] of points.slice(1)) ctx.lineTo(x, y);
			ctx.stroke();

			const end = points[points.length - 1];
			const previous = points[points.length - 2];
			const angle = Math.atan2(end[1] - previous[1], end[0] - previous[0]);
			const arrowLength = 8 / scale;
			ctx.fillStyle = style.link_color;
			ctx.beginPath();
			ctx.moveTo(end[0], end[1]);
			ctx.lineTo(
				end[0] - arrowLength * Math.cos(angle - Math.PI / 6),
				end[1] - arrowLength * Math.sin(angle - Math.PI / 6),
			);
			ctx.lineTo(
				end[0] - arrowLength * Math.cos(angle + Math.PI / 6),
				end[1] - arrowLength * Math.sin(angle + Math.PI / 6),
			);
			ctx.closePath();
			ctx.fill();

			const segmentLengths = points.slice(1).map((point, index) =>
				Math.hypot(point[0] - points[index][0], point[1] - points[index][1])
			);
			const totalLength = segmentLengths.reduce((sum, length) => sum + length, 0);
			const phase = (performance.now() / 2200 + link.flowOffset) % 1;
			let distance = phase * totalLength;
			let segmentIndex = 0;
			while (segmentIndex < segmentLengths.length - 1 && distance > segmentLengths[segmentIndex]) {
				distance -= segmentLengths[segmentIndex++];
			}
			const segmentStart = points[segmentIndex];
			const segmentEnd = points[segmentIndex + 1];
			const progress = distance / segmentLengths[segmentIndex];
			ctx.fillStyle = '#e6f4ff';
			ctx.beginPath();
			ctx.arc(
				segmentStart[0] + (segmentEnd[0] - segmentStart[0]) * progress,
				segmentStart[1] + (segmentEnd[1] - segmentStart[1]) * progress,
				2.5 / scale,
				0,
				2 * Math.PI,
			);
			ctx.fill();
			ctx.restore();
		}

		data.links.forEach((link, index) => {
			link.flowOffset = index / Math.max(1, data.links.length);
		});

		let initialFitComplete = false;
		const graph = ForceGraph()(graphContainer)
			.width(graphContainer.clientWidth)
			.height(graphContainer.clientHeight)
			.backgroundColor(style.background_color)
			.nodeLabel(node => `${node.is_function ? 'function' : 'feature'}: ${node.label}<br>entity: ${node.entity || 'n/a'}`)
			.nodeRelSize(6)
			.nodeVal(node => node.is_function ? 7 : 5)
			.nodeColor(node => node.is_function ? functionColor : node.entityColor)
			.nodeCanvasObjectMode(() => 'replace')
			.nodeCanvasObject(drawNode)
			.nodePointerAreaPaint((node, color, ctx) => {
				ctx.fillStyle = color;
				ctx.fillRect(node.x - node.cardWidth / 2, node.y - node.cardHeight / 2,
					node.cardWidth, node.cardHeight);
			})
			.linkColor(() => style.link_color)
			.linkWidth(style.link_width)
			.linkCanvasObjectMode(() => 'replace')
			.linkCanvasObject(drawLink)
			.linkDirectionalParticles(1)
			.linkDirectionalParticleWidth(0.1)
			.linkDirectionalParticleColor(() => 'rgba(0, 0, 0, 0)')
			.linkDirectionalArrowLength(0)
			.onNodeClick((_node, event) => selectAtPointer(event))
			.onLinkClick((_link, event) => selectAtPointer(event))
			.onBackgroundClick(event => selectAtPointer(event))
			.cooldownTicks(1)
			.onEngineStop(() => {
				if (!initialFitComplete) {
					graph.zoomToFit(0, 80);
					initialFitComplete = true;
				}
			})
			.graphData(data);

		function fitGraph() {
			graph.zoomToFit(600, 80);
		}

		function resizeGraph() {
			graph.width(graphContainer.clientWidth).height(graphContainer.clientHeight);
			fitGraph();
		}

		return { graph, fit: fitGraph, resize: resizeGraph };
	}

	function create3D(graphContainer, data, updateDetails) {
		let initialFitComplete = false;
		const graph = ForceGraph3D()(graphContainer)
			.width(graphContainer.clientWidth)
			.height(graphContainer.clientHeight)
			.graphData(data)
			.backgroundColor(style.background_color)
			.nodeLabel(node => `${node.is_function ? 'function' : 'feature'}: ${node.label}<br>entity: ${node.entity || 'n/a'}`)
			.nodeColor(node => node.is_function ? functionColor : node.entityColor)
			.nodeRelSize(style.node_rel_size)
			.nodeResolution(style.node_resolution)
			.linkDirectionalArrowLength(style.arrow_length)
			.linkDirectionalArrowRelPos(style.arrow_rel_pos)
			.linkWidth(style.link_width)
			.linkColor(() => style.link_color)
			.linkOpacity(style.link_opacity)
			.linkDirectionalParticles(2)
			.linkDirectionalParticleWidth(2)
			.linkDirectionalParticleSpeed(0.003)
			.onNodeClick(node => updateDetails(node))
			.onEngineStop(() => {
				if (!initialFitComplete) {
					graph.zoomToFit(0, 60);
					initialFitComplete = true;
				}
			})
			.nodeThreeObject(node => {
				const color = node.is_function ? functionColor : node.entityColor;
				const material = new THREE.MeshLambertMaterial({ color });
				const isVariable = !node.is_function;
				const geometry = isVariable
					? new THREE.SphereGeometry(style.feature_node_size, 16, 12)
					: new THREE.OctahedronGeometry(style.function_node_size, 0);
				const mesh = new THREE.Mesh(geometry, material);

				if (!isVariable) {
					return mesh;
				}

				const group = new THREE.Group();
				group.add(mesh);
				const label = new SpriteText(node.label || '', 3.2, style.label_color);
				label.backgroundColor = 'rgba(16,24,32,0.72)';
				label.padding = 2;
				label.borderRadius = 2;
				label.position.set(0, 14, 0);
				group.add(label);
				return group;
			});
		const chargeForce = graph.d3Force('charge');
		chargeForce.strength(style.charge_strength);
		chargeForce.distanceMax(style.charge_distance_max);
		graph.d3Force('link').distance(style.link_distance);
		const fit = () => graph.zoomToFit(0, 60);
		const resize = () => {
			graph.width(graphContainer.clientWidth).height(graphContainer.clientHeight);
			fit();
		};
		return { graph, fit, resize };
	}

	mountGraphViews(data, create2D, create3D, updateDetails, document.getElementById('node-details'));
}
