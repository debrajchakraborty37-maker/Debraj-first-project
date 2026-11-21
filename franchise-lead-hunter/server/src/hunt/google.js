// Google Programmable Search (Custom Search JSON API). Needs GOOGLE_SEARCH_API_KEY and GOOGLE_SEARCH_CX.
// Search is billed per query, so every call is counted by the hunt and capped by the monthly budget.
export class GoogleSearch {
  constructor({ apiKey, cx, fetchImpl = fetch }) {
    this.apiKey = apiKey; this.cx = cx; this.fetch = fetchImpl;
  }
  get configured() { return Boolean(this.apiKey && this.cx); }

  /** @returns {Promise<{title:string, snippet:string, link:string}[]>} */
  async search(query, { num = 10 } = {}) {
    if (!this.configured) throw new Error('Google Search API is not configured');
    const url = new URL('https://www.googleapis.com/customsearch/v1');
    url.search = new URLSearchParams({ key: this.apiKey, cx: this.cx, q: query, num: String(num), gl: 'in' }).toString();
    const res = await this.fetch(url, { signal: AbortSignal.timeout(15_000) });
    if (!res.ok) throw new Error(`Google Search failed (${res.status})`);
    const data = await res.json();
    return (data.items || []).map((i) => ({ title: i.title || '', snippet: i.snippet || '', link: i.link || '' }));
  }
}
