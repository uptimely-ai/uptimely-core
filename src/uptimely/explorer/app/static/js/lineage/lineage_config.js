export const DATASET_PALETTE = Object.freeze([
	'#ff9f43', '#2dd4bf', '#fb7185', '#a78bfa',
	'#facc15', '#60a5fa', '#f472b6', '#a3e635',
	'#22d3ee', '#c084fc', '#4ade80', '#f87171',
]);
export const UNASSIGNED_DATASET = 'Unassigned';
export const CARD_STYLE = Object.freeze({
	minWidth: 112, maxWidth: 280, characterWidth: 8, horizontalPadding: 52,
	height: 38, cornerRadius: 12,
	shadowColor: 'rgba(0, 0, 0, .36)', shadowBlur: 14, shadowOffsetY: 4,
	background: '#1a2732', featureBackground: '#172a35', dimmedBackground: '#121c24',
	textColor: '#e8edf2', dimmedTextColor: 'rgba(232, 237, 242, .3)',
	font: '600 12px "DM Sans", sans-serif',
	borderWidth: 1.5, selectedBorderWidth: 3, selectedBorderColor: '#f8d66d',
	iconLeft: 12, iconSize: 12, iconRadius: 3,
	featureIconLeft: 13, featureIconWidth: 4, featureIconHeight: 18, featureIconRadius: 2,
	labelLeft: 34, labelHorizontalPadding: 46,
});
export const LINK_STYLE = Object.freeze({
	highlightColor: '#67e8f9', dimmedColor: 'rgba(70, 84, 95, .35)',
	highlightWidth: 3, highlightWidthMultiplier3D: 3, width2D: 1.5,
	particleCount: 2, particleWidth: 2, particleSpeed: 0.003,
	highlightParticleColor: '#f8d66d',
});
export const DIMMED_COLOR = '#46545f';
export const MIN_RENDER_SCALE = 0.01;
export const STATIC_LAYOUT_COOLDOWN_TICKS = 1;
export const DATASET_LAYOUT = Object.freeze({
	rankGap: 100, nodeSpacing: 70, fitPadding: 80,
	lanePadding: 32, laneHeaderHeight: 36, laneGap: 16,
	labelFont: '600 14px "DM Sans", sans-serif', labelColor: '#9fb3c3',
	evenBackground: 'rgba(143, 163, 181, .07)', oddBackground: 'rgba(143, 163, 181, .03)',
	borderColor: 'rgba(143, 163, 181, .3)', orderingPasses: 4,
});
export const LINK_ROUTE = Object.freeze({
	straightTolerance: 1, cornerRadius: 14, curveSteps: 8,
	arrowLength: 8, arrowHalfAngle: Math.PI / 6,
	flowDurationMs: 2200, particleRadius: 2.5, particleColor: '#e6f4ff',
	// Keep the renderer active while the custom canvas particles animate.
	particleCount: 1, particleWidth: 0.1, invisibleParticleColor: 'rgba(0, 0, 0, 0)',
});
export const VIEW_TIMING = Object.freeze({ initialFit: 0, fit: 600, zoom: 250 });
export const NODE_STYLE_3D = Object.freeze({
	sphereWidthSegments: 16, sphereHeightSegments: 12, labelOffset: 14,
	selectedScale: 1.4, highlightedScale: 1.15, dimmedScale: 0.75,
	fitPadding: 60, labelHeight: 3.2, labelBackground: 'rgba(16,24,32,0.72)',
	labelPadding: 2, labelBorderRadius: 2,
});
