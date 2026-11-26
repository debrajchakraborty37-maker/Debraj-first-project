# Sales Insights Dashboard (Angular)

A management sales dashboard: filters, key tiles (Gross / Net / Total Sales, Bill Cuts, APC, online and offline, week-to-date,
month-to-date, Swiggy and Zomato), four charts, APC by business type, and data checks.

**This project ships with SAMPLE data only** (invented brands and numbers). No real company data is stored in it. The repository
is public, so never commit real sales data here.

## Run it on your computer
You need Node.js (current LTS). Then, in this folder:

```bash
npm install
npm start
```

Open http://localhost:4200. Other commands:

```bash
npm test          # unit tests (calculations and the page)
npm run build     # production build into dist/
```

## Where things are
| File | What it does |
|---|---|
| `src/app/core/models.ts` | The shape of one Daily Data row, the metrics and the filters |
| `src/app/core/calc.ts` | All the maths: totals, online/offline, WTD/MTD, trend, rankings, APC by type, data checks |
| `src/app/core/dashboard.store.ts` | Holds the data and the filter choices; every number on screen is derived from these |
| `src/app/core/data-source.ts` | Where rows come from: `sample` (default) or `api` |
| `src/app/core/sample-data.ts` | The invented demo data |
| `src/app/app.ts`, `app.html` | The page: filters, tiles, charts, tables |
| `src/app/ui/` | Small parts: tile, multi-select drop-down, bar chart |

## Rules built in (change them in `calc.ts` if the business decides otherwise)
- Net Sales is the headline. Gross and Total Sales show "Not reported" when no row has them (blank is not zero).
- Rows with the same date + brand + location are added together.
- Online = Zomato Online + Swiggy Online + Ownly (net). Offline = Net Sales - Online (dine-in included).
- APC = Net Sales / Bill Cuts, and is also shown per business type (cafes and showrooms are not comparable).
- Week to date starts on Monday. WTD, MTD and the 31-day trend count up to the "To" date, or the latest date in the data.

## Connect real data (next step)
The browser must never read the Google Sheet directly. Put a small secure back end in between:

```
Daily Data (Google Sheet)  ->  back end (checks who is signed in)  ->  this app
```

1. Build the back end so that `GET <apiUrl>` returns a JSON array of rows shaped like `DailyRow` in `models.ts`
   (`date` as `yyyy-mm-dd`; use `null` for a blank number).
2. In `src/app/core/data-source.ts` set `dataSource: 'api'` and `apiUrl: 'https://...'`.
3. Add Google sign-in limited to the company domain, and let the back end return only the brands each person may see.

## Roadmap
1. Real data through the back end, with sign-in and roles (CEO / COO / Sales Leader).
2. Targets, comparison with last week / last month, growth %.
3. Morning refresh and a daily summary email.
