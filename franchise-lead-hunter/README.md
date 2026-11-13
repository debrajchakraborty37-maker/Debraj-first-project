# Franchise Lead Hunter

Mobile app (Flutter, Android + iPhone + web) and secured API that find **B2B HNI franchise-investor leads** and **lead agencies**
from Google, and keep them in your Google Sheet. The Sheet is the database and master copy; the app can also export CSV copies.

```
Flutter app  ──HTTPS + login token──►  Node API  ──►  Google Sheet (Leads, Agencies, Runs, Rules)
                                         │
                                         └─►  Google Programmable Search (hourly hunt, monthly query budget)
```

## What is built

| Area | Status |
|---|---|
| Login (team accounts), token-secured API, lockout, rate limits | Done, tested |
| Google Sheet as database (read, add, update; adds columns on the right, never reorders yours) | Done, tested against an in-memory stand-in. **Not yet run against your real Sheet** (needs the service account, below) |
| Dashboard for Leads and Agencies | Done |
| Triage (swipe keep / skip, undo), Leads, Lead detail, Agencies, Agency detail, Log, Hunt rules, CSV export | Done, widget-tested |
| Hunt: Google search, B2B HNI filter, duplicate check, run log, monthly budget cap | Done, tested with a fake search; **not yet run against live Google Search** |
| Push notifications, contact enrichment (Apollo) | Not built yet (Version 1.1) |
| Android / iPhone store builds | Project is set up; needs Android SDK / Xcode on your machine |

## B2B HNI rule

A lead is **HNI B2B** when its stated budget is at least the HNI line (default Rs 1 crore, editable in Hunt rules) **and** the profession is a business owner or
senior decision maker (owner, director, founder, MD, CEO, partner, senior or general manager, and similar; see `server/src/segment.js`).
The hunt saves only HNI B2B leads. The app shows only HNI B2B by default; switch "B2B HNI only" off to see everything in the Sheet.

## Security

- Every API route except `/health` and login needs a signed token. Tokens expire (default 12 h) and stop working if the user is removed.
- Passwords are stored only as scrypt hashes. **The plain password is never in this repository.**
- 5 wrong passwords lock that account for 15 minutes; login and general rate limits; strict input validation; security headers; HTTPS required in production.
- The app keeps its token in the phone's secure storage. Release builds only talk to HTTPS addresses.
- Exports are protected against spreadsheet formula injection. The app only opens http(s), tel and mailto links.
- The service account key and search key live only on the server.

## Set up (about 30 minutes)

### 1. Google access
1. Google Cloud console: create a project, enable **Google Sheets API** and **Custom Search API**.
2. Create a **service account**, make a JSON key. Share your Sheet with the service account's email as **Editor**.
3. Create a **Programmable Search Engine** (search the entire web) for its id (`cx`), and an **API key** for Custom Search.

### 2. Server
```bash
cd server
npm install
npm test                      # 10 tests, no Google needed
npm run hash                  # type the password at the prompt, copy the hash it prints
cp .env.example .env          # fill JWT_SECRET, ADMIN_PASSWORD_HASH, GOOGLE_SERVICE_ACCOUNT_JSON, search keys
npm start
```
First start adds these columns on the right of your tabs if missing: Leads: Lead ID, Owner, Source URL, Segment. Agencies: Agency ID, Owner.
It creates two tabs, **Runs** and **Rules**, and fills ids for existing rows. Nothing is deleted or reordered.

Try it without Google: `npm run dev:demo` (in-memory sample data; set JWT_SECRET, ADMIN_EMAIL, ADMIN_PASSWORD_HASH first).

Deploy on Google Cloud Run: follow [DEPLOY_CLOUD_RUN.md](DEPLOY_CLOUD_RUN.md) (one service serves the API and the phone web app).

### 3. Team accounts
The admin is `ADMIN_EMAIL`. Add team members on the server: `npm run user:add -- name@company.com "Name" member`.

### 4. App
```bash
cd app
flutter pub get
flutter test
flutter run --dart-define=API_BASE_URL=https://your-server.example.com
flutter build apk --release --dart-define=API_BASE_URL=https://your-server.example.com   # Android
flutter build ipa --release --dart-define=API_BASE_URL=https://your-server.example.com   # iPhone, on a Mac
flutter build web --release --dart-define=API_BASE_URL=https://your-server.example.com   # open from any phone browser
```
For a web build on another address, put that address in `CORS_ORIGINS`.

## Monthly budget
Each search query counts. `monthlyQueryCap` (Hunt rules, default 2000) stops the hunt when used up; the Dashboard shows usage.
Google Custom Search gives 100 free queries a day, then bills per 1,000. `maxQueriesPerRun` (default 12) limits one run.

## Known limits
- Public search results rarely include names, phones or emails. The app shows "Contact hidden on source" and never goes around a login wall; enrichment is planned for 1.1.
- Reading budgets from search results is best effort. If a budget comes only from a URL, the note says "verify".
- Check each source site's terms before adding it to the hunt.
- Team accounts beyond the admin are stored in a file on the server; use a host with persistent disk, or move them to a store of your choice.
