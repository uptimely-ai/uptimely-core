import * as LineageConfig from './lineage_config.js';
import * as LineageLayout from './lineage_layout.js';
import { dataTypeIconName } from '../rendering/shared_markup.js';

function readPayload(id) {
	return JSON.parse(document.getElementById(id).textContent);
}

function tooltip(text) {
	const element = document.createElement('div');
	element.className = 'lineage-tooltip';
	element.textContent = text;
	return element;
}

function detailIcon(name) {
	const icon = document.createElement('i');
	icon.setAttribute('data-lucide', name);
	icon.setAttribute('aria-hidden', 'true');
	return icon;
}

function showDetails(panel, title, sections, summary = '', {
	kind = '', icon = 'mouse-pointer-2', color = null,
} = {}) {
	const header = document.createElement('header');
	header.className = sections.length ? 'lineage-details-header' : 'lineage-details-empty';
	const identity = document.createElement('div');
	const label = document.createElement('p');
	label.className = 'lineage-details-kind';
	label.textContent = kind || 'Selection';
	const heading = document.createElement('h2');
	heading.textContent = title;
	identity.append(label, heading);
	header.append(detailIcon(icon), identity);
	if (color) header.style.setProperty('--node-color', color);
	panel.replaceChildren(header);
	for (const { title: sectionTitle, icon: sectionIcon, rows } of sections) {
		if (!rows.length) continue;
		const section = document.createElement('section');
		section.className = 'lineage-details-section';
		section.setAttribute('aria-label', sectionTitle);
		const sectionHeading = document.createElement('h3');
		const sectionLabel = document.createElement('span');
		sectionLabel.textContent = sectionTitle;
		sectionHeading.append(detailIcon(sectionIcon), sectionLabel);
		const list = document.createElement('dl');
		for (const [label, value, type, href] of rows) {
			const row = document.createElement('div');
			const name = document.createElement('dt');
			name.textContent = label;
			const description = document.createElement('dd');
			const text = document.createElement(href ? 'a' : 'span');
			text.textContent = value == null ? 'n/a' : String(value);
			if (href) text.href = href;
			const iconName = dataTypeIconName(type);
			if (iconName) {
				description.className = 'data-type-label';
				text.className = 'data-type-label-text';
				const typeIcon = detailIcon(iconName);
				typeIcon.className = 'data-type-label-icon';
				typeIcon.setAttribute('data-type', type);
				description.append(typeIcon);
			}
			description.append(text);
			row.append(name, description);
			list.append(row);
		}
		section.append(sectionHeading, list);
		panel.append(section);
	}
	if (summary) {
		const note = document.createElement('div');
		note.className = sections.length ? 'lineage-details-note' : 'lineage-details-hint';
		const text = document.createElement('p');
		text.textContent = summary;
		if (sections.length) note.append(detailIcon('info'));
		note.append(text);
		panel.append(note);
	}
	lucide.createIcons({ root: panel });
}

function appendLegend(container, entries) {
	for (const { label, color } of entries) {
		const item = document.createElement('span');
		item.className = 'lineage-profile-key';
		item.style.setProperty('--color', color);
		item.textContent = label;
		container.append(item);
	}
}

function prepareDatasetColors(data, container, style = {}) {
	const datasets = new Map(data.nodes
		.filter(node => !node.is_operator)
		.map(node => [
			node.profile_id || LineageConfig.UNASSIGNED_DATASET,
			node.profile_name || node.profile_id || LineageConfig.UNASSIGNED_DATASET,
		]));
	const datasetIds = [...datasets.keys()].sort((a, b) =>
		datasets.get(a).localeCompare(datasets.get(b)));
	const colors = new Map(datasetIds.map(
		(dataset, index) => [dataset, LineageConfig.DATASET_PALETTE[index % LineageConfig.DATASET_PALETTE.length]]
	));
	appendLegend(container, datasetIds.map(dataset => ({
		label: datasets.get(dataset), color: colors.get(dataset),
	})));
	const mergeColor = style.function_colors?.merge || style.function_color;
	for (const node of data.nodes) {
		node.profile_id = node.profile_id || LineageConfig.UNASSIGNED_DATASET;
		node.datasetColor = colors.get(node.profile_id);
		node.mergeColor = mergeColor;
	}
}

