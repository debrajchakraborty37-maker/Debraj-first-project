import 'package:material_ui/material_ui.dart';
import 'package:provider/provider.dart';
import '../state/app_state.dart';
import '../widgets/common.dart';
import 'agencies_screen.dart';
import 'dashboard_screen.dart';
import 'leads_screen.dart';
import 'log_screen.dart';
import 'triage_screen.dart';

class HomeShell extends StatefulWidget {
  const HomeShell({super.key});
  @override
  State<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends State<HomeShell> {
  int _tab = 0;
  static const _pages = <Widget>[DashboardScreen(), TriageScreen(), LeadsScreen(), AgenciesScreen(), LogScreen()];

  @override
  Widget build(BuildContext context) {
    final s = context.watch<AppState>();
    return Scaffold(
      body: SafeArea(
        child: Column(children: [
          if (s.error != null) ErrorBanner(s.error!, onClose: s.clearError),
          Expanded(child: IndexedStack(index: _tab, children: _pages)),
        ]),
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _tab,
        onDestinationSelected: (i) => setState(() => _tab = i),
        destinations: [
          const NavigationDestination(icon: Icon(Icons.dashboard_outlined), selectedIcon: Icon(Icons.dashboard), label: 'Dashboard'),
          NavigationDestination(
            icon: Badge(isLabelVisible: s.triageQueue.isNotEmpty, label: Text('${s.triageQueue.length}'), child: const Icon(Icons.swipe_outlined)),
            selectedIcon: const Icon(Icons.swipe), label: 'Triage'),
          const NavigationDestination(icon: Icon(Icons.groups_outlined), selectedIcon: Icon(Icons.groups), label: 'Leads'),
          const NavigationDestination(icon: Icon(Icons.business_outlined), selectedIcon: Icon(Icons.business), label: 'Agencies'),
          const NavigationDestination(icon: Icon(Icons.history), selectedIcon: Icon(Icons.history), label: 'Log'),
        ],
      ),
    );
  }
}
