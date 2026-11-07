import { ExplorerLineage } from './lineage_components.js';
import { initializeLineage } from './lineage_initializer.js';
import { KINDS } from '../rendering/shared_markup.js';
import {
	drawDatasetMarkers, drawMainframeSpines, invocationColor, invocationContribution, invocationFlowDetails, invocationLabel, invocationRole, isDefaultMerge,
	prepareInvocationLayout,
} from './invocation_layout.js';

export function initializeInvocationLineage(signal) {
	const STAGE_COLUMNS = Object.freeze({
		headerHeight: 48, background: 'rgba(143, 163, 181, .035)',
	});
	const { DATASET_LAYOUT } = ExplorerLineage;
	const invocationNodeDetails = document.getElementById('invocation-node-details');
	let scoped = false;
	const automaticDescription = node => isDefaultMerge(node) ? '\nAutomatically supplied default merge' : '';

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
		link.textContent = node.operator_name || node.operator_id.replace(/[_-]/g, ' ')
			.replace(/\b\w/g, letter => letter.toUpperCase());
		row.append(label, link);
		invocationNodeDetails.append(row);
	}

	function updateInvocationDetails(node, fullLineage = true) {
		if (!node) {
			ExplorerLineage.showDetails(invocationNodeDetails, 'invocation details', [],
				'Select an invocation to inspect its function kind, arguments, profile, declared features, and invocation dependencies.');
			return;
		}
		const rows = [
			['Highlight', fullLineage ? 'All upstream sources and downstream consumers'
				: 'Immediate inputs and consumers only'],
			['Profile', node.dataset_name || node.dataset_id],
			['Profile ID', node.dataset_id],
			['Phase', invocationRole(node) === 'merge' ? 'merge' : 'compute'],
			['Stage', node.stage],
			['Function kind', node.function_kind || 'n/a'],
			['Function', invocationLabel(node)],
			['Function ID', node.function_id || 'n/a'],
			['Arguments', formatArguments(node.arguments)],
			['Profile', node.profile || 'n/a'],
			[node.is_effect ? 'Declared feature outputs' : 'Produces',
				node.feature || (node.is_effect ? 'None' : 'n/a')],
		];
		if (invocationRole(node) === 'merge') {
			rows.push(
				['Merge target', node.merge_target ?? node.arguments?.target],
				['Fragment source', node.fragment_source ?? node.arguments?.fragment],
				['Merge keys', formatList(node.merge_keys ?? node.arguments?.target_keys)],
			);
			if (isDefaultMerge(node)) rows.push(['Binding', 'Automatically supplied default merge']);
		}
		if (node.is_effect && node.input_features?.length) {
			rows.push(['Declared inputs', formatList(node.input_features)]);
		}
		rows.push(['invocation dependencies', formatList(node.dependency_ids)]);
		ExplorerLineage.showDetails(invocationNodeDetails, 'invocation details', rows,
			`${invocationFlowDetails(node, scoped)} ${invocationRole(node) === 'merge'
				? 'Publishes the operator fragment; compute and merge are separate invocations.'
				: node.is_effect
				? 'Declared feature inputs and outputs define logical dependencies only. Dataframes are passed only through explicitly bound arguments; escape return values are ignored.'
				: ''}`.trim());
		appendOperatorLink(node);
	}

	function drawStageColumns(layout, ctx, scale) {
		const top = -layout.height / 2 - STAGE_COLUMNS.headerHeight;
		const bottom = layout.height / 2;
		const left = -layout.gridBounds.width / 2;
		const right = layout.gridBounds.width / 2;
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
		scoped = graphData.is_scoped === true;
		return ExplorerLineage.createLineage3D(lineageContainer, graphData, { ...style, quiet_links: true }, {
			label: node => `${invocationLabel(node)}${automaticDescription(node)}\noperator: ${node.operator_id}\n${invocationContribution(node)}`,
			color: invocationColor,
			onSelect: updateSelection,
			highlight,
			configure: forceGraph => forceGraph.linkDirectionalArrowLength(link =>
				highlight.isLinkDirect(link) ? style.arrow_length
					: style.arrow_length * ExplorerLineage.LINK_STYLE.overviewArrowScale)
				.linkDirectionalArrowRelPos(style.arrow_rel_pos),
			object: node => {
				const role = invocationRole(node);
				const geometry = role === 'merge'
					? new THREE.OctahedronGeometry(style.feature_node_size, 0)
					: role === 'enrich'
						? new THREE.BoxGeometry(style.feature_node_size, style.feature_node_size, style.feature_node_size)
						: new THREE.SphereGeometry(style.feature_node_size,
							ExplorerLineage.NODE_STYLE_3D.sphereWidthSegments,
							ExplorerLineage.NODE_STYLE_3D.sphereHeightSegments);
				const mesh = new THREE.Mesh(geometry, new THREE.MeshLambertMaterial({
					color: invocationColor(node),
				}));
				return ExplorerLineage.labeledMesh(mesh, invocationLabel(node), style,
					ExplorerLineage.NODE_STYLE_3D.labelOffset, null,
					KINDS[node.function_kind]?.icon || 'square-function',
					isDefaultMerge(node) ? 'sparkles' : null);
			},
		});
	}

	function createLineage2D(lineageContainer, graphData, updateSelection, style, highlight) {
		scoped = graphData.is_scoped === true;
		const layout = prepareInvocationLayout(graphData);
		if (layout.columns.length) {
			layout.bounds.y -= STAGE_COLUMNS.headerHeight / 2;
			layout.bounds.height += STAGE_COLUMNS.headerHeight;
		}
		return ExplorerLineage.createLineage2D(lineageContainer, graphData,
			{ ...style, quiet_links: true }, layout, highlight, {
			label: node => `${invocationLabel(node)}${automaticDescription(node)}\noperator: ${node.operator_id}\nprofile: ${node.dataset_name || node.dataset_id}\nstage: ${node.stage}\n${invocationContribution(node)}`,
			drawNode: (node, ctx) =>
				ExplorerLineage.drawCard(
					node, ctx, invocationLabel(node),
					invocationColor(node), highlight, false,
					{
						iconName: KINDS[node.function_kind]?.icon || 'square-function',
						badgeIconName: isDefaultMerge(node) ? 'sparkles' : null,
					}),
			onSelect: updateSelection,
			renderOverlay: (ctx, scale) => {
				drawStageColumns(layout, ctx, scale);
				drawMainframeSpines(layout, ctx, scale);
				drawDatasetMarkers(layout, ctx, scale, ExplorerLineage.drawIcon);
			},
		});
	}

	initializeLineage(signal, updateInvocationDetails, createLineage2D, createLineage3D);
}
