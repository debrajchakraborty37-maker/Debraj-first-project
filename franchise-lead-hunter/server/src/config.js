import 'dotenv/config';

function req(env, name) {
  const v = env[name];
  if (!v) throw new Error(`Missing required environment variable ${name}`);
  return v;
}

/** Build the config from an env object (injectable for tests). */
export function loadConfig(env = process.env) {
  const store = env.STORE || 'google';
  const cfg = {
    nodeEnv: env.NODE_ENV || 'development',
    port: Number(env.PORT || 8080),
    store,
    jwtSecret: req(env, 'JWT_SECRET'),
    jwtTtl: env.JWT_TTL || '12h',
    adminEmail: (env.ADMIN_EMAIL || '').trim().toLowerCase(),
    adminPasswordHash: env.ADMIN_PASSWORD_HASH || '',
    adminName: env.ADMIN_NAME || 'Admin',
    corsOrigins: (env.CORS_ORIGINS || '').split(',').map((s) => s.trim()).filter(Boolean),
    usersFile: env.USERS_FILE || new URL('../data/users.json', import.meta.url).pathname,
    sheetId: store === 'google' ? req(env, 'SHEET_ID') : env.SHEET_ID || '',
    serviceAccountJson: env.GOOGLE_SERVICE_ACCOUNT_JSON || '', // raw JSON or base64
    searchApiKey: env.GOOGLE_SEARCH_API_KEY || '',
    searchEngineId: env.GOOGLE_SEARCH_CX || '',
    schedulerEnabled: env.SCHEDULER !== 'off',
    schedulerToken: env.SCHEDULER_TOKEN || '', // lets Cloud Scheduler trigger hunts
    usersJson: env.USERS_JSON || '', // extra team users as JSON, e.g. from Secret Manager
    publicDir: env.PUBLIC_DIR || new URL('../public', import.meta.url).pathname,
  };
  if (cfg.jwtSecret.length < 32) throw new Error('JWT_SECRET must be at least 32 characters');
  if (!cfg.adminEmail || !cfg.adminPasswordHash) {
    throw new Error('ADMIN_EMAIL and ADMIN_PASSWORD_HASH must be set (use `npm run hash`)');
  }
  if (cfg.schedulerToken && cfg.schedulerToken.length < 24) throw new Error('SCHEDULER_TOKEN must be at least 24 characters');
  if (cfg.nodeEnv === 'production' && cfg.store !== 'google') {
    throw new Error('STORE must be "google" in production');
  }
  return cfg;
}
