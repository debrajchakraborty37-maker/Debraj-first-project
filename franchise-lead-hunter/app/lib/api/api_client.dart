import 'dart:convert';
import 'dart:typed_data';
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:http/http.dart' as http;
import '../config.dart';
import '../models.dart';
import 'jsonp_stub.dart' if (dart.library.js_interop) 'jsonp_web.dart';

class ApiException implements Exception {
  final int status;
  final String message;
  const ApiException(this.status, this.message);
  @override
  String toString() => message;
}

/// All server calls. Every call except login carries the bearer token; a 401 signs the user out.
class ApiClient {
  ApiClient({String? base, http.Client? client})
      : base = (base ?? kApiBaseUrl).replaceAll(RegExp(r'/+$'), ''),
        _http = client ?? http.Client();

  /// Server address. Can be changed from the sign-in screen.
  String base;
  final http.Client _http;

  /// A Google Apps Script web app (the Sheet as the server) speaks one POST address with an "action"; everything else is REST.
  bool get isSheetServer => RegExp(r'^(https://script\.google(usercontent)?\.com/|http://localhost:\d+/exec)').hasMatch(base);
  String? token;
  void Function()? onUnauthorized;

  Uri _uri(String path, [Map<String, String>? q]) => Uri.parse('$base$path').replace(queryParameters: q);

  Future<http.Response> _send(String method, String path,
      {Object? body, Map<String, String>? query, Duration timeout = const Duration(seconds: 25)}) async {
    if (isSheetServer) return _sendSheet(method, path, body: body, query: query, timeout: timeout);
    final headers = {
      'Content-Type': 'application/json',
      if (token != null) 'Authorization': 'Bearer $token',
    };
    final uri = _uri(path, query);
    try {
      final req = http.Request(method, uri)..headers.addAll(headers);
      if (body != null) req.body = jsonEncode(body);
      final res = await http.Response.fromStream(await _http.send(req).timeout(timeout));
      if (res.statusCode == 401 && path != '/api/auth/login') onUnauthorized?.call();
      if (res.statusCode >= 400) throw ApiException(res.statusCode, _message(res));
      return res;
    } on ApiException {
      rethrow;
    } catch (_) {
      throw const ApiException(0, 'Cannot reach the server. Check your connection and try again.');
    }
  }

  /// Translates the REST-style calls into the Sheet server's single "action" address.
  Future<http.Response> _sendSheet(String method, String path,
      {Object? body, Map<String, String>? query, required Duration timeout}) async {
    String action;
    Map<String, dynamic> args = {};
    final b = (body as Map<String, dynamic>?) ?? {};
    final id = path.split('/').last;
    if (path == '/api/auth/login') { action = 'login'; }
    else if (path == '/api/auth/me') { action = 'me'; }
    else if (path == '/api/dashboard') { action = 'dashboard'; }
    else if (path == '/api/leads') { action = 'leads'; args = {'all': query?['segment'] == 'all'}; }
    else if (path.startsWith('/api/leads/')) { action = 'patchLead'; args = {'id': id, 'changes': b}; }
    else if (path == '/api/agencies') { action = 'agencies'; }
    else if (path.startsWith('/api/agencies/')) { action = 'patchAgency'; args = {'id': id, 'changes': b}; }
    else if (path == '/api/runs') { action = 'runs'; }
    else if (path == '/api/hunt/run') { action = 'hunt'; }
    else if (path == '/api/rules') { action = method == 'PUT' ? 'saveRules' : 'rules'; if (method == 'PUT') args = {'changes': b}; }
    else if (path.startsWith('/api/export/')) { action = 'export'; args = {'kind': id.replaceAll('.csv', '')}; }
    else { throw const ApiException(404, 'Not found.'); }
    final payload = jsonEncode({
      'action': action,
      if (action == 'login') ...{'email': b['email'], 'password': b['password']} else if (token != null) 'token': token,
      if (args.isNotEmpty) 'args': args,
    });
    try {
      final res = await _sheetRoundTrip(payload, timeout);
      final Map<String, dynamic> j;
      try { j = jsonDecode(res) as Map<String, dynamic>; }
      catch (_) { throw const ApiException(0, 'The Sheet server did not answer correctly. Check the server address.'); }
      final status = (j['status'] as num?)?.toInt() ?? 500;
      if (status == 401 && action != 'login') onUnauthorized?.call();
      if (status >= 400) throw ApiException(status, _messageFor(status));
      final data = j['data'];
      if (action == 'export') return http.Response.bytes(utf8.encode((data as Map)['csv'] as String), 200);
      return http.Response(jsonEncode(data), 200);
    } on ApiException {
      rethrow;
    } catch (_) {
      throw ApiException(0, 'Cannot reach the Sheet server. Check the address ends in /exec, that the script is deployed for "Anyone", and your connection.');
    }
  }

