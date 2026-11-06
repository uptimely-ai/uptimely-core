import { ExplorerLineage } from './lineage_components.js';
import { initializeLineage } from './lineage_initializer.js';
import { projectFeatureLineage } from './feature_projection.js';

export function initializeFeatureLineage(signal) {
	const DETAIL_VALUE_MAX_LENGTH = 220;
	const LINEAGE_LAYOUT_2D = Object.freeze({
		nodeRelativeSize: 6, functionValue: 7, featureValue: 5,
	});
	const { DATASET_LAYOUT } = ExplorerLineage;
	const nodeDetails = document.getElementById('node-details');

	function formatDetailValue(value) {
		return value == null ? 'n/a' : String(value).slice(0, DETAIL_VALUE_MAX_LENGTH);
	}

	function updateDetails(node) {
		if (!node) {
			ExplorerLineage.showDetails(nodeDetails, 'Selected item', [],
				'Select a feature or visible operator to see its identifier and details.');
			return;
		}
		const label = node.label || node.id || 'Unknown';
		if (node.is_operator === true) {
			const entrypoint = node.entrypoint || null;
			const features = Array.isArray(node.features) ? node.features : [];
			const outputLabel = node.is_effect ? 'Declared logical outputs' : 'Produces';
			const rows = [
				['Node type', 'Operator'],
				['Profile', node.profile || 'n/a'],
				['Profile', node.dataset_name || node.dataset_id],
				['Profile ID', node.dataset_id],
				['Operator', node.operator_id || label],
				['Function', node.function_name || node.function_id || 'n/a'],
				['Function ID', node.function_id || 'n/a'],
				['Function kind', node.function_kind || 'n/a'],
			];
			if (features.length) rows.push([outputLabel, formatDetailValue(features.join(', '))]);
			if (entrypoint) rows.push(['Entrypoint', formatDetailValue(entrypoint)]);
			ExplorerLineage.showDetails(nodeDetails, 'Selected item', rows,
				node.is_effect
					? 'Declared feature dependencies only; outputs are not materialized as dataframe columns.'
					: '');
			return;
		}
		const dataType = node.data_type || node.type || 'unknown';
		const profile = node.profile || 'n/a';
		ExplorerLineage.showDetails(nodeDetails, 'Selected item', [
			['Node type', 'Feature'], ['Feature', label], ['Feature ID', node.feature_id || node.id],
			['Profile', node.dataset_name || node.dataset_id], ['Profile ID', node.dataset_id],
			['Profile', formatDetailValue(profile)], ['Data type', formatDetailValue(dataType)],
		]);
	}

	function createLineage2D(lineageContainer, graphData, updateSelection, style, highlight) {
		const functionColor = style.function_color;
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
		const layout = ExplorerLineage.prepareLineageLayout(
			graphData, node => nodeRanks.get(node.id), node => node.label || node.id);
		const drawNode = (node, ctx) => {
			const isOperator = node.is_operator === true;
			const color = isOperator ? functionColor : node.datasetColor;
			ExplorerLineage.drawCard(node, ctx, node.label || node.id, color, highlight, !isOperator);
		};
		return ExplorerLineage.createLineage2D(lineageContainer, graphData, style, layout, highlight, {
			label: node => `${node.is_operator ? 'operator' : 'feature'}: ${node.label}\nprofile: ${node.profile || 'n/a'}`,
			color: node => node.is_operator ? functionColor : node.datasetColor,
			nodeValue: node => node.is_operator
				? LINEAGE_LAYOUT_2D.functionValue : LINEAGE_LAYOUT_2D.featureValue,
			nodeRelativeSize: LINEAGE_LAYOUT_2D.nodeRelativeSize,
			drawNode,
			onSelect: updateSelection,
		});
	}

	function createLineage3D(lineageContainer, graphData, updateSelection, style, highlight) {
		const functionColor = style.function_color;
		return ExplorerLineage.createLineage3D(lineageContainer, graphData, style, {
			label: node => `${node.is_operator ? 'function' : 'feature'}: ${node.label}\nprofile: ${node.profile || 'n/a'}`,
			color: node => node.is_operator ? functionColor : node.datasetColor,
			onSelect: updateSelection,
			highlight,
			configure: forceGraph => forceGraph.linkDirectionalArrowLength(style.arrow_length)
				.linkDirectionalArrowRelPos(style.arrow_rel_pos),
			object: node => {
				if (!node.is_operator) {
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

	return initializeLineage(signal, updateDetails, createLineage2D, createLineage3D,
		projectFeatureLineage);
}
