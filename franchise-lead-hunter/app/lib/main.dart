import 'package:material_ui/material_ui.dart';
import 'package:provider/provider.dart';
import 'api/api_client.dart';
import 'config.dart';
import 'demo/demo_client.dart';
import 'screens/home_shell.dart';
import 'screens/login_screen.dart';
import 'state/app_state.dart';
import 'theme.dart';

void main() {
  runApp(ChangeNotifierProvider(
    create: (_) => AppState(kDemo ? ApiClient(base: 'https://demo.local', client: demoClient()) : ApiClient(), demo: kDemo)..restore(),
    child: const LeadHunterApp(),
  ));
}

class LeadHunterApp extends StatelessWidget {
  const LeadHunterApp({super.key});

  @override
  Widget build(BuildContext context) {
    final s = context.watch<AppState>();
    return MaterialApp(
      title: 'Franchise Lead Hunter',
      debugShowCheckedModeBanner: false,
      theme: buildTheme(Brightness.light),
      darkTheme: buildTheme(Brightness.dark),
      themeMode: s.themeMode,
      home: s.booting
          ? const Scaffold(body: Center(child: CircularProgressIndicator()))
          : s.signedIn ? const HomeShell() : const LoginScreen(),
    );
  }
}
