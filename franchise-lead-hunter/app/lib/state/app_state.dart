import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:material_ui/material_ui.dart';
import '../api/api_client.dart';
import '../models.dart';

class AppState extends ChangeNotifier {
  AppState(this.api, {FlutterSecureStorage? storage, this.demo = false}) : _storage = storage ?? const FlutterSecureStorage() {
    api.onUnauthorized = () => logout(silent: false);
  }

  final ApiClient api;
  final bool demo; // demo build: nothing is stored on the device
  final FlutterSecureStorage _storage;
  static const _tokenKey = 'flh_token', _serverKey = 'flh_server';

  AppUser? user;
  bool booting = true, loading = false, hunting = false;
  String? error;
  ThemeMode themeMode = ThemeMode.dark;

  Dashboard? dashboard;
  List<Lead> leads = [];
  List<Agency> agencies = [];
  List<Run> runs = [];
  Rules? rules;
  bool showAllLeads = false; // false = B2B HNI only
  final List<_Swipe> _history = [];

  bool get signedIn => user != null;

  // ---- session ----
  String get serverUrl => api.base;

  /// Server address chosen on the sign-in screen (Cloud Run link or Google Apps Script link). HTTPS only.
  Future<String?> setServer(String url) async {
    final u = url.trim().replaceAll(RegExp(r'/+$'), '');
    final ok = RegExp(r'^https://[^\s/]+').hasMatch(u) || RegExp(r'^http://(localhost|127\.0\.0\.1|10\.0\.2\.2)(:\d+)?').hasMatch(u);
    if (!ok) return 'Enter an address that starts with https://';
    api.base = u;
    try { await _storage.write(key: _serverKey, value: u); } catch (_) {}
    notifyListeners();
    return null;
  }

  Future<void> restore() async {
    try {
      final saved = demo ? null : await _storage.read(key: _serverKey);
      if (saved != null && saved.isNotEmpty) api.base = saved;
    } catch (_) {}
    try {
      final t = demo ? null : await _storage.read(key: _tokenKey);
      if (t != null) {
        api.token = t;
        user = await api.me();
        await refreshAll();
      }
    } catch (_) {
      api.token = null;
      user = null;
    }
    booting = false;
    notifyListeners();
  }

  /// Returns an error message, or null on success.
  Future<String?> login(String email, String password) async {
    try {
      user = await api.login(email.trim(), password);
      if (!demo) { try { await _storage.write(key: _tokenKey, value: api.token); } catch (_) {} }
      await refreshAll();
      return null;
    } on ApiException catch (e) {
      return e.message;
    }
  }

  Future<void> logout({bool silent = true}) async {
    api.token = null;
    user = null;
    dashboard = null; leads = []; agencies = []; runs = []; rules = null; _history.clear();
    error = silent ? null : 'Your session ended. Sign in again.';
    try { await _storage.delete(key: _tokenKey); } catch (_) {}
    notifyListeners();
  }

  void clearError() { error = null; notifyListeners(); }

  void setThemeMode(ThemeMode m) { themeMode = m; notifyListeners(); }

  // ---- loading ----
  Future<void> refreshAll() async {
    loading = true; error = null; notifyListeners();
    try {
      final r = await Future.wait([
        api.dashboard(), api.leads(all: showAllLeads), api.agencies(), api.runs(), api.rules(),
      ]);
      dashboard = r[0] as Dashboard; leads = r[1] as List<Lead>; agencies = r[2] as List<Agency>;
      runs = r[3] as List<Run>; rules = r[4] as Rules;
    } on ApiException catch (e) {
      error = e.message;
    }
    loading = false; notifyListeners();
  }

  Future<void> setShowAll(bool v) async { showAllLeads = v; await refreshAll(); }

  // ---- triage: New leads, biggest budget first ----
  List<Lead> get triageQueue =>
      (leads.where((l) => l.status == 'New').toList()..sort((a, b) => (b.budgetCr ?? 0).compareTo(a.budgetCr ?? 0)));
  List<Lead> get keptLeads => leads.where((l) => l.status != 'New' && l.status != 'Skipped').toList();
  List<Lead> get skippedLeads => leads.where((l) => l.status == 'Skipped').toList();
  bool get canUndo => _history.isNotEmpty;

  Future<void> swipe(Lead l, {required bool keep}) async {
    _history.add(_Swipe(l.id, l.status));
    await setLeadStatus(l.id, keep ? 'Shortlisted' : 'Skipped', owner: keep ? user?.email : null);
  }

  Future<void> undo() async {
    if (_history.isEmpty) return;
    final s = _history.removeLast();
    await setLeadStatus(s.id, s.previousStatus);
  }

  // ---- lead / agency edits: update the screen at once, then save to the Sheet, roll back on failure ----
  Future<void> setLeadStatus(String id, String status, {String? owner}) =>
      _patchLead(id, {'status': status, if (owner != null) 'owner': owner});
  Future<void> setFollowUp(String id, String date) => _patchLead(id, {'nextFollowUp': date});
  Future<void> setLeadNotes(String id, String notes) => _patchLead(id, {'notes': notes});

  Future<void> _patchLead(String id, Map<String, dynamic> changes) async {
    final i = leads.indexWhere((l) => l.id == id);
    if (i < 0) return;
    final before = leads[i];
    leads[i] = _copyLead(before, changes);
    error = null; notifyListeners();
    try {
      leads[i] = await api.patchLead(id, changes);
    } on ApiException catch (e) {
      leads[i] = before; error = e.message;
    }
    notifyListeners();
  }

  Future<void> patchAgency(String id, Map<String, dynamic> changes) async {
    final i = agencies.indexWhere((a) => a.id == id);
    if (i < 0) return;
    final before = agencies[i];
    try {
      agencies[i] = await api.patchAgency(id, changes);
    } on ApiException catch (e) {
      agencies[i] = before; error = e.message;
    }
    notifyListeners();
  }

  // ---- hunt / rules ----
  Future<Run?> huntNow() async {
    hunting = true; error = null; notifyListeners();
    Run? run;
    try {
      run = await api.huntNow();
      await refreshAll();
    } on ApiException catch (e) {
      error = e.message;
    }
    hunting = false; notifyListeners();
    return run;
  }

  Future<String?> saveRules(Map<String, dynamic> changes) async {
    try {
      rules = await api.saveRules(changes);
      notifyListeners();
      return null;
    } on ApiException catch (e) {
      return e.message;
    }
  }

  Lead _copyLead(Lead l, Map<String, dynamic> c) => Lead(
        id: l.id, name: l.name, brand: l.brand, city: l.city, profession: l.profession,
        status: c['status'] as String? ?? l.status, quality: l.quality, segment: l.segment, source: l.source,
        sourceUrl: l.sourceUrl, notes: c['notes'] as String? ?? l.notes, phone: l.phone, email: l.email,
        dateReceived: l.dateReceived, nextFollowUp: c['nextFollowUp'] as String? ?? l.nextFollowUp,
        owner: c['owner'] as String? ?? l.owner, budgetCr: l.budgetCr,
      );
}

class _Swipe {
  final String id, previousStatus;
  _Swipe(this.id, this.previousStatus);
}
