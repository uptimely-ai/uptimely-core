import { CARD_STYLE, DATASET_LAYOUT, MIN_RENDER_SCALE } from './lineage_config.js';
import { prepareLineageLayout, prepareLineageRoutes } from './lineage_layout.js';

const INVOCATION_LAYOUT = Object.freeze({
	cardHeight: CARD_STYLE.height, rowGap: 58, trackGap: 48, footerHeight: 28,
	spineWidth: 5, spineOpacity: 0.28,
	groupPadding: 12, groupRadius: 16, groupFillOpacity: 0.08, groupBorderOpacity: 0.3,
});
const DEFAULT_MERGE_FUNCTION_ID = '__uptimely_merge_by_grain';
const DATASET_MARKERS = Object.freeze({
	gap: 32, padding: 16, iconSize: 20, badgeSize: 36, radius: 9,
	minLabelWidth: 140, labelGap: 12, connectorLength: 24,
});

export function isDefaultMerge(node) {
	return invocationRole(node) === 'merge' && node.function_id === DEFAULT_MERGE_FUNCTION_ID;
}

export function invocationRole(node) {
	if (node.function_kind === 'merge' || node.phase === 'merge') return 'merge';
	if (node.function_kind === 'vectorize') return 'enrich';
	return node.is_effect ? 'effect' : 'compute';
}

export function invocationColor(node) {
	return ['merge', 'enrich'].includes(invocationRole(node))
		? node.datasetColor : DATASET_LAYOUT.labelColor;
}

export function invocationLabel(node) {
	if (isDefaultMerge(node)) return 'Merge by grain';
	const name = node.function_name || node.function_id || node.label || node.id;
	return invocationRole(node) === 'merge'
		? name.replace(/_/g, ' ').replace(/^\w/, letter => letter.toUpperCase()) : name;
}

export function invocationContribution(node) {
	const outputs = node.feature || 'none declared';
	const role = invocationRole(node);
	return `${role === 'merge' ? 'Publishes' : role === 'enrich' ? 'Adds' : 'Declared outputs'}: ${outputs}`;
}

export function invocationFlowDetails(node, scoped = false) {
	const role = invocationRole(node);
	const placement = ['merge', 'enrich'].includes(role)
		? 'Profile color: Dataset contributor. Same-stage groups imply no order.'
		: role === 'effect' ? 'Gray: separate Dataset consumer or effect.'
			: 'Gray: compute branch above the Dataset spine.';
	return `${placement} Spine / start / ${scoped ? 'Selected outputs ready' : 'Dataset ready'}: plan accumulation, not runtime status. Arrows: dependencies; direct links are strongest, full lineage lighter.`;
}

