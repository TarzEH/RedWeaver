/** Helpers for the MITRE ATT&CK Navigator (https://mitre-attack.github.io/attack-navigator/).
 *
 * RedWeaver layers are served behind auth on localhost, so the Navigator's
 * `#layerURL=` (which fetches a public, CORS-enabled URL client-side) can't reach
 * them. The reliable cross-environment path is: download the layer JSON locally,
 * then open the Navigator where the operator chooses "Open Existing Layer →
 * Upload". This helper does both in one click.
 */

export const NAVIGATOR_URL = "https://mitre-attack.github.io/attack-navigator/";

/** Trigger a browser download of an ATT&CK Navigator layer JSON. */
export function downloadLayer(layer: unknown, filename = "attack-layer.json"): void {
  const blob = new Blob([JSON.stringify(layer, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename.endsWith(".json") ? filename : `${filename}.json`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  // Revoke after the click has had a chance to start the download.
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/**
 * Download the layer and open the ATT&CK Navigator in a new tab. The caller
 * should surface a hint (toast) telling the operator to use the Navigator's
 * "Open Existing Layer → Upload" with the just-downloaded file.
 */
export function openInNavigator(layer: unknown, filename = "attack-layer.json"): void {
  downloadLayer(layer, filename);
  window.open(NAVIGATOR_URL, "_blank", "noopener,noreferrer");
}
