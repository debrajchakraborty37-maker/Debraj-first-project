// Sample rows copied from the real Sheet, used only by the in-memory demo store and the tests.
import { LEAD_FIELDS, AGENCY_FIELDS } from './schema.js';

const h = (fields) => fields.map(([, header]) => header);
const lead = (o) => Object.fromEntries(LEAD_FIELDS.filter(([k]) => k in o).map(([k, header]) => [header, o[k]]));
const agency = (o) => Object.fromEntries(AGENCY_FIELDS.filter(([k]) => k in o).map(([k, header]) => [header, o[k]]));

export function demoSeed() {
  return {
    Leads: {
      headers: h(LEAD_FIELDS.slice(0, 13)),
      rows: [
        lead({ dateReceived: '06 Nov 2026', source: 'Google search (SMERGERS investor profile)', brand: 'Cafe / F&B', name: 'Name not shown (Owner, food and beverages, real estate)', city: 'Bangalore', profession: 'Owner, food and beverages, real estate', budgetCr: '5.00', quality: 'Warm', status: 'New', nextFollowUp: '09 Nov 2026', notes: 'Public profile, up to INR 5 crore for restaurants and bars. Contact details appear only after connecting on SMERGERS. https://www.smergers.com/investor/owner-food-beverages-real-estate-franchise-investor-in-bangalore-looking-to-invest-in-restaurants-and-bars-upto-inr-5-crore/fy1o7' }),
        lead({ dateReceived: '06 Nov 2026', source: 'Google search (SMERGERS investor profile)', brand: 'Beauty and wellness, gyms (branded, FOCO model)', name: 'Name not shown (Senior Manager, insurance agency)', city: 'Delhi', profession: 'Senior Manager, insurance agency', budgetCr: '1.80', quality: 'Warm', status: 'New', nextFollowUp: '09 Nov 2026', notes: 'Public profile, up to INR 1.8 crore. Contact details appear only after connecting on SMERGERS. https://www.smergers.com/investor/senior-manager-insurance-agency-franchise-investor-in-delhi-looking-to-invest-in-beauty-and-wellness-businesses-upto-inr-18-crore/frn6hy/' }),
        lead({ dateReceived: '06 Nov 2026', source: 'Google search (SMERGERS investor profile)', brand: 'Cafe / F&B', name: 'Name not shown (Director, hospitality)', city: 'Madhya Pradesh', profession: 'Director, hospitality', budgetCr: '1.00', quality: 'Warm', status: 'New', nextFollowUp: '09 Nov 2026', notes: 'Public profile, up to INR 1 crore. https://www.smergers.com/investor/director-hospitality-franchise-investor-in-madhya-pradesh-looking-to-invest-in-restaurants-and-bars-upto-inr-1-crore/60j8o/' }),
        lead({ dateReceived: '06 Nov 2026', source: 'Google search (SMERGERS investor profile)', brand: 'Cafe / F&B (cafes, hotels)', name: 'Name not shown (Owner, electronics and furniture retail)', city: 'Badnawar, Madhya Pradesh', profession: 'Owner, electronics and furniture retail and distribution', budgetCr: '3.00', quality: 'Warm', status: 'Meeting', nextFollowUp: '14 Nov 2026', notes: 'Prefers FOCO or FOFO model and will arrange premises. https://www.smergers.com/investor/owner-electronics-and-furniture-retail-and-distribution-franchise-investor-in-badnawar-looking-to-invest-in-restaurants-and-bars-and-hotels-and-resorts-upto-inr-3-crore/pyuu1/' }),
        lead({ dateReceived: '07 Nov 2026', source: 'Manual', brand: 'Cafe / F&B', name: 'Student (small budget)', city: 'Pune', profession: 'Student', budgetCr: '0.20', quality: 'Cold', status: 'New', nextFollowUp: '', notes: 'Below HNI threshold, shown only when "all data" is requested.' }),
      ],
    },
    Agencies: {
      headers: h(AGENCY_FIELDS.slice(0, 14)),
      rows: [
        agency({ dateAdded: '06 Nov 2026', name: 'Franchise India', type: 'Franchise portal and consultancy', website: 'https://www.franchiseindia.com', phone: '0129-4244444', email: 'feedback@franchiseindia.in', city: 'Faridabad, Haryana', leadsOnly: 'Unclear', services: 'Portal and expos where investors browse brands.', pricing: 'Not public', sourceUrl: 'https://www.franchiseindia.com', status: 'New', notes: 'Claims unverified.', linkedin: 'https://in.linkedin.com/company/franchiseindia' }),
        agency({ dateAdded: '06 Nov 2026', name: 'Interskale', type: 'Lead generation agency', website: 'https://www.interskale.in', phone: '+91-8369509606', email: 'info@interskale.in', city: 'Mumbai', leadsOnly: 'Yes', services: 'Paid-ad franchisee leads with lead management tools.', pricing: 'From about Rs 1 lakh, 3-month minimum', sourceUrl: 'https://www.interskale.in/franchisee-lead-generation.html', status: 'New', notes: 'Ask whether it can reach Rs 1 to 3 crore investors.', linkedin: '' }),
        agency({ dateAdded: '06 Nov 2026', name: 'Digital Punch', type: 'Lead generation agency', website: 'https://digitalpunch.in', phone: '', email: 'go@digitalpunch.in', city: 'New Delhi', leadsOnly: 'Yes', services: 'Lead packages from Google, Facebook, Instagram and LinkedIn campaigns.', pricing: 'Rs 1.5 lakh for 100 leads', sourceUrl: 'https://digitalpunch.in/franchise-leads/', status: 'New', notes: 'Exclusivity not stated.', linkedin: '' }),
      ],
    },
  };
}