export function prepareInvocationLayout(data) {
	const layout = prepareLineageLayout(data, node => node.stage - 1, invocationLabel);
	for (const node of data.nodes) {
		if (isDefaultMerge(node)) {
			node.cardWidth = Math.min(CARD_STYLE.maxWidth,
				node.cardWidth + CARD_STYLE.featureIconSize + CARD_STYLE.iconLeft);
		}
	}
	const isPublisher = node => ['merge', 'enrich'].includes(invocationRole(node));
	let width = 0;
	for (const column of layout.columns) {
		column.cardWidth = Math.max(...layout.lanes.map(lane => {
			const nodes = lane.ranks.get(column.rank) || [];
			return Math.max(0, ...nodes.map(node => node.cardWidth));
		}));
		column.x = width + column.cardWidth / 2;
		column.width = column.cardWidth + DATASET_LAYOUT.rankGap;
		width += column.width;
	}
	width = Math.max(0, width - DATASET_LAYOUT.rankGap);
	for (const column of layout.columns) {
		column.x -= width / 2;
		for (const lane of layout.lanes) {
			const nodes = lane.ranks.get(column.rank) || [];
			for (const node of nodes) {
				node.x = node.fx = column.x;
				node.rankLeft = column.x - column.cardWidth / 2;
				node.rankRight = column.x + column.cardWidth / 2;
			}
		}
	}
	layout.width = width;
	layout.bounds.width = width + 2 * DATASET_LAYOUT.lanePadding;
	let height = 0;
	for (const lane of layout.lanes) {
		const groups = [...lane.ranks.values()];
		const count = predicate => Math.max(0, ...groups.map(nodes => nodes.filter(predicate).length));
		const computeCount = count(node => invocationRole(node) === 'compute');
		const effectCount = count(node => invocationRole(node) === 'effect');
		const publishCount = count(isPublisher);
		const trackHeight = count => count ? (count - 1) * INVOCATION_LAYOUT.rowGap
			+ INVOCATION_LAYOUT.cardHeight : 0;
		const computeHeight = trackHeight(computeCount);
		const publishHeight = Math.max(INVOCATION_LAYOUT.cardHeight, trackHeight(publishCount));
		lane.top = height;
		lane.spineY = lane.top + DATASET_LAYOUT.laneHeaderHeight + DATASET_LAYOUT.lanePadding
			+ computeHeight + (computeCount ? INVOCATION_LAYOUT.trackGap : 0) + publishHeight / 2;
		lane.height = DATASET_LAYOUT.laneHeaderHeight + 2 * DATASET_LAYOUT.lanePadding
			+ computeHeight + publishHeight + trackHeight(effectCount)
			+ (computeCount ? INVOCATION_LAYOUT.trackGap : 0)
			+ (effectCount ? INVOCATION_LAYOUT.trackGap : 0) + INVOCATION_LAYOUT.footerHeight;
		lane.name = groups.flat()[0].dataset_name || lane.id;
		lane.color = groups.flat()[0].datasetColor;
		lane.publicationGroups = [];
		for (const nodes of groups) {
			const compute = nodes.filter(node => invocationRole(node) === 'compute');
			const publishers = nodes.filter(node => ['merge', 'enrich'].includes(invocationRole(node)));
			const effects = nodes.filter(node => invocationRole(node) === 'effect');
			const place = (nodes, center) => nodes.forEach((node, index) => {
				node.cardHeight = INVOCATION_LAYOUT.cardHeight;
				node.y = node.fy = center + (index - (nodes.length - 1) / 2) * INVOCATION_LAYOUT.rowGap;
				node.routeY = lane.top + lane.height - INVOCATION_LAYOUT.footerHeight
					- DATASET_LAYOUT.lanePadding / 2;
			});
			place(compute, lane.spineY - publishHeight / 2 - INVOCATION_LAYOUT.trackGap - computeHeight / 2);
			place(publishers, lane.spineY);
			place(effects, lane.spineY + publishHeight / 2 + INVOCATION_LAYOUT.trackGap
				+ trackHeight(effectCount) / 2);
			if (publishers.length > 1) lane.publicationGroups.push(publishers);
		}
		height += lane.height + DATASET_LAYOUT.laneGap;
	}
	height = Math.max(0, height - DATASET_LAYOUT.laneGap);
	for (const lane of layout.lanes) {
		lane.spineY -= height / 2;
	}
	for (const node of data.nodes) {
		node.y = node.fy -= height / 2;
		node.routeY -= height / 2;
	}
	layout.height = height;
	layout.bounds.height = Math.max(1, height);
	layout.gridBounds = { ...layout.bounds };
	layout.hideLaneLabels = true;
	const startWidth = Math.max(DATASET_MARKERS.minLabelWidth,
		...layout.lanes.map(lane => lane.name.length * CARD_STYLE.characterWidth));
	const readyWidth = Math.max(DATASET_MARKERS.minLabelWidth,
		'Selected outputs ready'.length * CARD_STYLE.characterWidth);
	const markerWidth = textWidth => DATASET_MARKERS.badgeSize
		+ DATASET_MARKERS.labelGap + textWidth + 2 * DATASET_MARKERS.padding;
	const startExtent = markerWidth(startWidth) + DATASET_MARKERS.gap;
	const endExtent = markerWidth(readyWidth) + DATASET_MARKERS.gap;
	for (const lane of layout.lanes) {
		lane.datasetStart = {
			x: -layout.gridBounds.width / 2 - startExtent, y: lane.spineY,
			width: markerWidth(startWidth), label: lane.name, caption: 'Dataset',
		};
		const publishesDataset = [...lane.ranks.values()].some(nodes => nodes.some(isPublisher));
		lane.datasetReady = {
			x: layout.gridBounds.width / 2 + DATASET_MARKERS.gap, y: lane.spineY,
			width: markerWidth(readyWidth), available: publishesDataset, label: publishesDataset
				? data.is_scoped ? 'Selected outputs ready' : 'Dataset ready' : 'No dataset produced',
		};
	}
	layout.bounds.width += startExtent + endExtent;
	layout.bounds.x = (endExtent - startExtent) / 2;
	prepareLineageRoutes(data);
	return layout;
}

