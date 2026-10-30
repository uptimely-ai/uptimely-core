import { ExplorerLineage } from './lineage_components.js';
import { mountLineageViews } from './lineage_view_controller.js';

const DETAIL_VALUE_MAX_LENGTH = 220;
const LINEAGE_LAYOUT_2D = Object.freeze({
	nodeRelativeSize: 6, functionValue: 7, featureValue: 5,
});
const { DATASET_LAYOUT } = ExplorerLineage;
const graphData = ExplorerLineage.readPayload('graph-data');
const style = ExplorerLineage.readPayload('graph-style');
const functionColor = style.function_color;
ExplorerLineage.prepareDatasetColors(graphData, document.getElementById('dataset-legend'));
const nodeDetails = document.getElementById('node-details');

function formatDetailValue(value) {
	return value == null ? 'n/a' : String(value).slice(0, DETAIL_VALUE_MAX_LENGTH);
}

function updateDetails(node) {
	if (!node) {
		ExplorerLineage.showDetails(nodeDetails, 'Selected item', [],
			'Select any feature in the lineage to see its identifier and details.');
		return;
	}
	const label = node.label || node.id || 'Unknown';
	if (node.is_action === true) {
		const entrypoint = node.entrypoint || null;
		const features = Array.isArray(node.features) ? node.features : [];
		const outputLabel = node.function_kind === 'escape' ? 'Declared logical outputs' : 'Produces';
		const rows = [
			['Node type', 'Action'],
			['Dataset', node.dataset_id],
			['Action', node.action_id || label],
			['Function', node.function_id || 'n/a'],
			['Function kind', node.function_kind || 'n/a'],
		];
		if (features.length) rows.push([outputLabel, formatDetailValue(features.join(', '))]);
		if (entrypoint) rows.push(['Entrypoint', formatDetailValue(entrypoint)]);
		ExplorerLineage.showDetails(nodeDetails, 'Selected item', rows,
			node.function_kind === 'escape'
				? 'Declared feature dependencies only; outputs are not materialized as dataframe columns.'
				: '');
		return;
	}
	const dataType = node.data_type || node.type || 'unknown';
	const entity = node.entity || 'n/a';
	ExplorerLineage.showDetails(nodeDetails, 'Selected item', [
		['Node type', 'Feature'], ['Feature', label], ['Dataset', node.dataset_id],
		['Entity', formatDetailValue(entity)], ['Data type', formatDetailValue(dataType)],
	]);
}

function createLineage2D(lineageContainer, graphData, updateSelection) {
	const highlight = ExplorerLineage.createLineageHighlight(graphData);
	function rankNodes(data) {
		const children = new Map(data.nodes.map(node => [node.id, []]));
		const indegree = new Map(data.nodes.map(node => [node.id, 0]));
		for (const link of data.links) {
			children.get(link.source)?.push(link.target);
			indegree.set(link.target, (indegree.get(link.target) || 0) + 1);
		}
		const ranks = new Map(data.nodes.map(node => [node.id, 0]));
		const queue = data.nodes
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
		const unresolved = data.nodes
			.filter(node => indegree.get(node.id) > 0)
			.sort((a, b) => a.id.localeCompare(b.id));
		for (const node of unresolved) ranks.set(node.id, maxRank + 1);
		return ranks;
	}

	const nodeRanks = rankNodes(graphData);
	const layout = ExplorerLineage.prepareDatasetLayout(
		graphData, node => nodeRanks.get(node.id), node => node.label || node.id);
	const drawNode = (node, ctx) => {
		const isAction = node.is_action === true;
		const color = isAction ? functionColor : node.datasetColor;
		ExplorerLineage.drawCard(node, ctx, node.label || node.id, color, highlight, !isAction);
	};
	return ExplorerLineage.createDatasetLineage2D(lineageContainer, graphData, style, layout, highlight, {
		label: node => `${node.is_action ? 'action' : 'feature'}: ${node.label}\nentity: ${node.entity || 'n/a'}`,
		color: node => node.is_action ? functionColor : node.datasetColor,
		nodeValue: node => node.is_action
			? LINEAGE_LAYOUT_2D.functionValue : LINEAGE_LAYOUT_2D.featureValue,
		nodeRelativeSize: LINEAGE_LAYOUT_2D.nodeRelativeSize,
		drawNode,
		onSelect: updateSelection,
	});
}

function createLineage3D(lineageContainer, graphData, updateSelection) {
	const highlight = ExplorerLineage.createLineageHighlight(graphData);
	return ExplorerLineage.createLineage3D(lineageContainer, graphData, style, {
		label: node => `${node.is_action ? 'function' : 'feature'}: ${node.label}\nentity: ${node.entity || 'n/a'}`,
		color: node => node.is_action ? functionColor : node.datasetColor,
		onSelect: updateSelection,
		highlight,
		configure: forceGraph => forceGraph.linkDirectionalArrowLength(style.arrow_length)
			.linkDirectionalArrowRelPos(style.arrow_rel_pos),
		object: node => {
			if (!node.is_action) {
				return ExplorerLineage.datasetNodeObject(node, node.label, style);
			}
			const mesh = new THREE.Mesh(
				new THREE.OctahedronGeometry(style.function_node_size, 0),
				new THREE.MeshLambertMaterial({ color: functionColor }),
			);
			return ExplorerLineage.labeledMesh(mesh, node.label, style, 14);
		},
	});
}

mountLineageViews(graphData, createLineage2D, createLineage3D, updateDetails);
