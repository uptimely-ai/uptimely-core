{
	const callableGraphData = JSON.parse(document.getElementById('graph-data').textContent);
	const style = JSON.parse(document.getElementById('graph-style').textContent);
	const callableNodeDetails = document.getElementById('callable-node-details');
	const formatList = (values) => Array.isArray(values) && values.length ? values.join(', ') : 'none';
	const updateCallableDetails = (node) => {
		if (!node) {
			callableNodeDetails.innerHTML = `
				<h3 class="mb-2 font-mono text-xs uppercase tracking-wider text-slate-400">Callable details</h3>
				<div class="text-sm leading-6 text-slate-300">Select a callable to inspect its operation, entity, declared features, and callable dependencies.</div>
			`;
			return;
		}
		callableNodeDetails.innerHTML = `
			<h3 class="mb-2 font-mono text-xs uppercase tracking-wider text-slate-400">Callable details</h3>
			<div class="mb-1 break-all text-xs text-slate-300"><strong>Operation:</strong> ${node.operation || 'n/a'}</div>
			<div class="mb-1 break-all text-xs text-slate-300"><strong>Function:</strong> ${node.function_id || 'n/a'}</div>
			<div class="mb-1 break-all text-xs text-slate-300"><strong>Entity:</strong> ${node.entity || 'n/a'}</div>
			<div class="mb-1 break-all text-xs text-slate-300"><strong>${node.operation === 'escape' ? 'Declares external outputs' : 'Produces'}:</strong> ${node.feature || 'n/a'}</div>
			${node.operation === 'escape' ? '<div class="mb-1 text-xs text-violet-200">Not verified or materialized as dataframe columns.</div>' : ''}
			${node.operation === 'escape' && node.input_features?.length ? `<div class="mb-1 break-all text-xs text-slate-300"><strong>Declared inputs:</strong> ${formatList(node.input_features)}</div>` : ''}
			<div class="break-all text-xs text-slate-300"><strong>Callable dependencies:</strong> ${formatList(node.dependency_ids)}</div>
		`;
	};
	const callableColors = style.function_colors;
	function create3D(callableGraphContainer, callableGraphData, updateCallableDetails) {
		let initialFitComplete = false;
		const callableGraph = ForceGraph3D()(callableGraphContainer)
			.width(callableGraphContainer.clientWidth)
			.height(callableGraphContainer.clientHeight)
			.graphData(callableGraphData)
			.backgroundColor(style.background_color)
			.nodeLabel(node => `${node.function_id}<br>produces: ${node.feature}`)
			.nodeColor(node => callableColors[node.operation])
			.nodeRelSize(style.node_rel_size)
			.nodeResolution(style.node_resolution)
			.linkWidth(style.link_width)
			.linkColor(() => style.link_color)
			.linkOpacity(style.link_opacity)
			.linkDirectionalParticles(2)
			.linkDirectionalParticleWidth(2)
			.linkDirectionalParticleSpeed(0.003)
			.onNodeClick(node => updateCallableDetails(node))
			.onEngineStop(() => {
				if (!initialFitComplete) {
					callableGraph.zoomToFit(0, 60);
					initialFitComplete = true;
				}
			})
			.nodeThreeObject(node => {
				const material = new THREE.MeshLambertMaterial({ color: callableColors[node.operation] });
				const mesh = new THREE.Mesh(
					new THREE.OctahedronGeometry(style.function_node_size, 0),
					material,
				);
				const group = new THREE.Group();
				group.add(mesh);
				const label = new SpriteText(node.function_id || '', 3.2, style.label_color);
				label.backgroundColor = 'rgba(16,24,32,0.72)';
				label.padding = 2;
				label.borderRadius = 2;
				label.position.set(0, 18, 0);
				group.add(label);
				return group;
			});
		callableGraph.d3Force('charge').strength(style.charge_strength).distanceMax(style.charge_distance_max);
		callableGraph.d3Force('link').distance(style.link_distance);
		const fit = () => callableGraph.zoomToFit(0, 60);
		const resize = () => {
			callableGraph.width(callableGraphContainer.clientWidth)
				.height(callableGraphContainer.clientHeight);
			fit();
	};
	return { graph: callableGraph, fit, resize };
	}
	function create2D(callableGraphContainer, callableGraphData, updateCallableDetails) {
		const layers = new Map();
		for (const node of callableGraphData.nodes) {
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
		const selectCallableAtPointer = (event) => {
			const bounds = callableGraphContainer.getBoundingClientRect();
			const point = callableGraph.screen2GraphCoords(
				event.clientX - bounds.left, event.clientY - bounds.top);
			const node = [...callableGraphData.nodes].reverse().find(node =>
				Math.abs(point.x - node.x) <= node.cardWidth / 2 &&
				Math.abs(point.y - node.y) <= node.cardHeight / 2);
			if (node) updateCallableDetails(node);
		};
		let initialFitComplete = false;
		const callableGraph = ForceGraph()(callableGraphContainer)
			.width(callableGraphContainer.clientWidth)
			.height(callableGraphContainer.clientHeight)
			.backgroundColor(style.background_color)
			.nodeLabel(node => node.label)
			.onRenderFramePre(drawStageLanes)
			.nodeCanvasObjectMode(() => 'replace')
			.nodeCanvasObject((node, ctx) => {
				const left = node.x - node.cardWidth / 2;
				const top = node.y - node.cardHeight / 2;
				ctx.save();
				ctx.beginPath();
				ctx.roundRect(left, top, node.cardWidth, node.cardHeight, 10);
				ctx.fillStyle = '#172a35';
				ctx.fill();
				ctx.strokeStyle = callableColors[node.operation];
				ctx.lineWidth = 1.5;
				ctx.stroke();
				ctx.fillStyle = style.label_color;
				ctx.textBaseline = 'top';
				node.label_lines.forEach((line, index) => {
					ctx.font = index === 0
						? '600 12px "DM Sans", sans-serif'
						: '11px "DM Sans", sans-serif';
					ctx.fillText(line, left + 14, top + 10 + index * 18, node.cardWidth - 28);
				});
				ctx.restore();
			})
			.nodePointerAreaPaint((node, color, ctx) => {
				ctx.fillStyle = color;
				ctx.fillRect(node.x - node.cardWidth / 2, node.y - node.cardHeight / 2,
					node.cardWidth, node.cardHeight);
			})
			.linkColor(() => style.link_color)
			.linkWidth(style.link_width)
			.linkDirectionalParticles(2)
			.linkDirectionalParticleWidth(2)
			.linkDirectionalParticleSpeed(0.003)
			.onNodeClick((_node, event) => selectCallableAtPointer(event))
			.onLinkClick((_link, event) => selectCallableAtPointer(event))
			.onBackgroundClick(event => selectCallableAtPointer(event))
			.cooldownTicks(1)
			.onEngineStop(() => {
				if (!initialFitComplete) {
					callableGraph.zoomToFit(0, 140);
					initialFitComplete = true;
				}
			})
			.graphData(callableGraphData);
		const fitCallableGraph = () => callableGraph.zoomToFit(500, 140);
		const resize = () => {
			callableGraph.width(callableGraphContainer.clientWidth)
				.height(callableGraphContainer.clientHeight);
			fitCallableGraph();
		};
		return { graph: callableGraph, fit: fitCallableGraph, resize };
	}

	mountGraphViews(callableGraphData, create2D, create3D, updateCallableDetails, callableNodeDetails);
}
