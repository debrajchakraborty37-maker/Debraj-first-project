import cron from 'node-cron';
import { loadConfig } from './config.js';
import { GoogleSheetStore } from './sheets/googleStore.js';
import { MemoryStore } from './sheets/memoryStore.js';
import { createRepos } from './repo.js';
import { GoogleSearch } from './hunt/google.js';
import { Hunter } from './hunt/hunt.js';
import { createApp } from './app.js';
import { demoSeed } from './demoData.js';
import { isDue } from './hunt/schedule.js';

const cfg = loadConfig();
const store = cfg.store === 'memory'
  ? new MemoryStore(demoSeed())
  : new GoogleSheetStore({ sheetId: cfg.sheetId, serviceAccountJson: cfg.serviceAccountJson });
const repos = await createRepos(store);
const search = new GoogleSearch({ apiKey: cfg.searchApiKey, cx: cfg.searchEngineId });
const hunter = new Hunter({ repos, search });
const app = createApp({ cfg, repos, hunter });

// Runs at the top of every hour and lets the saved rules decide whether this hour is a hunt hour.
if (cfg.schedulerEnabled) {
  cron.schedule('0 * * * *', async () => {
    try {
      const { schedule } = await repos.rules.get();
      if (isDue(schedule, new Date().getUTCHours())) console.info('scheduled hunt', await hunter.run({ trigger: 'schedule', by: 'scheduler' }));
    } catch (e) { console.error('scheduled hunt failed', e.message); }
  });
}

app.listen(cfg.port, () => console.info(`Franchise Lead Hunter API on :${cfg.port} (store=${cfg.store})`));
