import 'package:material_ui/material_ui.dart';
import 'package:provider/provider.dart';
import '../config.dart';
import '../demo/demo_client.dart';
import '../state/app_state.dart';
import '../theme.dart';
import '../widgets/common.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});
  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _email = TextEditingController(text: kDemo ? demoEmail : ''), _password = TextEditingController(text: kDemo ? demoPassword : '');
  final _server = TextEditingController();
  bool _busy = false, _show = false;
  String? _error;

  @override
  void dispose() { _email.dispose(); _password.dispose(); _server.dispose(); super.dispose(); }

  Future<void> _submit() async {
    if (_busy) return;
    setState(() { _busy = true; _error = null; });
    final state = context.read<AppState>();
    if (!kDemo && _server.text.trim().isNotEmpty && _server.text.trim() != state.serverUrl) {
      final bad = await state.setServer(_server.text);
      if (bad != null) { if (mounted) setState(() { _busy = false; _error = bad; }); return; }
    }
    final err = await state.login(_email.text, _password.text);
    if (!mounted) return;
    setState(() { _busy = false; _error = err; });
    if (err == null) _password.clear();
  }

  @override
  Widget build(BuildContext context) {
    final c = FlhColors.of(context);
    final session = context.watch<AppState>().error;
    return Scaffold(
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 400),
              child: AutofillGroup(
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text('Franchise\nLead Hunter', style: TextStyle(fontSize: 34, height: 1.05, fontWeight: FontWeight.w800, color: c.ink)),
                  const SizedBox(height: 8),
                  Muted(kDemo ? 'Demo with sample data. Nothing is saved. Just tap Sign in.' : 'Sign in with your team account.', size: 14),
                  const SizedBox(height: 28),
                  TextField(
                    controller: _email, keyboardType: TextInputType.emailAddress, autofillHints: const [AutofillHints.username],
                    autocorrect: false, enableSuggestions: false, textInputAction: TextInputAction.next,
                    decoration: const InputDecoration(labelText: 'Login ID'),
                  ),
                  const SizedBox(height: 14),
                  TextField(
                    controller: _password, obscureText: !_show, autofillHints: const [AutofillHints.password],
                    autocorrect: false, enableSuggestions: false, onSubmitted: (_) => _submit(),
                    decoration: InputDecoration(
                      labelText: 'Password',
                      suffixIcon: IconButton(
                        tooltip: _show ? 'Hide password' : 'Show password',
                        icon: Icon(_show ? Icons.visibility_off_outlined : Icons.visibility_outlined),
                        onPressed: () => setState(() => _show = !_show),
                      ),
                    ),
                  ),
                  if (_error != null || session != null) ...[
                    const SizedBox(height: 12),
                    Text(_error ?? session!, style: TextStyle(color: c.hot, fontWeight: FontWeight.w600)),
                  ],
                  if (!kDemo) Theme(
                    data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
                    child: ExpansionTile(
                      tilePadding: EdgeInsets.zero, title: const Muted('Server address (advanced)', size: 13),
                      children: [
                        TextField(
                          controller: _server, keyboardType: TextInputType.url, autocorrect: false, enableSuggestions: false,
                          decoration: InputDecoration(labelText: 'Server address', hintText: context.read<AppState>().serverUrl),
                        ),
                        const SizedBox(height: 4),
                        const Align(alignment: Alignment.centerLeft,
                            child: Muted('Paste your Google Apps Script or Cloud Run link once. It is remembered on this device.')),
                      ],
                    ),
                  ),
                  const SizedBox(height: 12),
                  SizedBox(
                    width: double.infinity,
                    child: FilledButton(
                      onPressed: _busy ? null : _submit,
                      style: FilledButton.styleFrom(padding: const EdgeInsets.symmetric(vertical: 16)),
                      child: Text(_busy ? 'Signing in…' : 'Sign in', style: const TextStyle(fontWeight: FontWeight.w700)),
                    ),
                  ),
                ]),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
