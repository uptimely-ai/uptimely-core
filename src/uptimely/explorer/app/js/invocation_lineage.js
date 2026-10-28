{
	const STAGE_LAYOUT = Object.freeze({
		nodeGap: 24, laneWidth: 360, minLaneHeight: 160, laneVerticalPadding: 96,
		labelFontSize: 14, labelFontWeight: 600, labelFontFamily: '"DM Sans", sans-serif',
		evenBackground: 'rgba(143, 163, 181, .07)', oddBackground: 'rgba(143, 163, 181, .03)',
		borderColor: 'rgba(143, 163, 181, .4)', borderWidth: 1,
		labelColor: '#9fb3c3', labelTop: 28, fitPadding: 140,
	});
	const { LINK_STYLE, DIMMED_COLOR, MIN_RENDER_SCALE, STATIC_LAYOUT_COOLDOWN_TICKS } = ExplorerGraph;
	const invocationGraphData = ExplorerGraph.readPayload('graph-data');
	const style = ExplorerGraph.readPayload('graph-style');
	ExplorerGraph.prepareDatasetColors(invocationGraphData, document.getElementById('dataset-legend'));
	const invocationNodeDetails = document.getElementById('invocation-node-details');
	const formatList = (values) => Array.isArray(values) && values.length ? values.join(', ') : 'none';
	const formatArguments = (arguments_) => Object.entries(arguments_ || {})
		.map(([name, value]) => `${name}=${JSON.stringify(value)}`)
		.join(', ') || 'none';
	const updateInvocationDetails = (node) => {
		if (!node) {
			ExplorerGraph.showDetails(invocationNodeDetails, 'invocation details', [],
				'Select an invocation to inspect its function kind, arguments, entity, declared features, and invocation dependencies.');
			return;
		}
		const rows = [
			['Function kind', node.function_kind || 'n/a'],
			['Function', node.function_id || 'n/a'],
			['Arguments', formatArguments(node.arguments)],
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
	function create3D(invocationGraphContainer, invocationGraphData, updateInvocationDetails) {
		const highlight = ExplorerGraph.createDependencyHighlight(invocationGraphData);
		return ExplorerGraph.create3D(invocationGraphContainer, invocationGraphData, style, {
			label: node => `${node.function_id}\n${node.function_kind === 'escape' ? 'declares external outputs' : 'produces'}: ${node.feature}`,
			color: node => node.datasetColor,
			onSelect: updateInvocationDetails,
			highlight,
			configure: graph => graph.linkDirectionalArrowLength(style.arrow_length)
				.linkDirectionalArrowRelPos(style.arrow_rel_pos),
			object: node => ExplorerGraph.datasetNodeObject(node, node.function_id, style),
		});
	}
	function create2D(invocationGraphContainer, invocationGraphData, updateInvocationDetails) {
		const highlight = ExplorerGraph.createDependencyHighlight(invocationGraphData);
		const layers = new Map();
		for (const node of invocationGraphData.nodes) {
			const rank = node.stage - 1;
			if (!layers.has(rank)) layers.set(rank, []);
			layers.get(rank).push(node);
			ExplorerGraph.sizeCard(node, node.function_id);
		}
		for (const [rank, nodes] of layers) {
			const stackHeight = nodes.reduce((height, node) => height + node.cardHeight, 0)
				+ (nodes.length - 1) * STAGE_LAYOUT.nodeGap;
			let top = -stackHeight / 2;
			nodes.forEach(node => {
				node.fx = rank * STAGE_LAYOUT.laneWidth;
				node.fy = top + node.cardHeight / 2;
				node.x = node.fx;
				node.y = node.fy;
				top += node.cardHeight + STAGE_LAYOUT.nodeGap;
			});
		}
		const stageCount = layers.size;
		const laneHeight = Math.max(
			STAGE_LAYOUT.minLaneHeight,
			Math.max(0, ...[...layers.values()].map(nodes =>
				nodes.reduce((height, node) => height + node.cardHeight, 0)
					+ (nodes.length - 1) * STAGE_LAYOUT.nodeGap
			)) + STAGE_LAYOUT.laneVerticalPadding
		);
		const drawStageLanes = (ctx, globalScale) => {
			const scale = Math.max(globalScale, MIN_RENDER_SCALE);
			ctx.save();
			ctx.font = `${STAGE_LAYOUT.labelFontWeight} ${STAGE_LAYOUT.labelFontSize / scale}px ${STAGE_LAYOUT.labelFontFamily}`;
			ctx.textAlign = 'center';
			ctx.textBaseline = 'middle';
			for (let stage = 0; stage < stageCount; stage++) {
				const left = stage * STAGE_LAYOUT.laneWidth - STAGE_LAYOUT.laneWidth / 2;
				ctx.fillStyle = stage % 2 === 0
					? STAGE_LAYOUT.evenBackground
					: STAGE_LAYOUT.oddBackground;
				ctx.fillRect(left, -laneHeight / 2, STAGE_LAYOUT.laneWidth, laneHeight);
				ctx.strokeStyle = STAGE_LAYOUT.borderColor;
				ctx.lineWidth = STAGE_LAYOUT.borderWidth / scale;
				ctx.beginPath();
				ctx.moveTo(left, -laneHeight / 2);
				ctx.lineTo(left + STAGE_LAYOUT.laneWidth, -laneHeight / 2);
				ctx.moveTo(left, laneHeight / 2);
				ctx.lineTo(left + STAGE_LAYOUT.laneWidth, laneHeight / 2);
				ctx.stroke();
				ctx.fillStyle = STAGE_LAYOUT.labelColor;
				ctx.fillText(`Stage ${stage + 1}`, stage * STAGE_LAYOUT.laneWidth, -laneHeight / 2 + STAGE_LAYOUT.labelTop);
			}
			ctx.restore();
		};
		const selectInvocationAtPointer = event => ExplorerGraph.selectCard(
			invocationGraph, invocationGraphContainer, invocationGraphData.nodes, event, updateInvocationDetails);
		const invocationGraph = ForceGraph()(invocationGraphContainer)
			.width(invocationGraphContainer.clientWidth)
			.height(invocationGraphContainer.clientHeight)
			.backgroundColor(style.background_color)
			.nodeLabel(node => ExplorerGraph.tooltip(node.label))
			.onRenderFramePre(drawStageLanes)
			.nodeCanvasObjectMode(() => 'replace')
			.nodeCanvasObject((node, ctx) => ExplorerGraph.drawCard(
				node, ctx, node.function_id, invocationColors[node.function_kind], highlight))
			.nodePointerAreaPaint(ExplorerGraph.paintPointerArea)
			.linkColor(link => highlight.isLinkHighlighted(link)
				? LINK_STYLE.highlightColor
				: highlight.hasSelection() ? LINK_STYLE.dimmedColor : style.link_color)
			.linkWidth(link => highlight.isLinkHighlighted(link) ? LINK_STYLE.highlightWidth : style.link_width)
			.linkDirectionalParticles(LINK_STYLE.particleCount)
			.linkDirectionalParticleWidth(LINK_STYLE.particleWidth)
			.linkDirectionalParticleSpeed(LINK_STYLE.particleSpeed)
			.linkDirectionalParticleColor(link => highlight.isLinkHighlighted(link)
				? LINK_STYLE.highlightParticleColor
				: highlight.hasSelection() ? DIMMED_COLOR : style.link_color)
			.onNodeClick((_node, event) => selectInvocationAtPointer(event))
			.onLinkClick((_link, event) => selectInvocationAtPointer(event))
			.onBackgroundClick(event => selectInvocationAtPointer(event))
			.cooldownTicks(STATIC_LAYOUT_COOLDOWN_TICKS);
		const view = ExplorerGraph.createView(invocationGraph, invocationGraphContainer, STAGE_LAYOUT.fitPadding, '2d');
		view.selectNode = id => {
			highlight.select(invocationGraphData.nodes.find(node => node.id === id) || null);
		};
		invocationGraph.graphData(invocationGraphData);
		return view;
	}

	mountGraphViews(invocationGraphData, create2D, create3D, updateInvocationDetails, invocationNodeDetails);
}