function datasetNodeObject(node, text, style) {
	const mesh = new THREE.Mesh(
		new THREE.SphereGeometry(style.feature_node_size,
			LineageConfig.NODE_STYLE_3D.sphereWidthSegments,
			LineageConfig.NODE_STYLE_3D.sphereHeightSegments),
		new THREE.MeshLambertMaterial({
			color: node.phase === 'merge' ? node.mergeColor : node.datasetColor,
		}),
	);
	return labeledMesh(mesh, text, style, LineageConfig.NODE_STYLE_3D.labelOffset,
		node.data_type || node.type || 'unknown');
}

const iconPaths = new Map();

function drawDataTypeIcon(ctx, type, x, y, size, color) {
	drawIcon(ctx, dataTypeIconName(type) || 'braces', x, y, size, color);
}

function drawIcon(ctx, name, x, y, size, color) {
	if (!iconPaths.has(name)) {
		const key = name.replace(/(^|-)(\w)/g, (_match, _separator, letter) => letter.toUpperCase());
		const paths = lucide.icons[key].map(([tag, attributes]) => {
			const path = new Path2D(tag === 'path' ? attributes.d : undefined);
			const number = key => Number(attributes[key] || 0);
			if (tag === 'circle') {
				path.arc(number('cx'), number('cy'), number('r'), 0, Math.PI * 2);
			} else if (tag === 'ellipse') {
				path.ellipse(number('cx'), number('cy'), number('rx'), number('ry'), 0, 0, Math.PI * 2);
			} else if (tag === 'rect') {
				path.roundRect(number('x'), number('y'), number('width'), number('height'), number('rx'));
			} else if (tag === 'line') {
				path.moveTo(number('x1'), number('y1'));
				path.lineTo(number('x2'), number('y2'));
			} else if (tag !== 'path') {
				throw new Error(`Unsupported lineage icon shape: ${tag}`);
			}
			return path;
		});
		iconPaths.set(name, paths);
	}
	ctx.save();
	ctx.translate(x, y);
	ctx.scale(size / 24, size / 24);
	ctx.strokeStyle = color;
	ctx.lineWidth = 2;
	ctx.lineCap = 'round';
	ctx.lineJoin = 'round';
	for (const path of iconPaths.get(name)) ctx.stroke(path);
	ctx.restore();
}

