/** Fixed guide panel width — keep in sync with DemoGuidePanel + CommandCenter offset. */
export const GUIDE_PANEL_WIDTH_PX = 400;
export const GUIDE_PANEL_WIDTH_XL_PX = 340;

export function guidePanelWidthPx(viewportWidth: number): number {
  if (viewportWidth < 1280) return GUIDE_PANEL_WIDTH_XL_PX;
  return Math.min(GUIDE_PANEL_WIDTH_PX, Math.round(viewportWidth * 0.35));
}