  /// One round trip to the Sheet server, returned as JSON text. Retries once, because the script can be slow to wake up.
  Future<String> _sheetRoundTrip(String payload, Duration timeout) async {
    Object? last;
    for (var attempt = 0; attempt < 2; attempt++) {
      try {
        if (kIsWeb) {
          final enc = base64Url.encode(utf8.encode(payload));
          if (enc.length <= 6500) {
            return await jsonpGet(Uri.parse(base).replace(queryParameters: {'p': enc}), timeout);
          }
        }
        // Large requests (and phone apps) use POST. text/plain keeps it a "simple" request, so no CORS preflight.
        final req = http.Request('POST', Uri.parse(base))
          ..headers['Content-Type'] = 'text/plain;charset=utf-8'
          ..body = payload;
        if (!kIsWeb) req.followRedirects = false;
        var res = await http.Response.fromStream(await _http.send(req).timeout(timeout));
        for (var hops = 0; hops < 5 && const {301, 302, 303, 307, 308}.contains(res.statusCode); hops++) {
          final loc = res.headers['location'];
          if (loc == null) break;
          final get = http.Request('GET', Uri.parse(loc));
          if (!kIsWeb) get.followRedirects = false;
          res = await http.Response.fromStream(await _http.send(get).timeout(timeout));
        }
        return utf8.decode(res.bodyBytes);
      } catch (e) {
        last = e;
        if (attempt == 0) await Future<void>.delayed(const Duration(seconds: 2));
      }
    }
    throw last!;
  }

  String _message(http.Response r) => _messageFor(r.statusCode);

  String _messageFor(int status) {
    switch (status) {
      case 401: return 'Email or password is incorrect, or your session has ended.';
      case 403: return 'Only an admin can do that.';
      case 429: return 'Too many attempts. Wait a few minutes and try again.';
      case 400: return 'The server did not accept that change.';
      default: return 'The server had a problem ($status). Try again.';
    }
  }

  dynamic _json(http.Response r) => jsonDecode(utf8.decode(r.bodyBytes));

  Future<AppUser> login(String email, String password) async {
    final r = await _send('POST', '/api/auth/login', body: {'email': email, 'password': password});
    final j = _json(r) as Map<String, dynamic>;
    token = j['token'] as String;
    return AppUser.fromJson(j['user'] as Map<String, dynamic>);
  }

  Future<AppUser> me() async => AppUser.fromJson((_json(await _send('GET', '/api/auth/me')) as Map<String, dynamic>)['user']);

  Future<Dashboard> dashboard() async => Dashboard.fromJson(_json(await _send('GET', '/api/dashboard')) as Map<String, dynamic>);

  /// B2B HNI leads by default. [all] also returns leads below the HNI line.
  Future<List<Lead>> leads({bool all = false}) async {
    final r = await _send('GET', '/api/leads', query: {'limit': '500', if (all) 'segment': 'all'});
    return [for (final j in (_json(r)['items'] as List)) Lead.fromJson(j as Map<String, dynamic>)];
  }

  Future<Lead> patchLead(String id, Map<String, dynamic> changes) async =>
      Lead.fromJson(_json(await _send('PATCH', '/api/leads/$id', body: changes)) as Map<String, dynamic>);

  Future<List<Agency>> agencies() async {
    final r = await _send('GET', '/api/agencies');
    return [for (final j in (_json(r)['items'] as List)) Agency.fromJson(j as Map<String, dynamic>)];
  }

  Future<Agency> patchAgency(String id, Map<String, dynamic> changes) async =>
      Agency.fromJson(_json(await _send('PATCH', '/api/agencies/$id', body: changes)) as Map<String, dynamic>);

  Future<List<Run>> runs() async {
    final r = await _send('GET', '/api/runs');
    return [for (final j in (_json(r)['items'] as List)) Run.fromJson(j as Map<String, dynamic>)];
  }

  Future<Run> huntNow() async =>
      Run.fromJson(_json(await _send('POST', '/api/hunt/run', timeout: const Duration(minutes: 3))) as Map<String, dynamic>);

  Future<Rules> rules() async => Rules.fromJson(_json(await _send('GET', '/api/rules')) as Map<String, dynamic>);

  Future<Rules> saveRules(Map<String, dynamic> changes) async =>
      Rules.fromJson(_json(await _send('PUT', '/api/rules', body: changes)) as Map<String, dynamic>);

  Future<Uint8List> exportCsv(String kind) async => (await _send('GET', '/api/export/$kind.csv')).bodyBytes;
}
