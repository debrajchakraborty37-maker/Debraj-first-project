import 'package:flutter/foundation.dart' show kIsWeb;

const String _apiBaseDefine = String.fromEnvironment('API_BASE_URL');

/// Server address.
/// - Phone apps (APK / iPhone): build with --dart-define=API_BASE_URL=https://your-service.run.app
/// - Web build served by the server itself: nothing to set, it uses the address it was opened from.
/// Release builds only talk to HTTPS addresses.
String get kApiBaseUrl =>
    _apiBaseDefine.isNotEmpty ? _apiBaseDefine : (kIsWeb ? Uri.base.origin : 'http://localhost:8080');

/// Demo build: sample data in the app itself, no server. flutter build web --dart-define=DEMO=true
const bool kDemo = bool.fromEnvironment('DEMO');
