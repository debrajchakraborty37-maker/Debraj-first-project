import crypto from 'node:crypto';
import fs from 'node:fs';
import jwt from 'jsonwebtoken';

const N = 16384, R = 8, P = 1, KEYLEN = 64;

export function hashPassword(password) {
  const salt = crypto.randomBytes(16);
  const hash = crypto.scryptSync(password, salt, KEYLEN, { N, r: R, p: P });
  return `scrypt$${N}$${salt.toString('base64')}$${hash.toString('base64')}`;
}

export function verifyPassword(password, stored) {
  try {
    const [alg, n, salt, hash] = String(stored).split('$');
    if (alg !== 'scrypt') return false;
    const expected = Buffer.from(hash, 'base64');
    const actual = crypto.scryptSync(password, Buffer.from(salt, 'base64'), expected.length, {
      N: Number(n), r: R, p: P,
    });
    return crypto.timingSafeEqual(actual, expected);
  } catch {
    return false;
  }
}

// A fixed hash so unknown emails cost the same time as known ones.
const DUMMY = hashPassword('not-a-real-password');

export class UserDirectory {
  constructor(cfg) {
    this.cfg = cfg;
  }
  all() {
    const users = [{
      email: this.cfg.adminEmail, name: this.cfg.adminName, role: 'admin', hash: this.cfg.adminPasswordHash,
    }];
    const sources = [];
    try { sources.push(JSON.parse(fs.readFileSync(this.cfg.usersFile, 'utf8'))); } catch { /* no users file */ }
    try { if (this.cfg.usersJson) sources.push(JSON.parse(this.cfg.usersJson)); } catch { /* bad USERS_JSON is ignored */ }
    for (const extra of sources) {
      for (const u of Array.isArray(extra) ? extra : []) {
        if (u.email && u.hash && !users.some((x) => x.email === u.email.toLowerCase())) {
          users.push({ email: u.email.toLowerCase(), name: u.name || u.email, role: u.role === 'admin' ? 'admin' : 'member', hash: u.hash });
        }
      }
    }
    return users;
  }
  authenticate(email, password) {
    const user = this.all().find((u) => u.email === String(email).trim().toLowerCase());
    const ok = verifyPassword(String(password), user ? user.hash : DUMMY);
    return ok && user ? { email: user.email, name: user.name, role: user.role } : null;
  }
  find(email) {
    const u = this.all().find((x) => x.email === String(email).toLowerCase());
    return u ? { email: u.email, name: u.name, role: u.role } : null;
  }
}

export function signToken(cfg, user) {
  return jwt.sign({ sub: user.email, name: user.name, role: user.role }, cfg.jwtSecret, {
    algorithm: 'HS256', expiresIn: cfg.jwtTtl, issuer: 'flh-server',
  });
}

export function requireAuth(cfg, users) {
  return (req, res, next) => {
    const h = req.headers.authorization || '';
    const token = h.startsWith('Bearer ') ? h.slice(7) : '';
    try {
      const p = jwt.verify(token, cfg.jwtSecret, { algorithms: ['HS256'], issuer: 'flh-server' });
      const user = users.find(p.sub); // removed users lose access at once
      if (!user) throw new Error('unknown user');
      req.user = user;
      next();
    } catch {
      res.status(401).json({ error: 'unauthorized' });
    }
  };
}

export const requireAdmin = (req, res, next) =>
  req.user?.role === 'admin' ? next() : res.status(403).json({ error: 'forbidden' });
