String _s(dynamic v) => v == null ? '' : v.toString();

class Lead {
  final String id, name, brand, city, profession, status, quality, segment, source, sourceUrl, notes, phone, email,
      dateReceived, nextFollowUp, owner;
  final double? budgetCr;
  const Lead({
    required this.id, required this.name, required this.brand, required this.city, required this.profession,
    required this.status, required this.quality, required this.segment, required this.source, required this.sourceUrl,
    required this.notes, required this.phone, required this.email, required this.dateReceived, required this.nextFollowUp,
    required this.owner, required this.budgetCr,
  });
  factory Lead.fromJson(Map<String, dynamic> j) => Lead(
        id: _s(j['id']), name: _s(j['name']), brand: _s(j['brand']), city: _s(j['city']), profession: _s(j['profession']),
        status: _s(j['status']), quality: _s(j['quality']), segment: _s(j['segment']), source: _s(j['source']),
        sourceUrl: _s(j['sourceUrl']), notes: _s(j['notes']), phone: _s(j['phone']), email: _s(j['email']),
        dateReceived: _s(j['dateReceived']), nextFollowUp: _s(j['nextFollowUp']), owner: _s(j['owner']),
        budgetCr: j['budgetCr'] is num ? (j['budgetCr'] as num).toDouble() : null,
      );
  String get budgetText => budgetCr == null ? 'Not stated' : 'Rs ${_trim(budgetCr!)} cr';
}

class Agency {
  final String id, name, type, website, phone, email, city, leadsOnly, services, pricing, sourceUrl, status, notes,
      linkedin, owner, dateAdded;
  const Agency({
    required this.id, required this.name, required this.type, required this.website, required this.phone,
    required this.email, required this.city, required this.leadsOnly, required this.services, required this.pricing,
    required this.sourceUrl, required this.status, required this.notes, required this.linkedin, required this.owner,
    required this.dateAdded,
  });
  factory Agency.fromJson(Map<String, dynamic> j) => Agency(
        id: _s(j['id']), name: _s(j['name']), type: _s(j['type']), website: _s(j['website']), phone: _s(j['phone']),
        email: _s(j['email']), city: _s(j['city']), leadsOnly: _s(j['leadsOnly']), services: _s(j['services']),
        pricing: _s(j['pricing']), sourceUrl: _s(j['sourceUrl']), status: _s(j['status']), notes: _s(j['notes']),
        linkedin: _s(j['linkedin']), owner: _s(j['owner']), dateAdded: _s(j['dateAdded']),
      );
}

class Run {
  final String id, startedAt, trigger, by, notes;
  final int queries, found, saved, duplicates, filtered, errors;
  const Run({
    required this.id, required this.startedAt, required this.trigger, required this.by, required this.notes,
    required this.queries, required this.found, required this.saved, required this.duplicates, required this.filtered,
    required this.errors,
  });
  static int _i(dynamic v) => v is num ? v.toInt() : int.tryParse(_s(v)) ?? 0;
  factory Run.fromJson(Map<String, dynamic> j) => Run(
        id: _s(j['id']), startedAt: _s(j['startedAt']), trigger: _s(j['trigger']), by: _s(j['by']), notes: _s(j['notes']),
        queries: _i(j['queries']), found: _i(j['found']), saved: _i(j['saved']), duplicates: _i(j['duplicates']),
        filtered: _i(j['filtered']), errors: _i(j['errors']),
      );
  bool get isError => errors > 0;
}

class Dashboard {
  final int leadsTotal, hniB2b, newLeads, hot, followUpsDue, agenciesTotal, leadsOnlyAgencies, newAgencies,
      queriesUsed, monthlyCap;
  final double pipelineValueCr;
  final Map<String, int> byStatus, byQuality, byType;
  final List<MapEntry<String, int>> topCities, topBrands;
  final Run? lastRun;
  final String schedule;
  final bool searchConfigured;
  const Dashboard({
    required this.leadsTotal, required this.hniB2b, required this.newLeads, required this.hot, required this.followUpsDue,
    required this.agenciesTotal, required this.leadsOnlyAgencies, required this.newAgencies, required this.queriesUsed,
    required this.monthlyCap, required this.pipelineValueCr, required this.byStatus, required this.byQuality, required this.byType,
    required this.topCities, required this.topBrands, required this.lastRun, required this.schedule,
    required this.searchConfigured,
  });
  static Map<String, int> _m(dynamic v) =>
      {for (final e in ((v ?? {}) as Map).entries) e.key.toString(): (e.value as num).toInt()};
  static List<MapEntry<String, int>> _top(dynamic v) =>
      [for (final e in ((v ?? []) as List)) MapEntry(_s(e['name']), (e['count'] as num).toInt())];
  factory Dashboard.fromJson(Map<String, dynamic> j) {
    final l = j['leads'] as Map<String, dynamic>, a = j['agencies'] as Map<String, dynamic>, h = j['hunt'] as Map<String, dynamic>;
    return Dashboard(
      leadsTotal: (l['total'] as num).toInt(), hniB2b: (l['hniB2b'] as num).toInt(), newLeads: (l['newCount'] as num).toInt(),
      hot: (l['hot'] as num).toInt(), followUpsDue: (l['followUpsDue'] as num).toInt(),
      pipelineValueCr: (l['pipelineValueCr'] as num).toDouble(), byStatus: _m(l['byStatus']), byQuality: _m(l['byQuality']), byType: _m(a['byType']),
      topCities: _top(l['topCities']), topBrands: _top(l['topBrands']),
      agenciesTotal: (a['total'] as num).toInt(), leadsOnlyAgencies: (a['leadsOnly'] as num).toInt(),
      newAgencies: (a['newCount'] as num).toInt(),
      queriesUsed: (h['queriesUsedThisMonth'] as num).toInt(), monthlyCap: (h['monthlyQueryCap'] as num).toInt(),
      lastRun: h['lastRun'] == null ? null : Run.fromJson(h['lastRun'] as Map<String, dynamic>),
      schedule: _s(h['schedule']), searchConfigured: h['searchConfigured'] == true,
    );
  }
}

class Rules {
  final List<String> brands, cities;
  final double hniMinCr;
  final String schedule;
  final int monthlyQueryCap, maxQueriesPerRun;
  const Rules({required this.brands, required this.cities, required this.hniMinCr, required this.schedule,
      required this.monthlyQueryCap, required this.maxQueriesPerRun});
  factory Rules.fromJson(Map<String, dynamic> j) => Rules(
        brands: [for (final b in (j['brands'] as List)) b.toString()], cities: [for (final c in (j['cities'] as List)) c.toString()],
        hniMinCr: (j['hniMinCr'] as num).toDouble(), schedule: _s(j['schedule']),
        monthlyQueryCap: (j['monthlyQueryCap'] as num).toInt(), maxQueriesPerRun: (j['maxQueriesPerRun'] as num).toInt(),
      );
}

class AppUser {
  final String email, name, role;
  const AppUser(this.email, this.name, this.role);
  factory AppUser.fromJson(Map<String, dynamic> j) => AppUser(_s(j['email']), _s(j['name']), _s(j['role']));
  bool get isAdmin => role == 'admin';
  bool get isOpenAccess => email == 'open-access';
}

String _trim(double v) => v == v.roundToDouble() ? v.toInt().toString() : v.toString();

const leadStatuses = ['New', 'Shortlisted', 'Contacted', 'Meeting', 'Negotiation', 'Won', 'Lost', 'Skipped'];

const _months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
String formatDate(DateTime d) => '${d.day.toString().padLeft(2, '0')} ${_months[d.month - 1]} ${d.year}';
