import 'dart:typed_data';
import 'package:material_ui/material_ui.dart';
import 'package:path_provider/path_provider.dart';
import 'package:provider/provider.dart';
import 'package:share_plus/share_plus.dart';
import '../models.dart';
import '../state/app_state.dart';
import '../theme.dart';
import '../widgets/common.dart';

class LogScreen extends StatelessWidget {
  const LogScreen({super.key});

  Future<void> _export(BuildContext context, AppState s, String kind) async {
    try {
      final Uint8List bytes = await s.api.exportCsv(kind);
      final dir = await getTemporaryDirectory();
      final path = '${dir.path}/$kind-${formatDate(DateTime.now()).replaceAll(' ', '-')}.csv';
      await XFile.fromData(bytes, mimeType: 'text/csv', name: '$kind.csv').saveTo(path);
      await SharePlus.instance.share(ShareParams(files: [XFile(path, mimeType: 'text/csv')], subject: 'Franchise Lead Hunter: $kind'));
    } catch (_) {
      if (context.mounted) toast(context, 'Could not export. Try again.');
    }
  }

  @override
  Widget build(BuildContext context) {
    final s = context.watch<AppState>();
    final c = FlhColors.of(context);
    return RefreshIndicator(
      onRefresh: s.refreshAll,
      child: ListView(padding: const EdgeInsets.fromLTRB(16, 12, 16, 24), children: [
        const Text('Sync and runs', style: TextStyle(fontSize: 26, fontWeight: FontWeight.w800)),
        const SizedBox(height: 10),
        FlhCard(tint: true, child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text('Google Sheet is the master copy', style: TextStyle(fontWeight: FontWeight.w700, color: c.ink)),
          const SizedBox(height: 2),
          Text('Leads ${s.dashboard?.leadsTotal ?? 0} · Agencies ${s.dashboard?.agenciesTotal ?? 0} · changes save to the Sheet at once',
              style: TextStyle(fontSize: 13, color: c.ink)),
        ])),
        const SizedBox(height: 10),
        FilledButton(
          style: FilledButton.styleFrom(backgroundColor: c.accent, foregroundColor: c.onAccent, padding: const EdgeInsets.symmetric(vertical: 14)),
          onPressed: s.hunting ? null : () async {
            final run = await s.huntNow();
            if (run != null && context.mounted) toast(context, 'Hunt finished: ${run.saved} saved');
          },
          child: Text(s.hunting ? 'Hunting…' : 'Hunt now', style: const TextStyle(fontWeight: FontWeight.w700)),
        ),
        const SectionLabel('Recent runs'),
        if (s.runs.isEmpty) const Muted('No runs yet. Tap Hunt now.', size: 14),
        for (final r in s.runs.take(15)) Padding(
          padding: const EdgeInsets.only(bottom: 10),
          child: FlhCard(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text('${r.startedAt} · ${r.trigger}', style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 13)),
            Muted('Found ${r.found} · Saved ${r.saved} · Duplicates ${r.duplicates} · Filtered ${r.filtered} · Queries ${r.queries}'),
            if (r.notes.isNotEmpty) Padding(padding: const EdgeInsets.only(top: 2),
                child: Text(r.notes, style: TextStyle(fontSize: 12, color: r.isError ? c.hot : c.muted))),
          ])),
        ),
        const SectionLabel('Export a copy'),
        Row(children: [
          Expanded(child: OutlinedButton(onPressed: () => _export(context, s, 'leads'), child: const Text('Leads CSV'))),
          const SizedBox(width: 8),
          Expanded(child: OutlinedButton(onPressed: () => _export(context, s, 'agencies'), child: const Text('Agencies CSV'))),
        ]),
        if (s.user?.isAdmin == true) ...[
          const SectionLabel('Hunt rules (admin)'),
          FlhCard(onTap: () => _editRules(context, s), child: Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
            Expanded(child: Text(s.rules == null ? 'Loading…' : '${s.rules!.schedule} · ${s.rules!.cities.join(', ')} · HNI from Rs ${s.rules!.hniMinCr} cr',
                style: const TextStyle(fontSize: 13))),
            const Icon(Icons.edit_outlined, size: 18),
          ])),
        ],
        const SectionLabel('Account'),
        FlhCard(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(s.user?.name ?? '', style: const TextStyle(fontWeight: FontWeight.w700)),
          Muted('${s.user?.email ?? ''} · ${s.user?.role ?? ''}'),
          const SizedBox(height: 10),
          Row(children: [
            ChoiceChip(label: const Text('Dark'), selected: s.themeMode == ThemeMode.dark, showCheckmark: false, onSelected: (_) => s.setThemeMode(ThemeMode.dark)),
            const SizedBox(width: 8),
            ChoiceChip(label: const Text('Light'), selected: s.themeMode == ThemeMode.light, showCheckmark: false, onSelected: (_) => s.setThemeMode(ThemeMode.light)),
            const Spacer(),
            TextButton(onPressed: () => s.logout(), child: const Text('Sign out')),
          ]),
        ])),
      ]),
    );
  }

  Future<void> _editRules(BuildContext context, AppState s) async {
    final r = s.rules;
    if (r == null) return;
    final brands = TextEditingController(text: r.brands.join(', '));
    final cities = TextEditingController(text: r.cities.join(', '));
    final hni = TextEditingController(text: '${r.hniMinCr}');
    final cap = TextEditingController(text: '${r.monthlyQueryCap}');
    var schedule = r.schedule;
    final ok = await showModalBottomSheet<bool>(
      context: context, isScrollControlled: true,
      builder: (ctx) => StatefulBuilder(builder: (ctx, set) => Padding(
        padding: EdgeInsets.fromLTRB(16, 16, 16, MediaQuery.viewInsetsOf(ctx).bottom + 16),
        child: SingleChildScrollView(child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Text('Hunt rules', style: TextStyle(fontSize: 20, fontWeight: FontWeight.w800)),
          const SizedBox(height: 12),
          TextField(controller: brands, decoration: const InputDecoration(labelText: 'Brands (comma separated)')),
          const SizedBox(height: 10),
          TextField(controller: cities, decoration: const InputDecoration(labelText: 'Cities (comma separated)')),
          const SizedBox(height: 10),
          TextField(controller: hni, keyboardType: const TextInputType.numberWithOptions(decimal: true), decoration: const InputDecoration(labelText: 'HNI line (Rs crore)')),
          const SizedBox(height: 10),
          TextField(controller: cap, keyboardType: TextInputType.number, decoration: const InputDecoration(labelText: 'Monthly search budget (queries)')),
          const SectionLabel('Schedule'),
          ChipChoices(options: const ['hourly', 'every3h', 'daily', 'off'], value: schedule, onChanged: (v) => set(() => schedule = v)),
          const SizedBox(height: 16),
          SizedBox(width: double.infinity, child: FilledButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Save rules'))),
        ])),
      )),
    );
    List<String> split(String t) => [for (final p in t.split(',')) if (p.trim().isNotEmpty) p.trim()];
    if (ok == true) {
      final err = await s.saveRules({
        'brands': split(brands.text), 'cities': split(cities.text), 'schedule': schedule,
        'hniMinCr': double.tryParse(hni.text) ?? r.hniMinCr, 'monthlyQueryCap': int.tryParse(cap.text) ?? r.monthlyQueryCap,
      });
      if (context.mounted) toast(context, err ?? 'Rules saved to the Sheet');
    }
    for (final c in [brands, cities, hni, cap]) { c.dispose(); }
  }
}
