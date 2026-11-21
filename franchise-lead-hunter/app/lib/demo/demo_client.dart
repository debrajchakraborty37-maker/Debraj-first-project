import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

/// Demo mode (build with --dart-define=DEMO=true): the real app UI running on sample data, no server needed.
/// Nothing is saved anywhere; a refresh resets it. Sign in with demo@leadhunter.app / demo.
const demoEmail = 'demo@leadhunter.app', demoPassword = 'demo';

http.Client demoClient() {
  final leads = <Map<String, dynamic>>[
    _lead('L-1', 'Name not shown (Owner, food and beverages, real estate)', 'Cafe / F&B', 'Bangalore', 'Owner, food and beverages, real estate', 5, 'Hot', 'New', '06 Nov 2026'),
    _lead('L-2', 'Name not shown (Senior Manager, insurance agency)', 'Beauty and wellness, gyms (FOCO)', 'Delhi', 'Senior Manager, insurance agency', 1.8, 'Hot', 'New', '06 Nov 2026'),
    _lead('L-3', 'Name not shown (Owner, electronics and furniture retail)', 'Cafe / F&B (cafes, hotels)', 'Badnawar, Madhya Pradesh', 'Owner, electronics and furniture retail', 3, 'Warm', 'Meeting', '06 Nov 2026', followUp: '14 Nov 2026'),
    _lead('L-4', 'Name not shown (Director, hospitality)', 'Cafe / F&B', 'Madhya Pradesh', 'Director, hospitality', 1, 'Warm', 'New', '06 Nov 2026'),
    _lead('L-5', 'Name not shown (GM HR and Operations, restaurant franchisee)', 'Cafe / F&B (fast food)', 'New Delhi', 'General Manager, HR and Operations', 1, 'Warm', 'Contacted', '06 Nov 2026', followUp: '12 Nov 2026'),
  ];
  final agencies = <Map<String, dynamic>>[
    _agency('A-1', 'Franchise India', 'Franchise portal and consultancy', 'Faridabad, Haryana', 'Unclear', 'Not public', '0129-4244444', 'feedback@franchiseindia.in', 'https://www.franchiseindia.com'),
    _agency('A-2', 'Franchise Voice', 'Franchise portal', 'Noida, Uttar Pradesh', 'Yes', 'Pay-per-lead or monthly plans', '', '', 'https://franchisevoice.com'),
    _agency('A-3', 'Interskale', 'Lead generation agency', 'Mumbai', 'Yes', 'From about Rs 1 lakh, 3-month minimum', '+91-8369509606', 'info@interskale.in', 'https://www.interskale.in'),
    _agency('A-4', 'Digital Punch', 'Lead generation agency', 'New Delhi', 'Yes', 'Rs 1.5 lakh for 100 leads', '', 'go@digitalpunch.in', 'https://digitalpunch.in'),
  ];
  final runs = <Map<String, dynamic>>[
    {'id': 'R-1', 'startedAt': '13 Nov 2026 14:00', 'trigger': 'schedule', 'by': 'scheduler', 'queries': 9, 'found': 42, 'saved': 4, 'duplicates': 30, 'filtered': 8, 'errors': 0, 'notes': ''},
    {'id': 'R-0', 'startedAt': '13 Nov 2026 13:00', 'trigger': 'schedule', 'by': 'scheduler', 'queries': 9, 'found': 38, 'saved': 0, 'duplicates': 34, 'filtered': 4, 'errors': 1, 'notes': 'One page did not load. Retrying next run.'},
  ];
  var rules = <String, dynamic>{
    'brands': ['Cafe / F&B', 'Beauty and wellness', 'Gyms'], 'cities': ['Delhi', 'Bangalore', 'Mumbai'],
    'hniMinCr': 1, 'maxBudgetCr': 25, 'schedule': 'hourly', 'maxQueriesPerRun': 12, 'monthlyQueryCap': 2000,
  };
  var hunted = false;

  http.Response ok(Object o, [int code = 200]) =>
      http.Response.bytes(utf8.encode(jsonEncode(o)), code, headers: {'content-type': 'application/json; charset=utf-8'});

  Map<String, int> count(Iterable<Map<String, dynamic>> xs, String k) {
    final m = <String, int>{};
    for (final x in xs) { final v = (x[k] ?? '').toString(); m[v.isEmpty ? 'Not set' : v] = (m[v.isEmpty ? 'Not set' : v] ?? 0) + 1; }
    return m;
  }

  Map<String, dynamic> dashboard() {
    final open = leads.where((l) => !['Won', 'Lost', 'Skipped'].contains(l['status']));
    final cities = count(leads, 'city').entries.toList()..sort((a, b) => b.value.compareTo(a.value));
    return {
      'leads': {
        'total': leads.length, 'hniB2b': leads.length, 'newCount': leads.where((l) => l['status'] == 'New').length,
        'hot': leads.where((l) => l['quality'] == 'Hot').length, 'followUpsDue': 1,
        'pipelineValueCr': open.fold<double>(0, (s, l) => s + (l['budgetCr'] as num)),
        'byQuality': count(leads, 'quality'), 'byStatus': count(leads, 'status'),
        'topCities': [for (final e in cities.take(5)) {'name': e.key, 'count': e.value}], 'topBrands': [],
      },
      'agencies': {
        'total': agencies.length, 'leadsOnly': agencies.where((a) => a['leadsOnly'] == 'Yes').length,
        'newCount': agencies.where((a) => a['status'] == 'New').length, 'byType': count(agencies, 'type'), 'byStatus': count(agencies, 'status'),
      },
      'hunt': {'lastRun': runs.first, 'schedule': rules['schedule'], 'queriesUsedThisMonth': 214, 'monthlyQueryCap': rules['monthlyQueryCap'], 'searchConfigured': true},
    };
  }

  return MockClient((req) async {
    final p = req.url.path;
    final body = req.body.isEmpty ? <String, dynamic>{} : jsonDecode(req.body) as Map<String, dynamic>;
    if (p == '/api/auth/login') {
      return body['email'] == demoEmail && body['password'] == demoPassword
          ? ok({'token': 'demo', 'user': {'email': demoEmail, 'name': 'Demo Admin', 'role': 'admin'}})
          : ok({'error': 'invalid_credentials'}, 401);
    }
    if (req.headers['Authorization'] != 'Bearer demo') return ok({'error': 'unauthorized'}, 401);
    if (p == '/api/auth/me') return ok({'user': {'email': demoEmail, 'name': 'Demo Admin', 'role': 'admin'}});
    if (p == '/api/dashboard') return ok(dashboard());
    if (p == '/api/leads') return ok({'total': leads.length, 'items': leads});
    if (p == '/api/agencies') return ok({'total': agencies.length, 'items': agencies});
    if (p == '/api/runs') return ok({'items': runs});
    if (p == '/api/rules') {
      if (req.method == 'PUT') rules = {...rules, ...body};
      return ok(rules);
    }
    if (p == '/api/hunt/run') {
      final run = <String, dynamic>{'id': 'R-${runs.length + 1}', 'startedAt': '13 Nov 2026 15:00', 'trigger': 'manual', 'by': demoEmail,
        'queries': 9, 'found': hunted ? 20 : 31, 'saved': hunted ? 0 : 2, 'duplicates': hunted ? 20 : 24, 'filtered': hunted ? 0 : 5, 'errors': 0, 'notes': ''};
      if (!hunted) {
        leads.add(_lead('L-6', 'Name not shown (Owner, logistics firm) (example)', 'Gyms (branded)', 'Pune', 'Owner, logistics', 2.5, 'Hot', 'New', '13 Nov 2026'));
        leads.add(_lead('L-7', 'Name not shown (Director, textile exports) (example)', 'Cafe / F&B', 'Surat', 'Director, textile exports', 1.2, 'Warm', 'New', '13 Nov 2026'));
      }
      hunted = true;
      runs.insert(0, run);
      await Future<void>.delayed(const Duration(milliseconds: 1200));
      return ok(run);
    }
    final m = RegExp(r'^/api/(leads|agencies)/([^/]+)$').firstMatch(p);
    if (m != null && req.method == 'PATCH') {
      final list = m.group(1) == 'leads' ? leads : agencies;
      final i = list.indexWhere((x) => x['id'] == m.group(2));
      if (i < 0) return ok({'error': 'not_found'}, 404);
      list[i] = {...list[i], ...body};
      return ok(list[i]);
    }
    if (p.startsWith('/api/export/')) return http.Response('Demo export\r\n', 200);
    return ok({'error': 'not_found'}, 404);
  });
}

Map<String, dynamic> _lead(String id, String name, String brand, String city, String prof, num bud, String q, String status, String date, {String followUp = ''}) => {
      'id': id, 'name': name, 'brand': brand, 'city': city, 'profession': prof, 'budgetCr': bud, 'quality': q, 'status': status,
      'segment': 'HNI B2B', 'source': 'Google search (SMERGERS investor profile)', 'sourceUrl': 'https://www.smergers.com/', 'dateReceived': date,
      'nextFollowUp': followUp, 'notes': 'Public profile, up to INR $bud crore. Contact details appear only after connecting on the source site.',
      'phone': '', 'email': '', 'owner': '',
    };

Map<String, dynamic> _agency(String id, String name, String type, String city, String leadsOnly, String pricing, String phone, String email, String web) => {
      'id': id, 'name': name, 'type': type, 'city': city, 'leadsOnly': leadsOnly, 'pricing': pricing, 'phone': phone, 'email': email,
      'website': web, 'services': 'Claims are from the agency\'s own site and are unverified.', 'sourceUrl': web, 'status': 'New', 'notes': '',
      'linkedin': '', 'owner': '', 'dateAdded': '06 Nov 2026',
    };
