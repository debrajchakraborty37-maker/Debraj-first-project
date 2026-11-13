// Usage: npm run hash            (prompts; nothing is echoed back or stored)
//        npm run hash -- "pw"    (avoid: the password lands in shell history)
import readline from 'node:readline';
import { hashPassword } from '../src/auth.js';

async function ask() {
  if (process.argv[2]) return process.argv[2];
  const rl = readline.createInterface({ input: process.stdin, output: process.stderr, terminal: true });
  return new Promise((resolve) => rl.question('Password: ', (a) => { rl.close(); resolve(a); }));
}

const pw = await ask();
if (pw.length < 8) { console.error('Use at least 8 characters.'); process.exit(1); }
console.log(hashPassword(pw));
