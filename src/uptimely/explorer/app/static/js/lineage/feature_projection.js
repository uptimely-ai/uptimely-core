// The canonical feature lineage connects inputs, operators, and outputs.
export function projectFeatureLineage(data, showOperators) {
	if (showOperators) return data;
	const nodes = new Map(data.nodes.map(node => [node.id, node]));
	const inputs = new Map();
	const outputs = new Map();
	const edges = new Map();
	const addEdge = (source, target, operatorId = null) => {
		const key = JSON.stringify([source, target]);
		if (!edges.has(key)) edges.set(key, { source, target, operator_ids: [] });
		const edge = edges.get(key);
		if (operatorId !== null && !edge.operator_ids.includes(operatorId)) {
			edge.operator_ids.push(operatorId);
		}
	};
	for (const link of data.links) {
		const source = nodes.get(link.source);
		const target = nodes.get(link.target);
		if (!source || !target) throw new Error("Feature lineage contains an unknown link endpoint.");
		if (source.is_operator === true && target.is_operator === true) {
			throw new Error("Feature lineage must connect operators through features.");
		}
		if (target.is_operator === true) {
			if (!inputs.has(target.id)) inputs.set(target.id, []);
			inputs.get(target.id).push(source.id);
		} else if (source.is_operator === true) {
			if (!outputs.has(source.id)) outputs.set(source.id, []);
			outputs.get(source.id).push(target.id);
		} else {
			addEdge(source.id, target.id);
		}
	}
	for (const node of data.nodes.filter(node => node.is_operator === true)) {
		for (const source of inputs.get(node.id) || []) {
			for (const target of outputs.get(node.id) || []) addEdge(source, target, node.id);
		}
	}
	return {
		nodes: data.nodes.filter(node => node.is_operator !== true),
		links: [...edges.values()].map(edge => ({
			...edge, operator_ids: edge.operator_ids.sort(),
		})),
	};
}
