# Deploy on Google Cloud Run

One Cloud Run service runs the API **and** the phone web app, so you get one HTTPS link. Cloud Scheduler triggers the hourly hunt.
Everything below runs in **Google Cloud Shell** (the `>_` button at the top right of console.cloud.google.com). Replace the values in CAPITALS.

You need: a Google Cloud project with billing on, and edit access to your Google Sheet.

## 1. Get the code and set variables
```bash
git clone -b claude/cool-gauss-0w53xz https://github.com/debrajchakraborty37-maker/Debraj-first-project.git
cd Debraj-first-project/franchise-lead-hunter/server

export PROJECT_ID=YOUR_PROJECT_ID
export REGION=asia-south1
export SHEET_ID=1nlnxzk2sFn5vC81XJp6-oej9OU1ZhSL9wVRVTZeSycs
gcloud config set project $PROJECT_ID
```
If the repository is private, Git asks for your GitHub user name and a personal access token (read access to this repository).

## 2. Turn on the Google services
```bash
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com \
  secretmanager.googleapis.com sheets.googleapis.com customsearch.googleapis.com cloudscheduler.googleapis.com
```

## 3. Create the server's identity and give it your Sheet
```bash
gcloud iam service-accounts create flh-server --display-name="Lead Hunter server"
export SA=flh-server@$PROJECT_ID.iam.gserviceaccount.com
echo $SA
```
Open your Google Sheet, press **Share**, paste the address printed above, set **Editor**, and untick "Notify". No key file is needed: Cloud Run uses this identity.

## 4. Set up Google Search (the lead finder)
1. Go to programmablesearchengine.google.com, create a search engine that searches **the entire web**, and copy its **Search engine ID** (`cx`).
2. In the Cloud console: APIs & Services, Credentials, **Create credentials, API key**. Restrict it to **Custom Search API**.
```bash
export SEARCH_CX=YOUR_SEARCH_ENGINE_ID
```

## 5. Store the secrets
Nothing secret goes into the code or the command line history.
```bash
# random signing key and scheduler secret
openssl rand -base64 48 | tr -d '\n' | gcloud secrets create flh-jwt-secret --data-file=-
openssl rand -hex 24    | tr -d '\n' | gcloud secrets create flh-scheduler-token --data-file=-

# admin password: type it at the prompt; only its hash is stored
npm install --omit=dev --silent
node scripts/hash-password.js | tr -d '\n' | gcloud secrets create flh-admin-hash --data-file=-

# search API key: paste it at the prompt (nothing is shown)
read -rs KEY; printf '%s' "$KEY" | gcloud secrets create flh-search-key --data-file=-; unset KEY

for s in flh-jwt-secret flh-scheduler-token flh-admin-hash flh-search-key; do
  gcloud secrets add-iam-policy-binding $s --member="serviceAccount:$SA" --role=roles/secretmanager.secretAccessor
done
```

## 6. Deploy
```bash
gcloud run deploy flh-server --source . --region $REGION \
  --service-account $SA --allow-unauthenticated \
  --min-instances 0 --max-instances 1 --memory 512Mi --timeout 300 \
  --set-env-vars "NODE_ENV=production,STORE=google,SCHEDULER=off,SHEET_ID=$SHEET_ID,GOOGLE_SEARCH_CX=$SEARCH_CX,ADMIN_EMAIL=debraj.c@theebg.com,ADMIN_NAME=Debraj C" \
  --set-secrets "JWT_SECRET=flh-jwt-secret:latest,ADMIN_PASSWORD_HASH=flh-admin-hash:latest,GOOGLE_SEARCH_API_KEY=flh-search-key:latest,SCHEDULER_TOKEN=flh-scheduler-token:latest"
```
`--allow-unauthenticated` only means the web address is public. Every data route still needs a login token; without it the server answers 401.
`--max-instances 1` keeps one hunt at a time and one login-lockout counter.

On first start the server adds a few columns to the right of your **Leads** and **Agencies** tabs and creates the **Runs** and **Rules** tabs. Nothing is deleted or reordered.

## 7. Check it
```bash
export URL=$(gcloud run services describe flh-server --region $REGION --format='value(status.url)')
echo $URL
curl $URL/health                                   # {"ok":true}
curl -s -o /dev/null -w "%{http_code}\n" $URL/api/leads   # 401 (no login, no data)
```
Open `$URL` on your phone, sign in with `debraj.c@theebg.com` and your password, then use the browser menu **Add to Home screen**.

## 8. Run the hunt every hour
Cloud Run sleeps between requests, so Cloud Scheduler wakes it:
```bash
TOKEN=$(gcloud secrets versions access latest --secret flh-scheduler-token)
gcloud scheduler jobs create http flh-hourly-hunt --location $REGION --schedule="0 * * * *" \
  --uri="$URL/internal/scheduled-hunt" --http-method=POST --headers="X-Scheduler-Token=$TOKEN" --attempt-deadline=300s
gcloud scheduler jobs run flh-hourly-hunt --location $REGION     # try it once now
```
The saved **schedule** in Hunt rules (hourly, every 3 h, daily, off) decides whether each call actually hunts.

## 9. Team members
Create a hash for each person (`node scripts/hash-password.js`), then save this as a secret and attach it:
```bash
cat > users.json <<'JSON'
[{"email":"name@theebg.com","name":"Name","role":"member","hash":"PASTE_HASH_HERE"}]
JSON
gcloud secrets create flh-users --data-file=users.json && rm users.json
gcloud secrets add-iam-policy-binding flh-users --member="serviceAccount:$SA" --role=roles/secretmanager.secretAccessor
gcloud run services update flh-server --region $REGION --update-secrets USERS_JSON=flh-users:latest
```

## 10. Android and iPhone apps (optional)
The web app already works from the phone browser. For store apps, build with your address:
```bash
cd ../app
flutter build apk --release --dart-define=API_BASE_URL=$URL      # Android
flutter build ipa --release --dart-define=API_BASE_URL=$URL      # iPhone, on a Mac
```

## Updating later
Re-run the step 6 command. To rebuild the web app first: `cd app && flutter build web --release --no-web-resources-cdn`, then copy it into `server/public` as before.

## If something goes wrong
- **Deploy says the container failed to start:** `gcloud run services logs read flh-server --region $REGION --limit 30`. The usual cause is the Sheet not shared with `$SA` as Editor, or a missing secret permission.
- **Login says "incorrect":** check `ADMIN_EMAIL` and re-create the hash secret with `gcloud secrets versions add flh-admin-hash --data-file=<(node scripts/hash-password.js | tr -d '\n')`, then redeploy.
- **"Google Search is not set up" on the dashboard:** the search key or engine ID is missing.
- **Organisation blocks public access:** your admin must allow `--allow-unauthenticated` (allUsers invoker) for this service.

## Cost
At this size Cloud Run, Cloud Scheduler (3 free jobs) and Secret Manager are close to free. Google Custom Search gives 100 free queries a day, then is billed per 1,000; the monthly cap in Hunt rules stops overspending.

## Security reminders
- Change the admin password you shared earlier; set it fresh at step 5.
- The service account only needs access to this one Sheet. Do not give it project-wide roles.