function drawCard(node, ctx, label, color, highlight, isFeature = false, {
	subtitle = '', iconName = null, badgeIconName = null,
} = {}) {
	const { CARD_STYLE, DIMMED_COLOR } = LineageConfig;
	const dimmed = highlight.hasSelection() && !highlight.isNodeHighlighted(node);
	const left = node.x - node.cardWidth / 2;
	ctx.save();
	ctx.shadowColor = CARD_STYLE.shadowColor;
	ctx.shadowBlur = CARD_STYLE.shadowBlur;
	ctx.shadowOffsetY = CARD_STYLE.shadowOffsetY;
	ctx.beginPath();
	ctx.roundRect(left, node.y - node.cardHeight / 2,
		node.cardWidth, node.cardHeight, CARD_STYLE.cornerRadius);
	ctx.fillStyle = dimmed ? CARD_STYLE.dimmedBackground
		: isFeature ? CARD_STYLE.featureBackground : CARD_STYLE.background;
	ctx.fill();
	ctx.shadowColor = 'transparent';
	const selected = highlight.isSelected(node);
	ctx.lineWidth = selected ? CARD_STYLE.selectedBorderWidth : CARD_STYLE.borderWidth;
	ctx.strokeStyle = selected ? CARD_STYLE.selectedBorderColor : dimmed ? DIMMED_COLOR : color;
	ctx.stroke();
	if (isFeature) {
		drawDataTypeIcon(ctx, node.data_type || node.type,
			left + CARD_STYLE.iconLeft, node.y - CARD_STYLE.featureIconSize / 2,
			CARD_STYLE.featureIconSize, dimmed ? CARD_STYLE.dimmedTextColor : CARD_STYLE.textColor);
	} else if (iconName) {
		drawIcon(ctx, iconName, left + CARD_STYLE.iconLeft,
			node.y - CARD_STYLE.featureIconSize / 2, CARD_STYLE.featureIconSize,
			dimmed ? CARD_STYLE.dimmedTextColor : CARD_STYLE.textColor);
	} else {
		ctx.beginPath();
		ctx.roundRect(left + CARD_STYLE.iconLeft, node.y - CARD_STYLE.iconSize / 2,
			CARD_STYLE.iconSize, CARD_STYLE.iconSize, CARD_STYLE.iconRadius);
		ctx.fillStyle = dimmed ? DIMMED_COLOR : color;
		ctx.fill();
	}
	ctx.fillStyle = dimmed ? CARD_STYLE.dimmedTextColor : CARD_STYLE.textColor;
	ctx.font = CARD_STYLE.font;
	ctx.textAlign = 'left';
	ctx.textBaseline = 'middle';
	const textWidth = node.cardWidth - CARD_STYLE.labelHorizontalPadding
		- (badgeIconName ? CARD_STYLE.featureIconSize + CARD_STYLE.iconLeft : 0);
	ctx.fillText(label, left + CARD_STYLE.labelLeft, node.y - (subtitle ? CARD_STYLE.titleOffset : 0),
		textWidth);
	if (subtitle) {
		ctx.font = CARD_STYLE.subtitleFont;
		ctx.fillStyle = dimmed ? CARD_STYLE.dimmedTextColor : LineageConfig.DATASET_LAYOUT.labelColor;
		ctx.fillText(subtitle, left + CARD_STYLE.labelLeft, node.y + CARD_STYLE.subtitleOffset,
			textWidth);
	}
	if (badgeIconName) {
		drawIcon(ctx, badgeIconName,
			left + node.cardWidth - CARD_STYLE.iconLeft - CARD_STYLE.featureIconSize,
			node.y - CARD_STYLE.featureIconSize / 2, CARD_STYLE.featureIconSize,
			dimmed ? CARD_STYLE.dimmedTextColor : LineageConfig.DATASET_LAYOUT.labelColor);
	}
	ctx.restore();
}

function paintPointerArea(node, color, ctx) {
	ctx.fillStyle = color;
	ctx.fillRect(node.x - node.cardWidth / 2, node.y - node.cardHeight / 2,
		node.cardWidth, node.cardHeight);
}

function selectCard(forceGraph, container, nodes, event, onSelect) {
	const bounds = container.getBoundingClientRect();
	const point = forceGraph.screen2GraphCoords(
		event.clientX - bounds.left, event.clientY - bounds.top);
	const node = [...nodes].reverse().find(node =>
		Math.abs(point.x - node.x) <= node.cardWidth / 2 &&
		Math.abs(point.y - node.y) <= node.cardHeight / 2);
	if (node) onSelect(node);
}

