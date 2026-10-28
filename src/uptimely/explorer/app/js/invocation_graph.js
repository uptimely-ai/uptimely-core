{
	const invocationGraphData = ExplorerGraph.readPayload('graph-data');
	const style = ExplorerGraph.readPayload('graph-style');
	ExplorerGraph.prepareEntityColors(invocationGraphData, document.getElementById('entity-legend'));
	const invocationNodeDetails = document.getElementById('invocation-node-details');
	const formatList = (values) => Array.isArray(values) && values.length ? values.join(', ') : 'none';
	const updateinvocationDetails = (node) => {
		if (!node) {
			ExplorerGraph.showDetails(invocationNodeDetails, 'invocation details', [],
				'Select an invocation to inspect its function kind, entity, declared features, and invocation dependencies.');
			return;
		}
		const rows = [
			['Function kind', node.function_kind || 'n/a'],
			['Function', node.function_id || 'n/a'],
			['Entity', node.entity || 'n/a'],
			[node.function_kind === 'escape' ? 'Declares external outputs' : 'Produces', node.feature || 'n/a'],
		];
		if (node.function_kind === 'escape' && node.input_features?.length) {
			rows.push(['Declared inputs', formatList(node.input_features)]);
		}
		rows.push(['invocation dependencies', formatList(node.dependency_ids)]);
		ExplorerGraph.showDetails(invocationNodeDetails, 'invocation details', rows,
			node.function_kind === 'escape' ? 'Not verified or materialized as dataframe columns.' : '');
	};
	const invocationColors = style.function_colors;
	function create3D(invocationGraphContainer, invocationGraphData, updateinvocationDetails) {
		const highlight = ExplorerGraph.createDependencyHighlight(invocationGraphData);
		return ExplorerGraph.create3D(invocationGraphContainer, invocationGraphData, style, {
			label: node => `${node.function_id}\n${node.function_kind === 'escape' ? 'declares external outputs' : 'produces'}: ${node.feature}`,
			color: node => node.entityColor,
			onSelect: updateinvocationDetails,
			highlight,
			configure: graph => graph.linkDirectionalArrowLength(style.arrow_length)
				.linkDirectionalArrowRelPos(style.arrow_rel_pos),
			object: node => ExplorerGraph.entityNodeObject(node, node.function_id, style),
		});
	}
	function create2D(invocationGraphContainer, invocationGraphData, updateinvocationDetails) {
		const highlight = ExplorerGraph.createDependencyHighlight(invocationGraphData);
		const layers = new Map();
		for (const node of invocationGraphData.nodes) {
			const rank = node.stage - 1;
			if (!layers.has(rank)) layers.set(rank, []);
			layers.get(rank).push(node);
			node.cardWidth = Math.min(
				320,
				Math.max(180, Math.max(...node.label_lines.map(line => line.length)) * 7 + 28)
			);
			node.cardHeight = Math.max(44, node.label_lines.length * 18 + 20);
		}
		for (const [rank, nodes] of layers) {
			const stackHeight = nodes.reduce((height, node) => height + node.cardHeight, 0)
				+ (nodes.length - 1) * 24;
			let top = -stackHeight / 2;
			nodes.forEach(node => {
				node.fx = rank * 360;
				node.fy = top + node.cardHeight / 2;
				node.x = node.fx;
				node.y = node.fy;
				top += node.cardHeight + 24;
			});
		}
		const stageCount = layers.size;
		const laneHeight = Math.max(
			160,
			Math.max(0, ...[...layers.values()].map(nodes =>
				nodes.reduce((height, node) => height + node.cardHeight, 0)
					+ (nodes.length - 1) * 24
			)) + 96
		);
		const drawStageLanes = (ctx, globalScale) => {
			const scale = Math.max(globalScale, 0.01);
			ctx.save();
			ctx.font = `600 ${14 / scale}px "DM Sans", sans-serif`;
			ctx.textAlign = 'center';
			ctx.textBaseline = 'middle';
			for (let stage = 0; stage < stageCount; stage++) {
				const left = stage * 360 - 180;
				ctx.fillStyle = stage % 2 === 0
					? 'rgba(143, 163, 181, .07)'
					: 'rgba(143, 163, 181, .03)';
				ctx.fillRect(left, -laneHeight / 2, 360, laneHeight);
				ctx.strokeStyle = 'rgba(143, 163, 181, .4)';
				ctx.lineWidth = 1 / scale;
				ctx.beginPath();
				ctx.moveTo(left, -laneHeight / 2);
				ctx.lineTo(left + 360, -laneHeight / 2);
				ctx.moveTo(left, laneHeight / 2);
				ctx.lineTo(left + 360, laneHeight / 2);
				ctx.stroke();
				ctx.fillStyle = '#9fb3c3';
				ctx.fillText(`Stage ${stage + 1}`, stage * 360, -laneHeight / 2 + 28);
			}
			ctx.restore();
		};
		const selectinvocationAtPointer = event => ExplorerGraph.selectCard(
			invocationGraph, invocationGraphContainer, invocationGraphData.nodes, event, updateinvocationDetails);
		const invocationGraph = ForceGraph()(invocationGraphContainer)
			.width(invocationGraphContainer.clientWidth)
			.height(invocationGraphContainer.clientHeight)
			.backgroundColor(style.background_color)
			.nodeLabel(node => ExplorerGraph.tooltip(node.label))
			.onRenderFramePre(drawStageLanes)
			.nodeCanvasObjectMode(() => 'replace')
			.nodeCanvasObject((node, ctx) => {
				const left = node.x - node.cardWidth / 2;
				const top = node.y - node.cardHeight / 2;
				ctx.save();
				ctx.beginPath();
				ctx.roundRect(left, top, node.cardWidth, node.cardHeight, 10);
				ctx.fillStyle = highlight.hasSelection() && !highlight.isNodeHighlighted(node)
					? '#121c24'
					: '#172a35';
				ctx.fill();
				ctx.strokeStyle = highlight.hasSelection()
					? highlight.isSelected(node) ? '#f8d66d'
						: highlight.isNodeHighlighted(node) ? '#67e8f9' : '#46545f'
					: invocationColors[node.function_kind];
				ctx.lineWidth = highlight.isSelected(node) ? 3 : 1.5;
				ctx.stroke();
				ctx.fillStyle = highlight.hasSelection() && !highlight.isNodeHighlighted(node)
					? 'rgba(232, 237, 242, .3)'
					: style.label_color;
				ctx.textBaseline = 'top';
				node.label_lines.forEach((line, index) => {
					ctx.font = index === 0
						? '600 12px "DM Sans", sans-serif'
						: '11px "DM Sans", sans-serif';
					ctx.fillText(line, left + 14, top + 10 + index * 18, node.cardWidth - 28);
				});
				ctx.restore();
			})
			.nodePointerAreaPaint(ExplorerGraph.paintPointerArea)
			.linkColor(link => highlight.isLinkHighlighted(link)
				? '#67e8f9'
				: highlight.hasSelection() ? 'rgba(70, 84, 95, .35)' : style.link_color)
			.linkWidth(link => highlight.isLinkHighlighted(link) ? 3 : style.link_width)
			.linkDirectionalParticles(2)
			.linkDirectionalParticleWidth(2)
			.linkDirectionalParticleSpeed(0.003)
			.linkDirectionalParticleColor(link => highlight.isLinkHighlighted(link)
				? '#f8d66d'
				: highlight.hasSelection() ? '#46545f' : style.link_color)
			.onNodeClick((_node, event) => selectinvocationAtPointer(event))
			.onLinkClick((_link, event) => selectinvocationAtPointer(event))
			.onBackgroundClick(event => selectinvocationAtPointer(event))
			.cooldownTicks(1);
		const view = ExplorerGraph.createView(invocationGraph, invocationGraphContainer, 140, '2d');
		view.selectNode = id => {
			highlight.select(invocationGraphData.nodes.find(node => node.id === id) || null);
		};
		invocationGraph.graphData(invocationGraphData);
		return view;
	}

	mountGraphViews(invocationGraphData, create2D, create3D, updateinvocationDetails, invocationNodeDetails);
}
