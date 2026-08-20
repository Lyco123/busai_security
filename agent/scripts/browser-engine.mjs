import { chromium } from 'playwright';

export function browserEngineConfig(env = process.env) {
  return {
    engine: String(env.ASSISTANT_BROWSER_ENGINE || 'chromium').trim().toLowerCase(),
    cdpEndpoint: env.ASSISTANT_CDP_ENDPOINT || 'http://127.0.0.1:9222',
  };
}

export async function openBrowser(config) {
  const engineConfig = browserEngineConfig();

  if (engineConfig.engine === 'obscura') {
    const browser = await chromium.connectOverCDP(engineConfig.cdpEndpoint);
    return {
      browser,
      engine: engineConfig.engine,
      cdpEndpoint: engineConfig.cdpEndpoint,
      close: () => browser.close(),
    };
  }

  if (engineConfig.engine !== 'chromium') {
    throw new Error(`Unsupported ASSISTANT_BROWSER_ENGINE: ${engineConfig.engine}`);
  }

  const browser = await chromium.launch({
    headless: config.headless,
    channel: config.browserChannel || undefined,
  });
  return {
    browser,
    engine: engineConfig.engine,
    cdpEndpoint: null,
    close: () => browser.close(),
  };
}
