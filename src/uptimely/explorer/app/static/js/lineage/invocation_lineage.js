import { ExplorerLineage } from './lineage_components.js';
import { initializeLineage } from './lineage_initializer.js';

export function initializeInvocationLineage(signal) {
	const STAGE_COLUMNS = Object.freeze({
		headerHeight: 48, background: 'rgba(143, 163, 181, .035)',
	});
	const { DATASET_LAYOUT } = ExplorerLineage;
	const invocationNodeDetails = document.getElementById('invocation-node-details');

	function formatList(values) {
		return Array.isArray(values) && values.length ? values.join(', ') : 'none';
	}

	function formatArguments(arguments_) {
		return Object.entries(arguments_ || {})
			.map(([name, value]) => `${name}=${JSON.stringify(value)}`)
			.join(', ') || 'none';
	}

	function appendOperatorLink(node) {
		if (!node.operator_id || !node.dataset_id) return;
		const row = document.createElement('div');
		row.className = 'meta';
		const label = document.createElement('strong');
		label.textContent = 'Owning operator: ';
		const link = document.createElement('a');
		const target = `operator-${node.dataset_id}-${node.operator_id}`;
		link.href = `?view=profiles#${encodeURIComponent(target)}`;
		link.textContent = node.operator_id;
		row.append(label, link);
		invocationNodeDetails.append(row);
	}

	function updateInvocationDetails(node) {
		if (!node) {
			ExplorerLineage.showDetails(invocationNodeDetails, 'invocation details', [],
				'Select an invocation to inspect its function kind, arguments, profile, declared features, and invocation dependencies.');
			return;
		}
		const rows = [
			['Profile', node.dataset_name || node.dataset_id],
			['Profile ID', node.dataset_id],
			['Phase', node.phase || 'compute'],
			['Stage', node.stage],
			['Function kind', node.function_kind || 'n/a'],
			['Function', node.function_name || node.function_id || 'n/a'],
			['Function ID', node.function_id || 'n/a'],
			['Arguments', formatArguments(node.arguments)],
			['Profile', node.profile || 'n/a'],
			[node.is_effect ? 'Declared feature outputs' : 'Produces',
				node.feature || (node.is_effect ? 'None' : 'n/a')],
		];
		if (node.phase === 'merge') {
			rows.push(
				['Merge target', node.merge_target],
				['Fragment source', node.fragment_source],
				['Merge keys', formatList(node.merge_keys)],
			);
		}
		if (node.is_effect && node.input_features?.length) {
			rows.push(['Declared inputs', formatList(node.input_features)]);
		}
		rows.push(['invocation dependencies', formatList(node.dependency_ids)]);
		ExplorerLineage.showDetails(invocationNodeDetails, 'invocation details', rows,
			node.phase === 'merge'
				? 'This merge invocation publishes the operator fragment into its target. Its status and dependencies are independent from the compute invocation.'
				: node.is_effect
				? 'Declared feature inputs and outputs define logical dependencies only. Dataframes are passed only through explicitly bound arguments; escape return values are ignored.'
				: '');
		appendOperatorLink(node);
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

	function createLineage3D(lineageContainer, graphData, updateSelection, style, highlight) {
		return ExplorerLineage.createLineage3D(lineageContainer, graphData, style, {
			label: node => `${node.phase === 'merge' ? 'Merge · ' : ''}${node.function_name || node.function_id}\n${node.is_effect ? 'declared outputs' : 'produces'}: ${node.feature || 'none'}`,
			color: node => node.phase === 'merge' ? node.mergeColor : node.datasetColor,
			onSelect: updateSelection,
			highlight,
			configure: forceGraph => forceGraph.linkDirectionalArrowLength(style.arrow_length)
				.linkDirectionalArrowRelPos(style.arrow_rel_pos),
			object: node => ExplorerLineage.datasetNodeObject(node, node.function_name || node.function_id, style),
		});
	}

	function createLineage2D(lineageContainer, graphData, updateSelection, style, highlight) {
		const layout = ExplorerLineage.prepareLineageLayout(
			graphData, node => node.stage - 1,
			node => `${node.phase === 'merge' ? 'Merge · ' : ''}${node.function_name || node.function_id}`);
		if (layout.columns.length) {
			layout.bounds.y -= STAGE_COLUMNS.headerHeight / 2;
			layout.bounds.height += STAGE_COLUMNS.headerHeight;
		}
		return ExplorerLineage.createLineage2D(lineageContainer, graphData, style, layout, highlight, {
			label: node => `${node.phase === 'merge' ? 'Merge · ' : ''}${node.label}\nprofile: ${node.dataset_name || node.dataset_id}\nstage: ${node.stage}`,
			drawNode: (node, ctx) =>
				ExplorerLineage.drawCard(
					node, ctx, `${node.phase === 'merge' ? 'Merge · ' : ''}${node.function_name || node.function_id}`,
					node.phase === 'merge' ? node.mergeColor : node.datasetColor, highlight),
			onSelect: updateSelection,
			renderOverlay: (ctx, scale) => drawStageColumns(layout, ctx, scale),
		});
	}

	initializeLineage(signal, updateInvocationDetails, createLineage2D, createLineage3D);
}
