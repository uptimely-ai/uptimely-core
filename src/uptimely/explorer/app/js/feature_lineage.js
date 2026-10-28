{
	const DETAIL_VALUE_MAX_LENGTH = 220;
	const FORCE_GRAPH_2D = Object.freeze({
		nodeRelativeSize: 6, functionValue: 7, featureValue: 5,
	});
	const { DATASET_LAYOUT, LINK_ROUTE, LINK_STYLE, STATIC_LAYOUT_COOLDOWN_TICKS } = ExplorerGraph;
	const data = ExplorerGraph.readPayload('graph-data');
	const style = ExplorerGraph.readPayload('graph-style');
	const functionColor = style.function_color;
	ExplorerGraph.prepareDatasetColors(data, document.getElementById('dataset-legend'));
	const nodeDetails = document.getElementById('node-details');
	const formatDetailValue = (value) => value == null ? 'n/a' : String(value).slice(0, DETAIL_VALUE_MAX_LENGTH);
	const updateDetails = (node) => {
		if (!node) {
			ExplorerGraph.showDetails(nodeDetails, 'Selected item', [],
				'Select any feature in the graph to see its identifier and details.');
			return;
		}
		const label = node.label || node.id || 'Unknown';
		const isAction = node.is_action === true;
		if (isAction) {
			const entrypoint = node.entrypoint || null;
			const features = Array.isArray(node.features) ? node.features : [];
			const outputLabel = node.function_kind === 'escape'
				? 'Declares external outputs'
				: 'Produces';
			const rows = [
				['Node type', 'Action'],
				['Dataset', node.dataset_id],
				['Action', node.action_id || label],
				['Function', node.function_id || 'n/a'],
				['Function kind', node.function_kind || 'n/a'],
			];
			if (features.length) rows.push([outputLabel, formatDetailValue(features.join(', '))]);
			if (entrypoint) rows.push(['Entrypoint', formatDetailValue(entrypoint)]);
			ExplorerGraph.showDetails(nodeDetails, 'Selected item', rows);
			return;
		}
		const dataType = node.data_type || node.type || 'unknown';
		const entity = node.entity || 'n/a';
		ExplorerGraph.showDetails(nodeDetails, 'Selected item', [
			['Node type', 'Feature'], ['Feature', label], ['Dataset', node.dataset_id],
			['Entity', formatDetailValue(entity)], ['Data type', formatDetailValue(dataType)],
		]);
	};

	function create2D(graphContainer, data, updateDetails) {
		const highlight = ExplorerGraph.createDependencyHighlight(data);
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

		const nodeRanks = rankNodes(data);
		const layout = ExplorerGraph.prepareDatasetLayout(
			data, node => nodeRanks.get(node.id), node => node.label || node.id);
		const selectAtPointer = event =>
			ExplorerGraph.selectCard(graph, graphContainer, data.nodes, event, updateDetails);

		function drawNode(node, ctx) {
			const isAction = node.is_action === true;
			const baseColor = isAction ? functionColor : node.datasetColor;
			ExplorerGraph.drawCard(node, ctx, node.label || node.id, baseColor, highlight, !isAction);
		}

		const graph = ForceGraph()(graphContainer)
			.width(graphContainer.clientWidth)
			.height(graphContainer.clientHeight)
			.backgroundColor(style.background_color)
			.onRenderFramePre((ctx, scale) => ExplorerGraph.drawDatasetLanes(layout, ctx, scale))
			.nodeLabel(node => ExplorerGraph.tooltip(`${node.is_action ? 'action' : 'feature'}: ${node.label}\nentity: ${node.entity || 'n/a'}`))
			.nodeRelSize(FORCE_GRAPH_2D.nodeRelativeSize)
			.nodeVal(node => node.is_action ? FORCE_GRAPH_2D.functionValue : FORCE_GRAPH_2D.featureValue)
			.nodeColor(node => node.is_action ? functionColor : node.datasetColor)
			.nodeCanvasObjectMode(() => 'replace')
			.nodeCanvasObject(drawNode)
			.nodePointerAreaPaint(ExplorerGraph.paintPointerArea)
			.linkColor(link => highlight.isLinkHighlighted(link)
				? LINK_STYLE.highlightColor
				: highlight.hasSelection() ? LINK_STYLE.dimmedColor : style.link_color)
			.linkWidth(link => highlight.isLinkHighlighted(link) ? LINK_STYLE.highlightWidth : style.link_width)
			.linkCanvasObjectMode(() => 'replace')
			.linkCanvasObject(ExplorerGraph.createDatasetLinkRenderer(data, style, highlight))
			.linkDirectionalParticles(LINK_ROUTE.particleCount)
			.linkDirectionalParticleWidth(LINK_ROUTE.particleWidth)
			.linkDirectionalParticleColor(() => LINK_ROUTE.invisibleParticleColor)
			.linkDirectionalArrowLength(0)
			.onNodeClick((_node, event) => selectAtPointer(event))
			.onLinkClick((_link, event) => selectAtPointer(event))
			.onBackgroundClick(event => selectAtPointer(event))
			.cooldownTicks(STATIC_LAYOUT_COOLDOWN_TICKS);
		const view = ExplorerGraph.createView(graph, graphContainer, DATASET_LAYOUT.fitPadding, '2d', layout.bounds);
		view.selectNode = id => {
			highlight.select(data.nodes.find(node => node.id === id) || null);
		};
		graph.graphData(data);
		return view;
	}

	function create3D(graphContainer, data, updateDetails) {
		const highlight = ExplorerGraph.createDependencyHighlight(data);
		return ExplorerGraph.create3D(graphContainer, data, style, {
			label: node => `${node.is_action ? 'function' : 'feature'}: ${node.label}\nentity: ${node.entity || 'n/a'}`,
			color: node => node.is_action ? functionColor : node.datasetColor,
			onSelect: updateDetails,
			highlight,
			configure: graph => graph.linkDirectionalArrowLength(style.arrow_length)
				.linkDirectionalArrowRelPos(style.arrow_rel_pos),
			object: node => {
				if (!node.is_action) {
					return ExplorerGraph.datasetNodeObject(node, node.label, style);
				}
				const mesh = new THREE.Mesh(
					new THREE.OctahedronGeometry(style.function_node_size, 0),
					new THREE.MeshLambertMaterial({ color: functionColor }),
				);
				return ExplorerGraph.labeledMesh(mesh, node.label, style, 14);
			},
		});
	}

	mountGraphViews(data, create2D, create3D, updateDetails, document.getElementById('node-details'));
}
