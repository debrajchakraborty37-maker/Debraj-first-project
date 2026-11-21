# Use the Google Sheet as the server (no Cloud Run, no hosting bill)

Google Apps Script runs **inside your Sheet** and acts as the server:

```
Phone app / web app ──► Apps Script web app (inside your Sheet) ──► Leads, Agencies, Runs, Rules tabs
                              │
                              └─► Google Search (hourly, by a time trigger)
```

The script is in `apps-script/Code.gs`. It does the same job as the Node server: login, dashboard, leads, agencies, hunt, rules, CSV export.
Passwords are never saved, only salted hashes in the script's private properties. Every call except `health` needs a login token.

> **Simplest way (recommended):** the script also serves the app itself. Add `Index.html` next to `Code.gs` (Apps Script: **+ > HTML**, name it `Index`), deploy, turn on **Open access**, and open the Web app address. The Dashboard appears directly, with no login, no separate hosting and no server address to paste.

## 1. Add the script to your Sheet (5 minutes)
1. Open your Google Sheet. Menu **Extensions > Apps Script**.
2. Delete the sample code. Paste all of `apps-script/Code.gs`.
3. Left side, **Project Settings** (gear): tick **Show "appsscript.json" manifest file in editor**. Back in **Editor**, open `appsscript.json` and paste the contents of `apps-script/appsscript.json`.
4. Press **Save**. Close the Apps Script tab and **reload the Sheet**. A new menu **Lead Hunter** appears (wait a few seconds).

## 2. Set it up from the Lead Hunter menu
Click each item once, in order. Google asks you to **authorise** the first time (Advanced > Go to project, because it is your own script).
1. **1. Set up tabs**: adds columns on the right of Leads and Agencies, creates Runs and Rules, adds ids to your existing rows. Your data is not changed or reordered.
2. **2. Set admin login**: type `debraj.c@theebg.com`, then choose a password (10+ characters). Use a **new** password, not the one shared in chat.
3. **3. Set Google Search keys**: paste the API key and the Search engine ID (see "Google Search" below). You can skip this and add it later; the app will say search is not set up.
4. **4. Start hourly hunt**: creates the time trigger. The app's Hunt rules decide whether each hour really hunts.

### Google Search (the lead finder)
1. programmablesearchengine.google.com: create a search engine that searches **the entire web**; copy its **Search engine ID**.
2. console.cloud.google.com: APIs & Services, enable **Custom Search API**, then Credentials, **Create API key**, restrict it to Custom Search API.
Google gives 100 free queries a day. The monthly cap in Hunt rules limits spending.

## 3. Publish it as a web app
1. In Apps Script: **Deploy > New deployment > Web app**.
2. **Execute as: Me**. **Who has access: Anyone**. Deploy.
3. Copy the **Web app URL** (ends in `/exec`). The menu item **Show app address** shows it again.

"Anyone" only means the address is reachable. Every data call still needs the login token; without it the script answers 401.
If your Google Workspace admin does not allow "Anyone", ask them to, or use the Cloud Run guide instead (`DEPLOY_CLOUD_RUN.md`).

Check it: open the URL in a browser. You should see `{"ok":true}`.

## 4. Open the app on your phone
**Web app (fastest):**
1. Upload the folder `franchise-lead-hunter/server/public` to a free static host. Easiest: **app.netlify.com/drop**, drag the folder in, and you get an `https://...netlify.app` link. (Cloudflare Pages or GitHub Pages also work.)
2. Open the link on your phone. On the sign-in screen open **Server address (advanced)**, paste the Web app URL, enter your login, and sign in.
3. Browser menu, **Add to Home screen**. The address is remembered on that phone.

**Android app (optional):** `cd app && flutter build apk --release --dart-define=API_BASE_URL=PASTE_WEB_APP_URL`.

## 5. Team members
Menu **Lead Hunter > Add team member** (email, name, password). They sign in the same way. Only the admin can change Hunt rules.

## Good to know
- **How the web app talks to the script:** browsers block normal calls to Google's script servers, so the web app loads each reply as a script tag (a GET with the request in the address). Phone apps use POST. When a login is used, the password travels in that web address over HTTPS, so keep a strong password and keep the app address private.
- **Slower than a server.** Each call takes about 1 to 3 seconds. Fine for a few hundred leads; for thousands, use the Cloud Run version.
- **Limits:** Apps Script allows about 20,000 web calls and 20,000 search fetches a day on a normal Google account (more on Workspace). A hunt must finish in 6 minutes; the 12-query default is well inside that.
- **Passwords:** hashed with a salt, 3,000 rounds of HMAC-SHA256. That is weaker than the Node server's scrypt, so use a long password. Five wrong tries lock an account for 15 minutes.
- **Updating the script:** paste the new `Code.gs`, then **Deploy > Manage deployments > edit > New version**. The address stays the same.
- **Who can edit the Sheet can read the script and its properties.** Keep the Sheet's editors to people you trust. Viewers cannot.
- Both servers can write the same tabs, but run only one at a time.
