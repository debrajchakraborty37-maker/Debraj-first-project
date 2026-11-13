# Facebook and LinkedIn lead connectors

Leads from your Facebook Lead Ads and LinkedIn Lead Gen Forms land in the **Leads** tab of your Google Sheet. The app shows them straight away.
They use the same duplicate check and HNI B2B marking as the rest of the system, and every run is logged in the **Runs** tab.

```
Facebook Lead Ads ──(Graph API, every 15 min)──►┐
                                                 ├─► Leads tab ─► the app
LinkedIn Lead Gen Forms ──(CSV pasted in a tab)──┘
```

## What was built
| | Facebook | LinkedIn |
|---|---|---|
| How leads arrive | Pulled from the Graph API every 15 minutes | You paste the CSV downloaded from Campaign Manager |
| Fields mapped | Name, email, phone, city, job title, company, budget, brand, other answers | Same, with flexible column names |
| Duplicates | By Facebook lead id | By LinkedIn lead id, or email + name + form |
| Budget | Reads "1_2_crore", "Rs 50 lakh", "5000000" and similar. A bare number is not guessed | Same |
| Marking | HNI B2B when the budget is at least the HNI line and the job title is an owner or senior role; otherwise Other (still kept) | Same |
| Security | Token kept in Script Properties and sent in a header, never in a web address or the Sheet | No credentials needed |

Not built: posting to Facebook or LinkedIn, LinkedIn's lead API (it needs partner approval), looking up people's profiles, automatic messaging or connection requests.
LinkedIn does not allow profile scraping or automation, and either can get your account restricted.

## Install (5 minutes)
1. Apps Script: **+ > Script**, name it `Social`, paste `Social.gs`. Replace `Code.gs` with the new `Code.gs`. Save.
2. **Deploy > Manage deployments > pencil > New version > Deploy**.
3. Reload the Sheet. The **Lead Hunter** menu now has Facebook and LinkedIn items.

## Facebook setup
You need to be an **admin of the Facebook Page** and have at least one Lead Ad form.
1. **Create a developer app.** Go to developers.facebook.com > **My Apps > Create App**, choose a **Business** type. Leave it in **Development** mode. Because you are the app admin and the Page admin, you do not need Meta's app review.
2. **Get a Page access token.**
   - Open **Tools > Graph API Explorer**, choose your app, and press **Generate Access Token** with these permissions: `pages_show_list`, `pages_read_engagement`, `pages_manage_ads`, `leads_retrieval`.
   - Call `me/accounts`. Find your Page and copy its **id** and **access_token**.
   - To make the token last, exchange the user token for a long-lived one first (`/oauth/access_token?grant_type=fb_exchange_token&client_id=APP_ID&client_secret=APP_SECRET&fb_exchange_token=TOKEN`), then call `me/accounts` again. A Page token from a long-lived user token does not expire.
   - **Keep the app secret and the tokens private.** Never paste them into chat or a document.
3. **Check Leads access.** In Meta Business Suite > Settings > Integrations > **Leads Access**, make sure your user (and your app, if listed) can access the Page's leads.
4. In the Sheet: **Lead Hunter > Facebook: connect page**. Enter the Page ID, then the token. It shows the Page name and the number of lead forms found. Nothing is saved if it fails.
5. **Facebook: import leads now** to test, then **Facebook: auto-import every 15 min**.

Meta keeps lead data for about 90 days, so keep the auto-import on.

## LinkedIn setup
1. **Lead Hunter > LinkedIn: set up import tab.** This creates the `Import_LinkedIn` tab.
2. In LinkedIn Campaign Manager: **Account assets > Lead gen forms > Download leads**. Choose the form and dates.
3. Open the CSV, copy everything including its header row, and paste it into `Import_LinkedIn` at cell **A1**. Column names can differ from the sample; common ones (First Name, Last Name, Email, Phone Number, Company Name, Job Title, City, Created Time) are recognised.
4. **Lead Hunter > LinkedIn: import leads now.** Imported rows get a date in an **Imported** column, so pasting the same file again never creates duplicates.

If you use Zapier or Make, they can send LinkedIn Lead Gen Form leads into the same tab automatically.

## Privacy
- Leads submitted a form themselves, and the note on each lead records that. Use the data only for the purpose stated on the form.
- To delete a person on request, delete their row in Leads (and in `Import_LinkedIn`).
- Keep Sheet editors to people you trust: they can read the script's properties.

## If something stops working
- Look at the **Runs** tab. A failed Facebook import shows "Facebook said: …" with the reason.
- "Error validating access token": the token expired or was revoked (for example after a password change). Generate a new token and run **Facebook: connect page** again.
- No leads appear: check the form has leads, the Page ID is right, and your user has Leads access.
