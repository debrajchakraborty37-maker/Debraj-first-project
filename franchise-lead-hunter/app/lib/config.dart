/// Server address. Set at build time:
///   flutter run --dart-define=API_BASE_URL=https://your-server.example.com
/// Release builds only talk to HTTPS addresses.
const String kApiBaseUrl = String.fromEnvironment('API_BASE_URL', defaultValue: 'http://localhost:8080');

/// Demo build: sample data in the app itself, no server. flutter build web --dart-define=DEMO=true
const bool kDemo = bool.fromEnvironment('DEMO');
