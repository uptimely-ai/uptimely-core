import {
	CARD_STYLE,
	DATASET_LAYOUT,
	LINK_ROUTE,
	LINK_STYLE,
	MIN_RENDER_SCALE,
} from './lineage_config.js';

function sizeCard(node, label) {
	node.cardWidth = Math.min(CARD_STYLE.maxWidth,
		Math.max(CARD_STYLE.minWidth, label.length * CARD_STYLE.characterWidth + CARD_STYLE.horizontalPadding));
	node.cardHeight = CARD_STYLE.height;
}

function prepareLineageLayout(graphData, rankForNode, labelForNode) {
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
		if (!lanes.has(node.profile_id)) {
			lanes.set(node.profile_id, {
				id: node.profile_id, ranks: new Map(), connections: new Map(),
			});
		}
		const lane = lanes.get(node.profile_id);
		if (!lane.ranks.has(node.rank)) lane.ranks.set(node.rank, []);
		lane.ranks.get(node.rank).push(node);
	}
	for (const link of graphData.links) {
		const source = nodesById.get(link.source);
		const target = nodesById.get(link.target);
		neighbors.get(source.id).push(target);
		neighbors.get(target.id).push(source);
		if (source.profile_id === target.profile_id) continue;
		for (const [from, to] of [[source, target], [target, source]]) {
			const connections = lanes.get(from.profile_id).connections;
			connections.set(to.profile_id, (connections.get(to.profile_id) || 0) + 1);
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
	let layoutHeight = 0;
	for (const lane of orderedLanes) {
		const stackHeight = Math.max(...[...lane.ranks.values()].map(nodes =>
			(nodes.length - 1) * DATASET_LAYOUT.nodeSpacing + nodes[0].cardHeight));
		lane.top = layoutHeight;
		lane.height = DATASET_LAYOUT.laneHeaderHeight + 2 * DATASET_LAYOUT.lanePadding + stackHeight;
		lane.center = lane.top + DATASET_LAYOUT.laneHeaderHeight
			+ DATASET_LAYOUT.lanePadding + stackHeight / 2;
		layoutHeight += lane.height + DATASET_LAYOUT.laneGap;
		for (const nodes of lane.ranks.values()) nodes.sort(compareNodes);
	}
	layoutHeight = Math.max(0, layoutHeight - DATASET_LAYOUT.laneGap);
	const positionRows = (rank = null) => {
		for (const lane of orderedLanes) {
			const groups = rank === null ? lane.ranks.values() : [lane.ranks.get(rank) || []];
			for (const nodes of groups) {
				nodes.forEach((node, index) => {
					node.fy = lane.center - layoutHeight / 2
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
				lane.ranks.get(rank)?.sort((a, b) => scores.get(a.id) - scores.get(b.id));
			}
			positionRows(rank);
		}
	}
	const rankWidths = new Map(ranksInOrder.map(rank => [
		rank, Math.max(...rankGroups.get(rank).map(node => node.cardWidth))
	]));
	const rankOffsets = new Map();
	let layoutWidth = 0;
	for (const rank of ranksInOrder) {
		rankOffsets.set(rank, layoutWidth + rankWidths.get(rank) / 2);
		layoutWidth += rankWidths.get(rank) + DATASET_LAYOUT.rankGap;
	}
	layoutWidth = Math.max(0, layoutWidth - DATASET_LAYOUT.rankGap);
	for (const rank of ranksInOrder) {
		for (const node of rankGroups.get(rank)) {
			node.fx = rankOffsets.get(rank) - layoutWidth / 2;
			node.x = node.fx;
			node.rankLeft = node.x - rankWidths.get(rank) / 2;
			node.rankRight = node.x + rankWidths.get(rank) / 2;
			const lane = lanes.get(node.profile_id);
			node.routeY = lane.top + lane.height - DATASET_LAYOUT.lanePadding / 2 - layoutHeight / 2;
		}
	}
	return {
		lanes: orderedLanes, width: layoutWidth, height: layoutHeight,
		columns: ranksInOrder.map(rank => ({
			rank,
			x: rankOffsets.get(rank) - layoutWidth / 2,
			width: rankWidths.get(rank) + DATASET_LAYOUT.rankGap,
		})),
		bounds: {
			x: 0, y: 0,
			width: layoutWidth + 2 * DATASET_LAYOUT.lanePadding,
			height: Math.max(1, layoutHeight),
		},
	};
}

function drawLineageLanes(layout, ctx, globalScale) {
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
		ctx.font = DATASET_LAYOUT.labelFont;
		ctx.fillStyle = DATASET_LAYOUT.labelColor;
		ctx.textAlign = 'left';
		ctx.textBaseline = 'middle';
		if (!layout.hideLaneLabels) {
			ctx.fillText(lane.name || lane.id, left + DATASET_LAYOUT.lanePadding,
				top + DATASET_LAYOUT.laneHeaderHeight / 2,
				width - 2 * DATASET_LAYOUT.lanePadding);
		}
	});
	ctx.restore();
}

function lineageLinkRoute(link) {
	return roundedRoute(link.routePoints);
}

function prepareLineageRoutes(data) {
	const endpointId = endpoint => typeof endpoint === 'object' ? endpoint.id : endpoint;
	const nodesById = new Map(data.nodes.map(node => [node.id, node]));
	for (const link of data.links) {
		link.routePoints = routeBetweenCards(
			nodesById.get(endpointId(link.source)), nodesById.get(endpointId(link.target)), data.nodes);
	}
}

function routeBetweenCards(source, target, nodes) {
	const margin = LINK_ROUTE.cornerRadius;
	const ports = node => [
		[[node.x + node.cardWidth / 2, node.y], [node.x + node.cardWidth / 2 + margin, node.y]],
		[[node.x - node.cardWidth / 2, node.y], [node.x - node.cardWidth / 2 - margin, node.y]],
		[[node.x, node.y + node.cardHeight / 2], [node.x, node.y + node.cardHeight / 2 + margin]],
		[[node.x, node.y - node.cardHeight / 2], [node.x, node.y - node.cardHeight / 2 - margin]],
	];
	const clear = route => route.slice(1).every((end, index) => {
		const start = route[index];
		return nodes.every(node => {
			const padding = node === source || node === target ? 0 : margin / 2;
			const left = node.x - node.cardWidth / 2 - padding;
			const right = node.x + node.cardWidth / 2 + padding;
			const top = node.y - node.cardHeight / 2 - padding;
			const bottom = node.y + node.cardHeight / 2 + padding;
			return start[0] === end[0]
				? start[0] <= left || start[0] >= right
					|| Math.max(start[1], end[1]) <= top || Math.min(start[1], end[1]) >= bottom
				: start[1] <= top || start[1] >= bottom
					|| Math.max(start[0], end[0]) <= left || Math.min(start[0], end[0]) >= right;
		});
	});
	const ys = [...new Set(nodes.flatMap(node => [
		node.y - node.cardHeight / 2 - margin, node.y + node.cardHeight / 2 + margin, node.routeY,
	]).filter(Number.isFinite))];
	const xs = [...new Set(nodes.flatMap(node => [
		node.x - node.cardWidth / 2 - margin, node.x + node.cardWidth / 2 + margin,
	]))];
	let best = null;
	let bestLength = Infinity;
	const consider = route => {
		const length = route.slice(1).reduce((sum, end, index) =>
			sum + Math.abs(end[0] - route[index][0]) + Math.abs(end[1] - route[index][1]), 0);
		if (length >= bestLength || !clear(route)) return;
		best = route;
		bestLength = length;
	};
	for (const [start, exit] of ports(source)) {
		for (const [end, entry] of ports(target)) {
			consider([start, exit, [entry[0], exit[1]], entry, end]);
			consider([start, exit, [exit[0], entry[1]], entry, end]);
			for (const x of [(exit[0] + entry[0]) / 2, ...xs]) {
				consider([start, exit, [x, exit[1]], [x, entry[1]], entry, end]);
			}
			for (const y of [(exit[1] + entry[1]) / 2, ...ys]) {
				consider([start, exit, [exit[0], y], [entry[0], y], entry, end]);
			}
		}
	}
	if (!best) throw new Error(`Unable to route lineage dependency ${source.id} -> ${target.id}`);
	return best;
}

function roundedRoute(route) {
	const vertices = [];
	for (const point of route) {
		const previous = vertices.at(-1);
		if (previous && point[0] === previous[0] && point[1] === previous[1]) continue;
		const before = vertices.at(-2);
		if (before && ((before[0] === previous[0] && previous[0] === point[0])
			|| (before[1] === previous[1] && previous[1] === point[1]))) vertices.pop();
		vertices.push(point);
	}
	const start = vertices[0];
	const end = vertices.at(-1);
	const corners = vertices.slice(1, -1);
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

function createLineageLinkRenderer(data, style, highlight) {
	data.links.forEach((link, index) => {
		link.flowOffset = index / Math.max(1, data.links.length);
	});
	return (link, ctx, globalScale) => {
		const points = lineageLinkRoute(link);
		const scale = Math.max(globalScale, MIN_RENDER_SCALE);
		const isHighlighted = highlight.isLinkHighlighted(link);
		const isTransitive = style.quiet_links && isHighlighted && highlight.isLinkDirect
			&& !highlight.isLinkDirect(link);
		const hasSelection = highlight.hasSelection();
		const linkColor = link.dependency_type === 'fragment'
			? style.function_colors?.merge || style.link_color : style.link_color;
		ctx.save();
		if (style.quiet_links && !isHighlighted) {
			ctx.globalAlpha = hasSelection ? LINK_STYLE.unrelatedOpacity : LINK_STYLE.overviewOpacity;
		} else if (isTransitive) {
			ctx.globalAlpha = LINK_STYLE.transitiveOpacity;
		}
		ctx.strokeStyle = isHighlighted
			? isTransitive ? LINK_STYLE.transitiveColor : LINK_STYLE.highlightColor
			: hasSelection ? LINK_STYLE.dimmedColor : linkColor;
		ctx.lineWidth = (isHighlighted ? isTransitive ? LINK_STYLE.transitiveWidth : LINK_STYLE.highlightWidth
			: style.quiet_links ? LINK_STYLE.overviewWidth : LINK_STYLE.width2D) / scale;
		ctx.lineCap = 'round';
		ctx.lineJoin = 'round';
		ctx.beginPath();
		ctx.moveTo(points[0][0], points[0][1]);
		for (const [x, y] of points.slice(1)) ctx.lineTo(x, y);
		ctx.stroke();

		const end = points[points.length - 1];
		const previous = points[points.length - 2];
		const angle = Math.atan2(end[1] - previous[1], end[0] - previous[0]);
		const screenArrowLength = LINK_ROUTE.arrowLength
			* (style.quiet_links && !isHighlighted ? LINK_STYLE.overviewArrowScale : 1) / scale;
		const arrowLength = Math.min(screenArrowLength, CARD_STYLE.height / 3);
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

		if (style.quiet_links && !isHighlighted) {
			ctx.restore();
			return;
		}
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
		ctx.fillStyle = isHighlighted
			? LINK_STYLE.highlightParticleColor
			: hasSelection ? LINK_STYLE.dimmedColor : linkColor;
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

export {
	createLineageLinkRenderer,
	drawLineageLanes,
	prepareLineageLayout,
	prepareLineageRoutes,
	lineageLinkRoute,
};
