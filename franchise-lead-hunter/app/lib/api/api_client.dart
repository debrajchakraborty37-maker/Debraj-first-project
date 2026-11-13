import 'dart:convert';
import 'dart:typed_data';
import 'package:http/http.dart' as http;
import '../config.dart';
import '../models.dart';

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

  final String base;
  final http.Client _http;
  String? token;
  void Function()? onUnauthorized;

  Uri _uri(String path, [Map<String, String>? q]) => Uri.parse('$base$path').replace(queryParameters: q);

  Future<http.Response> _send(String method, String path,
      {Object? body, Map<String, String>? query, Duration timeout = const Duration(seconds: 25)}) async {
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

  String _message(http.Response r) {
    switch (r.statusCode) {
      case 401: return 'Email or password is incorrect, or your session has ended.';
      case 403: return 'Only an admin can do that.';
      case 429: return 'Too many attempts. Wait a few minutes and try again.';
      case 400: return 'The server did not accept that change.';
      default: return 'The server had a problem (${r.statusCode}). Try again.';
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
