export function mountLineageViews(
	sourceData, createLineage2D, createLineage3D, showDetails, signal, projectData = null,
) {
	const buttons = [...document.querySelectorAll('[data-dimension]')];
	const errorMessage = document.getElementById('lineage-error');
	const views = new Map();
	const containers = new Map();
	const projections = new Map();
	const operatorToggle = projectData ? document.getElementById('show-operators') : null;
	const operatorLegend = projectData ? document.getElementById('operator-legend') : null;
	let activeDimension = null;
	let activeKey = null;
	let activeData = sourceData;
	let showOperators = true;
	let selectedId = null;
	const readOperators = () => {
		if (!projectData) return true;
		const value = new URL(window.location.href).searchParams.get('operators');
		if (value !== null && value !== 'show' && value !== 'hide') {
			throw new Error('Unknown lineage operator mode. Use operators=show or operators=hide.');
		}
		return value !== 'hide';
	};
	const selectNode = node => {
		selectedId = node?.id ?? null;
		showDetails(node);
		for (const view of views.values()) view.selectNode?.(selectedId);
	};
	const showView = (dimension, operators = showOperators) => {
		const key = `${operators}:${dimension}`;
		if (key === activeKey) return true;
		const container = document.getElementById(`lineage-${dimension}`);
		const wasHidden = container.hidden;
		const cached = views.has(key);
		container.hidden = false;
		let viewContainer = containers.get(key);
		try {
			if (!projections.has(operators)) {
				projections.set(operators, projectData ? projectData(sourceData, operators) : sourceData);
			}
			if (!views.has(key)) {
				viewContainer = document.createElement('div');
				viewContainer.className = 'lineage-view';
				container.append(viewContainer);
				// Force-graph mutates node positions and link endpoints; each view owns its data.
				const data = JSON.parse(JSON.stringify(projections.get(operators)));
				const create = dimension === '2d' ? createLineage2D : createLineage3D;
				const view = create(viewContainer, data, selectNode);
				views.set(key, view);
				containers.set(key, viewContainer);
			}
		} catch (error) {
			console.error(`Unable to display ${dimension.toUpperCase()} lineage`, error);
			container.hidden = wasHidden;
			viewContainer?.remove();
			errorMessage.textContent = `Unable to display the ${dimension.toUpperCase()} lineage: ${error.message}. ${
				activeDimension ? 'The current view is still available.' : 'Check that the visualization libraries can load and reload this page.'
			}`;
			errorMessage.hidden = false;
			operatorToggle?.setAttribute('aria-pressed', String(showOperators));
			return false;
		}
		const view = views.get(key);
		if (activeDimension) {
			views.get(activeKey).forceGraph.pauseAnimation();
			containers.get(activeKey).hidden = true;
			if (activeDimension !== dimension) {
				document.getElementById(`lineage-${activeDimension}`).hidden = true;
			}
		}
		activeDimension = dimension;
		activeKey = key;
		activeData = projections.get(operators);
		showOperators = operators;
		viewContainer.hidden = false;
		operatorToggle?.setAttribute('aria-pressed', String(operators));
		if (operatorLegend) operatorLegend.hidden = !operators;
		for (const button of buttons) {
			button.setAttribute('aria-pressed', String(button.dataset.dimension === dimension));
		}
		view.forceGraph.resumeAnimation();
		view.resize(!cached);
		selectNode(activeData.nodes.find(node => node.id === selectedId) || null);
		errorMessage.hidden = true;
		return true;
	};
	for (const button of buttons) {
		button.addEventListener('click', () => showView(button.dataset.dimension), { signal });
	}
	operatorToggle?.addEventListener('click', () => {
		const operators = !showOperators;
		if (!showView(activeDimension || '2d', operators)) return;
		const url = new URL(window.location.href);
		url.searchParams.set('operators', operators ? 'show' : 'hide');
		window.history.pushState(null, '', url);
	}, { signal });
	document.getElementById('reset-lineage').addEventListener('click', () => {
		selectNode(null);
		views.get(activeKey)?.fit();
	}, { signal });
	for (const button of document.querySelectorAll('[data-zoom]')) {
		button.addEventListener('click', () => views.get(activeKey)?.zoom(Number(button.dataset.zoom)), { signal });
	}
	const observer = new ResizeObserver(() => views.get(activeKey)?.resize());
	observer.observe(document.getElementById('lineage'));
	signal.addEventListener('abort', () => {
		observer.disconnect();
		for (const view of views.values()) {
			view.forceGraph.pauseAnimation();
			view.forceGraph._destructor();
		}
		views.clear();
		containers.clear();
		projections.clear();
	}, { once: true });
	window.addEventListener('pagehide', () => {
		for (const view of views.values()) view.forceGraph.pauseAnimation();
	}, { signal });
	window.addEventListener('pageshow', () => views.get(activeKey)?.forceGraph.resumeAnimation(), { signal });
	showView('2d', readOperators());
	return { update: () => showView(activeDimension || '2d', readOperators()) };
}
