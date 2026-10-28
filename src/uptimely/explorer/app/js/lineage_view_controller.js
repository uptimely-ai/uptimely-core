export function mountLineageViews(
	sourceData, createLineage2D, createLineage3D, showDetails, detailsPanel,
) {
	const buttons = [...document.querySelectorAll('[data-dimension]')];
	const errorMessage = document.getElementById('lineage-error');
	const views = new Map();
	let activeDimension = null;
	let selectedId = null;
	const selectNode = node => {
		selectedId = node?.id ?? null;
		showDetails(node);
		for (const view of views.values()) view.selectNode?.(selectedId);
	};
	const showView = dimension => {
		if (dimension === activeDimension) return;
		const container = document.getElementById(`lineage-${dimension}`);
		container.hidden = false;
		try {
			if (!views.has(dimension)) {
				// Force-graph mutates node positions and link endpoints; each view owns its data.
				const data = JSON.parse(JSON.stringify(sourceData));
				const create = dimension === '2d' ? createLineage2D : createLineage3D;
				const view = create(container, data, selectNode);
				views.set(dimension, view);
			}
		} catch (error) {
			console.error(`Unable to display ${dimension.toUpperCase()} lineage`, error);
			container.hidden = true;
			container.replaceChildren();
			errorMessage.textContent = `Unable to display the ${dimension.toUpperCase()} lineage. ${
				activeDimension ? 'The current view is still available.' : 'Check that the visualization libraries can load and reload this page.'
			}`;
			errorMessage.hidden = false;
			return;
		}
		const view = views.get(dimension);
		if (activeDimension) {
			views.get(activeDimension).forceGraph.pauseAnimation();
			document.getElementById(`lineage-${activeDimension}`).hidden = true;
		}
		activeDimension = dimension;
		for (const button of buttons) {
			button.setAttribute('aria-pressed', String(button.dataset.dimension === dimension));
		}
		view.forceGraph.resumeAnimation();
		view.resize();
		detailsPanel.classList.toggle('details-2d', dimension === '2d');
		selectNode(sourceData.nodes.find(node => node.id === selectedId) || null);
		errorMessage.hidden = true;
	};
	for (const button of buttons) button.addEventListener('click', () => showView(button.dataset.dimension));
	document.getElementById('reset-lineage').addEventListener('click', () => {
		selectNode(null);
		views.get(activeDimension)?.fit();
	});
	for (const button of document.querySelectorAll('[data-zoom]')) {
		button.addEventListener('click', () => views.get(activeDimension)?.zoom(Number(button.dataset.zoom)));
	}
	const observer = new ResizeObserver(() => views.get(activeDimension)?.resize());
	observer.observe(document.getElementById('lineage'));
	window.addEventListener('pagehide', () => {
		for (const view of views.values()) view.forceGraph.pauseAnimation();
	});
	window.addEventListener('pageshow', () => views.get(activeDimension)?.forceGraph.resumeAnimation());
	showView('2d');
}
