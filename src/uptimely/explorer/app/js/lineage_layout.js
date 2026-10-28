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
			const lane = lanes.get(node.dataset_id);
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
		const isHighlighted = highlight.isLinkHighlighted(link);
		const hasSelection = highlight.hasSelection();
		ctx.save();
		ctx.strokeStyle = isHighlighted
			? LINK_STYLE.highlightColor
			: hasSelection ? LINK_STYLE.dimmedColor : style.link_color;
		ctx.lineWidth = (isHighlighted ? LINK_STYLE.highlightWidth : LINK_STYLE.width2D) / scale;
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
		ctx.fillStyle = isHighlighted
			? LINK_STYLE.highlightParticleColor
			: hasSelection ? LINK_STYLE.dimmedColor : LINK_ROUTE.particleColor;
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
	createDatasetLinkRenderer,
	drawDatasetLanes,
	prepareDatasetLayout,
};