function createLineageHighlight(data, fullLineage = true) {
	const endpointId = endpoint => typeof endpoint === 'object' ? endpoint.id : endpoint;
	const incoming = new Map(data.nodes.map(node => [node.id, []]));
	const outgoing = new Map(data.nodes.map(node => [node.id, []]));
	for (const link of data.links) {
		incoming.get(endpointId(link.target))?.push(link);
		outgoing.get(endpointId(link.source))?.push(link);
	}
	let selectedId = null;
	let highlightedNodes = new Set();
	let highlightedLinks = new Set();
	const highlight = {
		select(node) {
			selectedId = node?.id ?? null;
			highlightedNodes = new Set();
			highlightedLinks = new Set();
			if (!selectedId) return;
			highlightedNodes.add(selectedId);
			for (const links of [incoming, outgoing]) {
				const visited = new Set([selectedId]);
				const pending = [selectedId];
				while (pending.length) {
					const current = pending.pop();
					for (const link of links.get(current) || []) {
						highlightedLinks.add(link);
						const next = links === incoming
							? endpointId(link.source)
							: endpointId(link.target);
						highlightedNodes.add(next);
						if (fullLineage && !visited.has(next)) {
							visited.add(next);
							pending.push(next);
						}
					}
				}
			}
		},
		hasSelection: () => selectedId !== null,
		isSelected: node => node.id === selectedId,
		isNodeHighlighted: node => highlightedNodes.has(node.id),
		isLinkHighlighted: link => highlightedLinks.has(link),
		isLinkDirect: link => selectedId !== null
			&& (endpointId(link.source) === selectedId || endpointId(link.target) === selectedId),
		setFullLineage(value) {
			fullLineage = value;
			highlight.select(data.nodes.find(node => node.id === selectedId) || null);
		},
	};
	return highlight;
}

function createLineageView(forceGraph, container, padding, dimension, bounds = null) {
	const fitGraph = duration => {
		if (dimension === '2d' && bounds) {
			forceGraph.centerAt(bounds.x, bounds.y, duration);
			forceGraph.zoom(Math.min(
				Math.max(1, container.clientWidth - 2 * padding) / bounds.width,
				Math.max(1, container.clientHeight - 2 * padding) / bounds.height,
			), duration);
			return;
		}
		forceGraph.zoomToFit(duration, padding);
	};
	let initialFitComplete = false;
	forceGraph.onEngineStop(() => {
		if (!initialFitComplete) {
			fitGraph(LineageConfig.VIEW_TIMING.initialFit);
			initialFitComplete = true;
		}
	});
	const fit = () => fitGraph(LineageConfig.VIEW_TIMING.fit);
	const resize = (fitToView = true) => {
		forceGraph.width(container.clientWidth).height(container.clientHeight);
		if (fitToView) fit();
	};
	const zoom = factor => {
		if (dimension === '2d') {
			forceGraph.zoom(forceGraph.zoom() * factor, LineageConfig.VIEW_TIMING.zoom);
			return;
		}
		const position = forceGraph.cameraPosition();
		const target = forceGraph.controls().target;
		forceGraph.cameraPosition({
			x: target.x + (position.x - target.x) / factor,
			y: target.y + (position.y - target.y) / factor,
			z: target.z + (position.z - target.z) / factor,
		}, target, LineageConfig.VIEW_TIMING.zoom);
	};
	return { forceGraph, fit, resize, zoom };
}

