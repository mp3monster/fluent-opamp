declare global {
  interface Window {
    __OPAMP_CSS_URLS__?: string[];
  }
}

export function applyThemeStylesheets(): void {
  const envRaw = import.meta.env.VITE_OPAMP_CSS_URLS as string | undefined;
  const envUrls = envRaw ? envRaw.split(',').map((value) => value.trim()).filter(Boolean) : [];
  const runtimeUrls = Array.isArray(window.__OPAMP_CSS_URLS__) ? window.__OPAMP_CSS_URLS__ : [];
  const urls = [...runtimeUrls, ...envUrls];

  for (const href of urls) {
    if (document.querySelector(`link[data-opamp-css="${href}"]`)) {
      continue;
    }
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = href;
    link.dataset.opampCss = href;
    document.head.appendChild(link);
  }
}
