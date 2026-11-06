import { ExplorerLineage } from './graph_components.js';
import { mountLineageViews } from './graph_view_controller.js';

export function initializeLineage(
	signal, updateDetails, createLineage2D, createLineage3D, projectData = null,
) {
	const graphData = ExplorerLineage.readPayload('graph-data');
	const style = ExplorerLineage.readPayload('graph-style');
	ExplorerLineage.prepareDatasetColors(graphData, document.getElementById('dataset-legend'));

	const createView = create => (container, data, updateSelection) =>
		create(container, data, updateSelection, style, ExplorerLineage.createLineageHighlight(data));

	return mountLineageViews(
		graphData, createView(createLineage2D), createView(createLineage3D), updateDetails,
		signal, projectData);
}