export function drawMainframeSpines(layout, ctx, scale) {
	ctx.save();
	const renderScale = Math.max(scale, MIN_RENDER_SCALE);
	for (const lane of layout.lanes) {
		const left = lane.datasetStart.x + lane.datasetStart.width + DATASET_MARKERS.connectorLength;
		const right = lane.datasetReady.x;
		ctx.strokeStyle = lane.color;
		ctx.globalAlpha = INVOCATION_LAYOUT.spineOpacity;
		ctx.lineWidth = INVOCATION_LAYOUT.spineWidth / renderScale;
		ctx.lineCap = 'round';
		let segmentStart = left;
		for (const nodes of [...lane.publicationGroups].sort((a, b) => a[0].x - b[0].x)) {
			const x = Math.min(...nodes.map(node => node.x - node.cardWidth / 2))
				- INVOCATION_LAYOUT.groupPadding;
			const groupRight = Math.max(...nodes.map(node => node.x + node.cardWidth / 2))
				+ INVOCATION_LAYOUT.groupPadding;
			const top = nodes[0].y - INVOCATION_LAYOUT.cardHeight / 2 - INVOCATION_LAYOUT.groupPadding;
			const bottom = nodes.at(-1).y + INVOCATION_LAYOUT.cardHeight / 2
				+ INVOCATION_LAYOUT.groupPadding;
			ctx.globalAlpha = INVOCATION_LAYOUT.spineOpacity;
			ctx.lineWidth = INVOCATION_LAYOUT.spineWidth / renderScale;
			ctx.beginPath();
			ctx.moveTo(segmentStart, lane.spineY);
			ctx.lineTo(x, lane.spineY);
			ctx.stroke();
			segmentStart = groupRight;
			ctx.beginPath();
			ctx.roundRect(x, top, groupRight - x, bottom - top, INVOCATION_LAYOUT.groupRadius);
			ctx.fillStyle = lane.color;
			ctx.globalAlpha = nodes.some(node => invocationRole(node) === 'enrich')
				? INVOCATION_LAYOUT.spineOpacity : INVOCATION_LAYOUT.groupFillOpacity;
			ctx.fill();
			if (!nodes.some(node => invocationRole(node) === 'enrich')) {
				ctx.globalAlpha = INVOCATION_LAYOUT.groupBorderOpacity;
				ctx.lineWidth = 1 / renderScale;
				ctx.stroke();
			}
		}
		ctx.globalAlpha = INVOCATION_LAYOUT.spineOpacity;
		ctx.lineWidth = INVOCATION_LAYOUT.spineWidth / renderScale;
		ctx.beginPath();
		ctx.moveTo(segmentStart, lane.spineY);
		ctx.lineTo(right, lane.spineY);
		ctx.stroke();
	}
	ctx.restore();
}

export function drawDatasetMarkers(layout, ctx, scale, drawIcon) {
	ctx.save();
	for (const lane of layout.lanes) {
		for (const [marker, ready] of [[lane.datasetStart, false], [lane.datasetReady, true]]) {
			const filled = ready && marker.available;
			const badgeX = ready ? marker.x + DATASET_MARKERS.padding
				: marker.x + marker.width - DATASET_MARKERS.padding - DATASET_MARKERS.badgeSize;
			const halfBadge = DATASET_MARKERS.badgeSize / 2;
			ctx.globalAlpha = 1;
			ctx.lineWidth = CARD_STYLE.borderWidth / Math.max(scale, MIN_RENDER_SCALE);
			ctx.strokeStyle = lane.color;
			ctx.fillStyle = filled ? lane.color : CARD_STYLE.background;
			ctx.beginPath();
			ctx.roundRect(badgeX, marker.y - halfBadge,
				filled ? marker.width - 2 * DATASET_MARKERS.padding : DATASET_MARKERS.badgeSize,
				DATASET_MARKERS.badgeSize, DATASET_MARKERS.radius);
			ctx.fill();
			ctx.stroke();
			drawIcon(ctx, 'table-2', badgeX + (DATASET_MARKERS.badgeSize - DATASET_MARKERS.iconSize) / 2,
				marker.y - DATASET_MARKERS.iconSize / 2, DATASET_MARKERS.iconSize,
				filled ? CARD_STYLE.background : lane.color);
			const textX = ready ? badgeX + DATASET_MARKERS.badgeSize + DATASET_MARKERS.labelGap
				: badgeX - DATASET_MARKERS.labelGap;
			const textWidth = ready ? marker.width - (textX - marker.x) - DATASET_MARKERS.padding
				: textX - marker.x - DATASET_MARKERS.padding;
			ctx.textAlign = ready ? 'left' : 'right';
			ctx.textBaseline = 'middle';
			ctx.font = CARD_STYLE.font;
			ctx.fillStyle = filled ? CARD_STYLE.background : CARD_STYLE.textColor;
			ctx.fillText(marker.label, textX, marker.y - (marker.caption ? CARD_STYLE.titleOffset : 0),
				textWidth);
			if (marker.caption) {
				ctx.font = CARD_STYLE.subtitleFont;
				ctx.fillStyle = DATASET_LAYOUT.labelColor;
				ctx.fillText(marker.caption, textX, marker.y + CARD_STYLE.subtitleOffset, textWidth);
				const end = marker.x + marker.width;
				ctx.fillStyle = lane.color;
				ctx.globalAlpha = INVOCATION_LAYOUT.spineOpacity;
				ctx.beginPath();
				ctx.moveTo(end, marker.y);
				ctx.lineTo(end + DATASET_MARKERS.connectorLength,
					marker.y - INVOCATION_LAYOUT.spineWidth / 2);
				ctx.lineTo(end + DATASET_MARKERS.connectorLength,
					marker.y + INVOCATION_LAYOUT.spineWidth / 2);
				ctx.closePath();
				ctx.fill();
			}
		}
	}
	ctx.restore();
}
