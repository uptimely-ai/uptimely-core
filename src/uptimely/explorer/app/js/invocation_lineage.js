{
	const STAGE_COLUMNS = Object.freeze({
		headerHeight: 48, background: 'rgba(143, 163, 181, .035)',
	});
	const { DATASET_LAYOUT, LINK_ROUTE, LINK_STYLE, STATIC_LAYOUT_COOLDOWN_TICKS } = ExplorerGraph;
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
			['Dataset', node.dataset_id],
			['Stage', node.stage],
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
		const layout = ExplorerGraph.prepareDatasetLayout(
			invocationGraphData, node => node.stage - 1, node => node.function_id);
		if (layout.columns.length) {
			layout.bounds.y -= STAGE_COLUMNS.headerHeight / 2;
			layout.bounds.height += STAGE_COLUMNS.headerHeight;
		}
		const drawStageColumns = (ctx, scale) => {
			const top = -layout.height / 2 - STAGE_COLUMNS.headerHeight;
			const bottom = layout.height / 2;
			const left = -layout.bounds.width / 2;
			const right = layout.bounds.width / 2;
			ctx.save();
			ctx.font = DATASET_LAYOUT.labelFont;
			ctx.textAlign = 'center';
			ctx.textBaseline = 'middle';
			ctx.lineWidth = 1 / Math.max(scale, ExplorerGraph.MIN_RENDER_SCALE);
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
		};
		const selectInvocationAtPointer = event => ExplorerGraph.selectCard(
			invocationGraph, invocationGraphContainer, invocationGraphData.nodes, event, updateInvocationDetails);
		const invocationGraph = ForceGraph()(invocationGraphContainer)
			.width(invocationGraphContainer.clientWidth)
			.height(invocationGraphContainer.clientHeight)
			.backgroundColor(style.background_color)
			.nodeLabel(node => ExplorerGraph.tooltip(`${node.label}\ndataset: ${node.dataset_id}\nstage: ${node.stage}`))
			.onRenderFramePre((ctx, scale) => {
				ExplorerGraph.drawDatasetLanes(layout, ctx, scale);
				drawStageColumns(ctx, scale);
			})
			.nodeCanvasObjectMode(() => 'replace')
			.nodeCanvasObject((node, ctx) => ExplorerGraph.drawCard(
				node, ctx, node.function_id, node.datasetColor, highlight))
			.nodePointerAreaPaint(ExplorerGraph.paintPointerArea)
			.linkColor(link => highlight.isLinkHighlighted(link)
				? LINK_STYLE.highlightColor
				: highlight.hasSelection() ? LINK_STYLE.dimmedColor : style.link_color)
			.linkWidth(link => highlight.isLinkHighlighted(link) ? LINK_STYLE.highlightWidth : style.link_width)
			.linkCanvasObjectMode(() => 'replace')
			.linkCanvasObject(ExplorerGraph.createDatasetLinkRenderer(invocationGraphData, style, highlight))
			.linkDirectionalParticles(LINK_ROUTE.particleCount)
			.linkDirectionalParticleWidth(LINK_ROUTE.particleWidth)
			.linkDirectionalParticleColor(() => LINK_ROUTE.invisibleParticleColor)
			.linkDirectionalArrowLength(0)
			.onNodeClick((_node, event) => selectInvocationAtPointer(event))
			.onLinkClick((_link, event) => selectInvocationAtPointer(event))
			.onBackgroundClick(event => selectInvocationAtPointer(event))
			.cooldownTicks(STATIC_LAYOUT_COOLDOWN_TICKS);
		const view = ExplorerGraph.createView(
			invocationGraph, invocationGraphContainer, DATASET_LAYOUT.fitPadding, '2d', layout.bounds);
		view.selectNode = id => {
			highlight.select(invocationGraphData.nodes.find(node => node.id === id) || null);
		};
		invocationGraph.graphData(invocationGraphData);
		return view;
	}

	mountGraphViews(invocationGraphData, create2D, create3D, updateInvocationDetails, invocationNodeDetails);
}