function createLineage2D(container, graphData, style, layout, highlight, {
	label,
	color,
	drawNode,
	onSelect,
	nodeValue,
	nodeRelativeSize,
	renderOverlay,
}) {
	let forceGraph;
	if (graphData.links.some(link => !link.routePoints)) LineageLayout.prepareLineageRoutes(graphData);
	const renderLink = LineageLayout.createLineageLinkRenderer(graphData, style, highlight);
	const selectAtPointer = event => selectCard(
		forceGraph, container, graphData.nodes, event, onSelect);
	forceGraph = ForceGraph()(container)
		.width(container.clientWidth)
		.height(container.clientHeight)
		.backgroundColor(style.background_color)
		.onRenderFramePre((ctx, scale) => {
			LineageLayout.drawLineageLanes(layout, ctx, scale);
			renderOverlay?.(ctx, scale);
		})
		.onRenderFramePost((ctx, scale) => {
			if (!style.quiet_links) return;
			for (const direct of [false, true]) {
				for (const link of graphData.links) {
					if (highlight.isLinkHighlighted(link) && highlight.isLinkDirect(link) === direct) {
						renderLink(link, ctx, scale);
					}
				}
			}
			// Keep cards and their labels above the emphasized dependency paths.
			for (const node of graphData.nodes) drawNode(node, ctx);
		})
		.nodeLabel(node => tooltip(label(node)))
		.nodeCanvasObjectMode(() => 'replace')
		.nodeCanvasObject((node, ctx) => drawNode(node, ctx))
		.nodePointerAreaPaint(paintPointerArea)
		.linkColor(link => highlight.isLinkHighlighted(link)
			? LineageConfig.LINK_STYLE.highlightColor
			: highlight.hasSelection() ? LineageConfig.LINK_STYLE.dimmedColor
				: link.dependency_type === 'fragment'
					? style.function_colors?.merge || style.link_color
					: style.link_color)
		.linkWidth(link => highlight.isLinkHighlighted(link)
			? LineageConfig.LINK_STYLE.highlightWidth : style.link_width)
		.linkCanvasObjectMode(() => 'replace')
		.linkCanvasObject((link, ctx, scale) => {
			if (!style.quiet_links || !highlight.isLinkHighlighted(link)) renderLink(link, ctx, scale);
		})
		.linkDirectionalParticles(LineageConfig.LINK_ROUTE.particleCount)
		.linkDirectionalParticleWidth(LineageConfig.LINK_ROUTE.particleWidth)
		.linkDirectionalParticleColor(() => LineageConfig.LINK_ROUTE.invisibleParticleColor)
		.linkDirectionalArrowLength(0)
		.onNodeClick((_node, event) => selectAtPointer(event))
		.onLinkClick((_link, event) => selectAtPointer(event))
		.onBackgroundClick(event => selectAtPointer(event))
		.cooldownTicks(LineageConfig.STATIC_LAYOUT_COOLDOWN_TICKS);
	if (color) forceGraph.nodeColor(color);
	if (nodeValue) forceGraph.nodeVal(nodeValue);
	if (nodeRelativeSize) forceGraph.nodeRelSize(nodeRelativeSize);
	const view = createLineageView(forceGraph, container, LineageConfig.DATASET_LAYOUT.fitPadding, '2d', layout.bounds);
	view.selectNode = id => highlight.select(graphData.nodes.find(node => node.id === id) || null);
	view.setFullLineage = value => highlight.setFullLineage(value);
	forceGraph.graphData(graphData);
	return view;
}

