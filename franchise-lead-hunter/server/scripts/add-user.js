// Add a team member: npm run user:add -- name@company.com "Full Name" [admin|member]
// Prompts for the password and stores only its hash in data/users.json (git-ignored).
import fs from 'node:fs';
import path from 'node:path';
import readline from 'node:readline';
import { hashPassword } from '../src/auth.js';

const [email, name = '', role = 'member'] = process.argv.slice(2);
if (!email || !/^\S+@\S+\.\S+$/.test(email)) { console.error('Usage: npm run user:add -- email "Name" [admin|member]'); process.exit(1); }
const file = process.env.USERS_FILE || path.resolve('data/users.json');
const rl = readline.createInterface({ input: process.stdin, output: process.stderr, terminal: true });
const pw = await new Promise((r) => rl.question('Password for the new user: ', (a) => { rl.close(); r(a); }));
if (pw.length < 8) { console.error('Use at least 8 characters.'); process.exit(1); }
let users = [];
try { users = JSON.parse(fs.readFileSync(file, 'utf8')); } catch { /* new file */ }
users = users.filter((u) => u.email.toLowerCase() !== email.toLowerCase());
users.push({ email: email.toLowerCase(), name: name || email, role: role === 'admin' ? 'admin' : 'member', hash: hashPassword(pw) });
fs.mkdirSync(path.dirname(file), { recursive: true });
fs.writeFileSync(file, JSON.stringify(users, null, 2), { mode: 0o600 });
console.error(`Saved ${email} (${role}).`);
