function mountGraphViews(sourceData, create2D, create3D, showDetails, detailsPanel) {
	const buttons = [...document.querySelectorAll('[data-dimension]')];
	const errorMessage = document.getElementById('graph-error');
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
		const container = document.getElementById(`graph-${dimension}`);
		container.hidden = false;
		try {
			if (!views.has(dimension)) {
				// Force-graph mutates node positions and link endpoints; each view owns its data.
				const data = JSON.parse(JSON.stringify(sourceData));
				const create = dimension === '2d' ? create2D : create3D;
				const view = create(container, data, selectNode);
				views.set(dimension, view);
			}
		} catch (error) {
			console.error(`Unable to display ${dimension.toUpperCase()} graph`, error);
			container.hidden = true;
			container.replaceChildren();
			errorMessage.textContent = `Unable to display the ${dimension.toUpperCase()} graph. ${
				activeDimension ? 'The current view is still available.' : 'Check that graph libraries can load and reload this page.'
			}`;
			errorMessage.hidden = false;
			return;
		}
		const view = views.get(dimension);
		if (activeDimension) {
			views.get(activeDimension).graph.pauseAnimation();
			document.getElementById(`graph-${activeDimension}`).hidden = true;
		}
		activeDimension = dimension;
		view.graph.resumeAnimation();
		view.resize();
		detailsPanel.classList.toggle('details-2d', dimension === '2d');
		selectNode(sourceData.nodes.find(node => node.id === selectedId) || null);
		for (const button of buttons) {
			button.setAttribute('aria-pressed', String(button.dataset.dimension === dimension));
		}
		errorMessage.hidden = true;
	};
	for (const button of buttons) button.addEventListener('click', () => showView(button.dataset.dimension));
	document.getElementById('fit-graph').addEventListener('click', () => views.get(activeDimension)?.fit());
	for (const button of document.querySelectorAll('[data-zoom]')) {
		button.addEventListener('click', () => views.get(activeDimension)?.zoom(Number(button.dataset.zoom)));
	}
	const observer = new ResizeObserver(() => views.get(activeDimension)?.resize());
	observer.observe(document.getElementById('graph'));
	window.addEventListener('pagehide', () => {
		for (const view of views.values()) view.graph.pauseAnimation();
	});
	window.addEventListener('pageshow', () => views.get(activeDimension)?.graph.resumeAnimation());
	showView('2d');
}
