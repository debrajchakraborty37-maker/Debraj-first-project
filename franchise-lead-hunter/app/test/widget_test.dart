import 'dart:convert';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:material_ui/material_ui.dart';
import 'package:http/testing.dart';
import 'package:lead_hunter/api/api_client.dart';
import 'package:lead_hunter/main.dart';
import 'package:lead_hunter/state/app_state.dart';
import 'package:provider/provider.dart';

class _MemStorage extends FlutterSecureStorage {
  final Map<String, String> m = {};
  @override
  Future<String?> read({required String key, AppleOptions? iOptions, AndroidOptions? aOptions, LinuxOptions? lOptions, WebOptions? webOptions, AppleOptions? mOptions, WindowsOptions? wOptions}) async => m[key];
  @override
  Future<void> write({required String key, required String? value, AppleOptions? iOptions, AndroidOptions? aOptions, LinuxOptions? lOptions, WebOptions? webOptions, AppleOptions? mOptions, WindowsOptions? wOptions}) async { m[key] = value ?? ''; }
  @override
  Future<void> delete({required String key, AppleOptions? iOptions, AndroidOptions? aOptions, LinuxOptions? lOptions, WebOptions? webOptions, AppleOptions? mOptions, WindowsOptions? wOptions}) async { m.remove(key); }
}

http.Response _json(Object o, [int code = 200]) =>
    http.Response(jsonEncode(o), code, headers: {'content-type': 'application/json'});

MockClient _server({required String goodPassword}) => MockClient((req) async {
      final p = req.url.path;
      if (p == '/api/auth/login') {
        final b = jsonDecode(req.body) as Map;
        return b['password'] == goodPassword
            ? _json({'token': 't', 'user': {'email': 'a@b.com', 'name': 'Admin', 'role': 'admin'}})
            : _json({'error': 'invalid_credentials'}, 401);
      }
      if (req.headers['Authorization'] != 'Bearer t') return _json({'error': 'unauthorized'}, 401);
      switch (p) {
        case '/api/dashboard':
          return _json({
            'leads': {'total': 5, 'hniB2b': 4, 'newCount': 2, 'hot': 1, 'followUpsDue': 1, 'pipelineValueCr': 10.8,
              'byQuality': {'Warm': 4}, 'byStatus': {'New': 2, 'Meeting': 1}, 'topCities': [{'name': 'Delhi', 'count': 2}], 'topBrands': []},
            'agencies': {'total': 3, 'leadsOnly': 2, 'newCount': 3, 'byType': {'Lead generation agency': 2}, 'byStatus': {'New': 3}},
            'hunt': {'lastRun': null, 'schedule': 'hourly', 'queriesUsedThisMonth': 4, 'monthlyQueryCap': 2000, 'searchConfigured': true},
          });
        case '/api/leads':
          return _json({'total': 1, 'items': [
            {'id': 'L-1', 'name': 'Owner, cafe chain', 'brand': 'Cafe / F&B', 'city': 'Pune', 'profession': 'Owner', 'status': 'New',
              'quality': 'Hot', 'segment': 'HNI B2B', 'budgetCr': 5, 'source': 'Google', 'sourceUrl': '', 'notes': '', 'phone': '', 'email': '',
              'dateReceived': '06 Nov 2026', 'nextFollowUp': '', 'owner': ''},
          ]});
        case '/api/agencies':
          return _json({'total': 0, 'items': []});
        case '/api/runs':
          return _json({'items': []});
        case '/api/rules':
          return _json({'brands': ['Cafe'], 'cities': ['Pune'], 'hniMinCr': 1, 'schedule': 'hourly', 'monthlyQueryCap': 2000, 'maxQueriesPerRun': 12});
      }
      return _json({'error': 'not_found'}, 404);
    });

Future<void> _pump(WidgetTester t, MockClient client) async {
  final state = AppState(ApiClient(base: 'https://api.test', client: client), storage: _MemStorage());
  await state.restore();
  await t.pumpWidget(ChangeNotifierProvider.value(value: state, child: const LeadHunterApp()));
  await t.pumpAndSettle();
}

