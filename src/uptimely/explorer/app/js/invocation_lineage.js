import { ExplorerLineage } from './lineage_components.js';
import { mountLineageViews } from './lineage_view_controller.js';

const STAGE_COLUMNS = Object.freeze({
	headerHeight: 48, background: 'rgba(143, 163, 181, .035)',
});
const { DATASET_LAYOUT } = ExplorerLineage;
const invocationGraphData = ExplorerLineage.readPayload('graph-data');
const style = ExplorerLineage.readPayload('graph-style');
ExplorerLineage.prepareDatasetColors(invocationGraphData, document.getElementById('dataset-legend'));
const invocationNodeDetails = document.getElementById('invocation-node-details');

function formatList(values) {
	return Array.isArray(values) && values.length ? values.join(', ') : 'none';
}

function formatArguments(arguments_) {
	return Object.entries(arguments_ || {})
		.map(([name, value]) => `${name}=${JSON.stringify(value)}`)
		.join(', ') || 'none';
}

function updateInvocationDetails(node) {
	if (!node) {
		ExplorerLineage.showDetails(invocationNodeDetails, 'invocation details', [],
			'Select an invocation to inspect its function kind, arguments, entity, declared features, and invocation dependencies.');
		return;
	}
	const rows = [
		['Dataset', node.dataset_id],
		['Stage', node.stage],
		['Function kind', node.function_kind || 'n/a'],
		['Function', node.function_id || 'n/a'],
		['Arguments', formatArguments(node.arguments)],
		['Entity', node.entity || 'n/a'],
		[node.function_kind === 'escape' ? 'Declared feature outputs' : 'Produces',
			node.feature || (node.function_kind === 'escape' ? 'None' : 'n/a')],
	];
	if (node.function_kind === 'escape' && node.input_features?.length) {
		rows.push(['Declared inputs', formatList(node.input_features)]);
	}
	rows.push(['invocation dependencies', formatList(node.dependency_ids)]);
	ExplorerLineage.showDetails(invocationNodeDetails, 'invocation details', rows,
		node.function_kind === 'escape'
			? 'Declared feature inputs and outputs define logical dependencies only. Dataframes are passed only through explicitly bound arguments; escape return values are ignored.'
			: '');
}

function drawStageColumns(layout, ctx, scale) {
	const top = -layout.height / 2 - STAGE_COLUMNS.headerHeight;
	const bottom = layout.height / 2;
	const left = -layout.bounds.width / 2;
	const right = layout.bounds.width / 2;
	ctx.save();
	ctx.font = DATASET_LAYOUT.labelFont;
	ctx.textAlign = 'center';
	ctx.textBaseline = 'middle';
	ctx.lineWidth = 1 / Math.max(scale, ExplorerLineage.MIN_RENDER_SCALE);
	ctx.strokeStyle = DATASET_LAYOUT.borderColor;
	layout.columns.forEach((column, index) => {
		const columnLeft = index === 0 ? left : column.x - column.width / 2;
		const columnRight = index === layout.columns.length - 1
			? right : column.x + column.width / 2;
		if (index % 2 === 0) {
			ctx.fillStyle = STAGE_COLUMNS.background;
			ctx.fillRect(columnLeft, top, columnRight - columnLeft, bottom - top);
		}
		ctx.beginPath();
		ctx.moveTo(columnLeft, top);
		ctx.lineTo(columnLeft, bottom);
		if (index === layout.columns.length - 1) {
			ctx.moveTo(columnRight, top);
			ctx.lineTo(columnRight, bottom);
		}
		ctx.stroke();
		ctx.fillStyle = DATASET_LAYOUT.labelColor;
		ctx.fillText(`Stage ${column.rank + 1}`, column.x,
			top + STAGE_COLUMNS.headerHeight / 2, columnRight - columnLeft);
	});
	ctx.restore();
}

function createLineage3D(lineageContainer, graphData, updateSelection) {
	const highlight = ExplorerLineage.createLineageHighlight(graphData);
	return ExplorerLineage.createLineage3D(lineageContainer, graphData, style, {
		label: node => `${node.function_id}\n${node.function_kind === 'escape' ? 'declared outputs' : 'produces'}: ${node.feature || 'none'}`,
		color: node => node.datasetColor,
		onSelect: updateSelection,
		highlight,
		configure: forceGraph => forceGraph.linkDirectionalArrowLength(style.arrow_length)
			.linkDirectionalArrowRelPos(style.arrow_rel_pos),
		object: node => ExplorerLineage.datasetNodeObject(node, node.function_id, style),
	});
}

function createLineage2D(lineageContainer, graphData, updateSelection) {
	const highlight = ExplorerLineage.createLineageHighlight(graphData);
	const layout = ExplorerLineage.prepareDatasetLayout(
		graphData, node => node.stage - 1, node => node.function_id);
	if (layout.columns.length) {
		layout.bounds.y -= STAGE_COLUMNS.headerHeight / 2;
		layout.bounds.height += STAGE_COLUMNS.headerHeight;
	}
	return ExplorerLineage.createDatasetLineage2D(lineageContainer, graphData, style, layout, highlight, {
		label: node => `${node.label}\ndataset: ${node.dataset_id}\nstage: ${node.stage}`,
		drawNode: (node, ctx) =>
			ExplorerLineage.drawCard(node, ctx, node.function_id, node.datasetColor, highlight),
		onSelect: updateSelection,
		renderOverlay: (ctx, scale) => drawStageColumns(layout, ctx, scale),
	});
}

mountLineageViews(
	invocationGraphData, createLineage2D, createLineage3D,
	updateInvocationDetails);
