import { ExplorerLineage } from './lineage_components.js';
import { initializeLineage } from './lineage_initializer.js';
import { projectFeatureLineage } from './feature_projection.js';
import { ICONS, KINDS, dataTypeIconName } from '../rendering/shared_markup.js';

export function initializeFeatureLineage(signal) {
	const LINEAGE_LAYOUT_2D = Object.freeze({
		nodeRelativeSize: 6, functionValue: 7, featureValue: 5,
	});
	const { DATASET_LAYOUT } = ExplorerLineage;
	const nodeDetails = document.getElementById('node-details');

	function updateDetails(node) {
		if (!node) {
			ExplorerLineage.showDetails(nodeDetails, 'No node selected', [],
				'Select a feature or operator to inspect its definition and connections.');
			return;
		}
		const label = node.label || node.id || 'Unknown';
		const profileSection = {
			title: 'Profile', icon: 'layers-2', rows: [
				['Name', node.profile_name || node.profile_id || node.profile],
				['Profile ID', node.profile_id || node.profile],
			],
		};
		if (node.is_operator === true) {
			const entrypoint = node.entrypoint || null;
			const features = Array.isArray(node.features) ? node.features : [];
			const outputLabel = node.is_effect ? 'Declared logical outputs' : 'Produces';
			const functionRows = [
				['Function', node.function_name || node.function_id || 'n/a'],
				['Function ID', node.function_id || 'n/a'],
				['Function kind', KINDS[node.function_kind]?.label || node.function_kind || 'n/a'],
			];
			if (entrypoint) functionRows.push(['Entrypoint', entrypoint]);
			ExplorerLineage.showDetails(nodeDetails, label, [
				{ title: 'Definition', icon: 'square-function', rows: [
					['Operator ID', node.operator_id || label], ...functionRows,
				] },
				profileSection,
				{ title: 'Outputs', icon: 'arrow-right-from-line', rows: [
					[outputLabel, features.length ? features.join(', ') : 'None'],
				] },
			],
				node.is_effect
					? 'Declared feature dependencies only; outputs are not materialized as dataframe columns.'
					: '', {
					kind: 'Operator', icon: KINDS[node.function_kind]?.icon || 'square-function',
				});
			return;
		}
		const dataType = node.data_type || node.type || 'unknown';
		ExplorerLineage.showDetails(nodeDetails, label, [
			{ title: 'Definition', icon: 'variable', rows: [
				['Feature ID', node.feature_id || node.id], ['Data type', dataType, dataType],
			] },
			profileSection,
		], '', { kind: 'Feature', icon: dataTypeIconName(dataType) || 'variable', color: node.datasetColor });
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
			graphData, node => nodeRanks.get(node.id), node => node.label || node.id,
			{ laneIcon: ICONS.profiles });
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