function createLineage3D(container, graphData, style, {
	label, color, object, onSelect, configure, highlight,
}) {
	const nodeColor = node => highlight?.hasSelection() && !highlight.isNodeHighlighted(node)
		? LineageConfig.DIMMED_COLOR
		: color(node);
	const createNodeObject = node => {
		const nodeObject = object(node);
		if (highlight?.hasSelection()) {
			const colorValue = nodeColor(node);
			nodeObject.traverse(object3d => {
				if (!object3d.isMesh) return;
				if (object3d.material?.color) object3d.material.color.set(colorValue);
				object3d.scale.setScalar(
					highlight.isSelected(node)
						? LineageConfig.NODE_STYLE_3D.selectedScale
						: highlight.isNodeHighlighted(node)
							? LineageConfig.NODE_STYLE_3D.highlightedScale
							: LineageConfig.NODE_STYLE_3D.dimmedScale,
				);
			});
		}
		return nodeObject;
	};
	const forceGraph = ForceGraph3D()(container)
		.width(container.clientWidth)
		.height(container.clientHeight)
		.backgroundColor(style.background_color)
		.nodeLabel(node => tooltip(label(node)))
		.nodeColor(nodeColor)
		.nodeRelSize(style.node_rel_size)
		.nodeResolution(style.node_resolution)
		.linkWidth(link => highlight?.isLinkHighlighted(link)
			? style.link_width * (style.quiet_links && !highlight.isLinkDirect(link)
				? LineageConfig.LINK_STYLE.transitiveWidthMultiplier3D
				: LineageConfig.LINK_STYLE.highlightWidthMultiplier3D)
			: style.link_width * (style.quiet_links ? LineageConfig.LINK_STYLE.overviewArrowScale : 1))
		.linkColor(link => highlight?.isLinkHighlighted(link)
			? style.quiet_links && !highlight.isLinkDirect(link)
				? LineageConfig.LINK_STYLE.transitiveColor : LineageConfig.LINK_STYLE.highlightColor
			: highlight?.hasSelection() ? LineageConfig.DIMMED_COLOR
				: link.dependency_type === 'fragment'
					? style.function_colors?.merge || style.link_color
					: style.link_color)
		.linkOpacity(style.link_opacity)
		.linkDirectionalParticles(link => !style.quiet_links || highlight?.isLinkHighlighted(link)
			? LineageConfig.LINK_STYLE.particleCount : 0)
		.linkDirectionalParticleWidth(LineageConfig.LINK_STYLE.particleWidth)
		.linkDirectionalParticleSpeed(LineageConfig.LINK_STYLE.particleSpeed)
		.linkDirectionalParticleColor(link => highlight?.isLinkHighlighted(link)
			? LineageConfig.LINK_STYLE.highlightParticleColor
			: highlight?.hasSelection() ? LineageConfig.DIMMED_COLOR : style.link_color)
		.onNodeClick(onSelect)
		.nodeThreeObject(createNodeObject);
	if (configure) configure(forceGraph);
	forceGraph.d3Force('charge').strength(style.charge_strength).distanceMax(style.charge_distance_max);
	forceGraph.d3Force('link').distance(style.link_distance);
	const view = createLineageView(forceGraph, container, LineageConfig.NODE_STYLE_3D.fitPadding, '3d');
	if (highlight) {
		view.setFullLineage = value => {
			highlight.setFullLineage(value);
			forceGraph.refresh();
		};
		view.selectNode = id => {
			highlight.select(graphData.nodes.find(node => node.id === id) || null);
			forceGraph.refresh();
		};
	}
	forceGraph.graphData(graphData);
	return view;
}

function labeledMesh(mesh, text, style, offset, dataType = null, iconName = null, badgeIconName = null) {
	const group = new THREE.Group();
	group.add(mesh);
	const label = new SpriteText(text || '', LineageConfig.NODE_STYLE_3D.labelHeight, style.label_color);
	label.backgroundColor = LineageConfig.NODE_STYLE_3D.labelBackground;
	label.padding = LineageConfig.NODE_STYLE_3D.labelPadding;
	label.borderRadius = LineageConfig.NODE_STYLE_3D.labelBorderRadius;
	label.position.set(0, offset, 0);
	group.add(label);
	const leadingIcon = iconName || (dataType !== null ? dataTypeIconName(dataType) || 'braces' : null);
	for (const [name, direction] of [[leadingIcon, -1], [badgeIconName, 1]]) {
		if (!name) continue;
		const canvas = document.createElement('canvas');
		canvas.width = canvas.height = 64;
		drawIcon(canvas.getContext('2d'), name, 0, 0, canvas.width, style.label_color);
		const texture = new THREE.CanvasTexture(canvas);
		texture.colorSpace = THREE.SRGBColorSpace;
		const icon = new THREE.Sprite(new THREE.SpriteMaterial({ map: texture, depthWrite: false }));
		const size = LineageConfig.NODE_STYLE_3D.labelHeight;
		icon.scale.set(size, size, 1);
		icon.position.set(direction * (label.scale.x / 2 + size * 0.75), offset, 0);
		group.add(icon);
	}
	return group;
}

const ExplorerLineage = {
	...LineageConfig,
	...LineageLayout,
	readPayload,
	tooltip,
	showDetails,
	appendLegend,
	prepareDatasetColors,
	datasetNodeObject,
	drawDataTypeIcon,
	drawIcon,
	drawCard,
	paintPointerArea,
	selectCard,
	createLineageHighlight,
	createLineageView,
	createLineage2D,
	createLineage3D,
	labeledMesh,
};

export { ExplorerLineage };