void main() {
  sheetServerTests();
  testWidgets('shows the sign-in screen first', (t) async {
    await _pump(t, _server(goodPassword: 'pw'));
    expect(find.text('Sign in'), findsOneWidget);
    expect(find.text('Dashboard'), findsNothing);
  });

  testWidgets('wrong password shows an error and stays signed out', (t) async {
    await _pump(t, _server(goodPassword: 'pw'));
    await t.enterText(find.byType(TextField).at(0), 'a@b.com');
    await t.enterText(find.byType(TextField).at(1), 'wrong');
    await t.tap(find.text('Sign in'));
    await t.pumpAndSettle();
    expect(find.textContaining('incorrect'), findsOneWidget);
    expect(find.text('Dashboard'), findsNothing);
  });

  testWidgets('sign in opens the dashboard with Leads and Agencies numbers', (t) async {
    await _pump(t, _server(goodPassword: 'pw'));
    await t.enterText(find.byType(TextField).at(0), 'a@b.com');
    await t.enterText(find.byType(TextField).at(1), 'pw');
    await t.tap(find.text('Sign in'));
    await t.pumpAndSettle();
    expect(find.text('Dashboard'), findsWidgets);
    expect(find.text('HNI B2B'), findsOneWidget);
    expect(find.text('Rs 10.8 cr'), findsOneWidget);
    await t.tap(find.text('Triage').last);
    await t.pumpAndSettle();
    expect(find.text('Owner, cafe chain'), findsOneWidget);
    expect(find.text('Keep'), findsOneWidget);
  });
}

// ---- Sheet-as-server mode: one POST address, replies like Google Apps Script (302 to a result address) ----
void sheetServerTests() {
  const exec = 'https://script.google.com/macros/s/ABC/exec';
  MockClient sheetServer() => MockClient((req) async {
        if (req.method == 'POST') {
          expect(req.headers['Content-Type'], startsWith('text/plain')); // no CORS preflight in browsers
          return http.Response('', 302, headers: {'location': 'https://script.googleusercontent.com/macros/echo?k=1#${base64Url.encode(utf8.encode(req.body))}'});
        }
        final sent = jsonDecode(utf8.decode(base64Url.decode(base64Url.normalize(req.url.fragment)))) as Map<String, dynamic>;
        http.Response j(int status, [Object? data]) => http.Response(jsonEncode({'status': status, if (data != null) 'data': data}), 200);
        switch (sent['action']) {
          case 'login':
            return sent['password'] == 'pw' ? j(200, {'token': 't', 'user': {'email': 'a@b.com', 'name': 'Admin', 'role': 'admin'}}) : j(401);
          case 'leads':
            return sent['token'] == 't' ? j(200, {'total': 1, 'items': [{'id': 'L-1', 'name': 'Owner', 'budgetCr': 3, 'status': 'New'}]}) : j(401);
          case 'patchLead':
            return j(200, {'id': (sent['args'] as Map)['id'], 'name': 'Owner', 'status': ((sent['args'] as Map)['changes'] as Map)['status']});
          case 'export':
            return j(200, {'csv': 'a,b\r\n'});
        }
        return j(404);
      });

  test('sheet server: login, list, patch and export go through one address and follow the redirect', () async {
    final api = ApiClient(base: exec, client: sheetServer());
    expect(api.isSheetServer, isTrue);
    await expectLater(api.login('a@b.com', 'bad'), throwsA(isA<ApiException>()));
    final u = await api.login('a@b.com', 'pw');
    expect(u.isAdmin, isTrue);
    final leads = await api.leads();
    expect(leads.single.id, 'L-1');
    expect((await api.patchLead('L-1', {'status': 'Shortlisted'})).status, 'Shortlisted');
    expect(utf8.decode(await api.exportCsv('leads')), 'a,b\r\n');
  });

  test('a normal https address is not treated as a sheet server', () {
    expect(ApiClient(base: 'https://flh-server-abc.a.run.app', client: sheetServer()).isSheetServer, isFalse);
  });
}
