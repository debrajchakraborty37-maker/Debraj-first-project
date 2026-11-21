# Apps Script: sales and marketing performance reporting

Google Sheets reporting scripts. Each folder holds one `Code.gs` to paste into **Extensions > Apps Script** of the matching Google Sheet.

| Folder | What it builds |
|---|---|
| `sales-leader-brand-performance/` | Tabs **Performance** (MTD), **FTD Performance**, **Master Dashboard**, **Brand Performance** (Performance with Brand in column A and Sales Leader in column B), **MTM-Trends** and **MTM-Trends Dashboard** (brand-wise gap analysis, Sales vs Performance Marketing, with a Quality ~ TAT regression). |
| `tat-source-sheet/` | Imports the daily TeleCRM CSV exports from a Drive folder into the "Source Data" tab (refresh button, auto-continues past the 6-minute limit). |

## Set-up
1. Open the target Google Sheet, then **Extensions > Apps Script**, select all in `Code.gs`, paste the matching file, save.
2. Replace every `PASTE_...` placeholder at the top of the file with the real Google Sheet / Drive folder ID (the long text in the URL). The real IDs are deliberately not stored in this public repository.
3. Reload the sheet and use the menu (**Performance** or **TAT Source**).

## Notes
- Manual refresh only; nothing runs on a schedule.
- The code was tested against a mock of Apps Script using real exports, not by running inside Google Sheets. No lead data or exports are stored here.
