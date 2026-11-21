import 'package:material_ui/material_ui.dart';
import 'package:provider/provider.dart';
import '../models.dart';
import '../state/app_state.dart';
import '../theme.dart';
import '../widgets/common.dart';

class DashboardScreen extends StatelessWidget {
  const DashboardScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final s = context.watch<AppState>();
    final d = s.dashboard;
    return RefreshIndicator(
      onRefresh: s.refreshAll,
      child: ListView(padding: const EdgeInsets.fromLTRB(16, 12, 16, 24), children: [
        Row(children: [
          const Expanded(child: Text('Dashboard', style: TextStyle(fontSize: 26, fontWeight: FontWeight.w800))),
          Muted(s.user?.name ?? ''),
        ]),
        const SizedBox(height: 4),
        const Muted('B2B HNI leads and agencies, live from your Google Sheet'),
        if (d == null) Padding(
          padding: const EdgeInsets.all(48),
          child: Center(child: s.loading ? const CircularProgressIndicator() : const Muted('Pull down to load.')),
        ) else ..._body(context, s, d),
      ]),
    );
  }

  List<Widget> _body(BuildContext context, AppState s, Dashboard d) {
    final c = FlhColors.of(context);
    return [
      const SectionLabel('Leads'),
      _Grid(children: [
        _Kpi('New', '${d.newLeads}', 'waiting in Triage', c.accent),
        _Kpi('HNI B2B', '${d.hniB2b}', 'of ${d.leadsTotal} in the Sheet', c.ink),
        _Kpi('Hot', '${d.hot}', 'best matches', c.hot),
        _Kpi('Follow-ups due', '${d.followUpsDue}', 'today or overdue', d.followUpsDue > 0 ? c.hot : c.ink),
      ]),
      const SizedBox(height: 10),
      FlhCard(child: Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
        const Muted('Pipeline value (HNI B2B, open)', size: 13),
        Text('Rs ${_n(d.pipelineValueCr)} cr', style: kMono.copyWith(fontSize: 18, fontWeight: FontWeight.w700, color: c.accent)),
      ])),
      const SectionLabel('Leads by status'),
      _Bars(entries: [for (final st in leadStatuses) if ((d.byStatus[st] ?? 0) > 0) MapEntry(st, d.byStatus[st]!)]),
      const SectionLabel('Top cities'),
      _Bars(entries: d.topCities),
      const SectionLabel('Agencies'),
      _Grid(children: [
        _Kpi('Total', '${d.agenciesTotal}', 'in the Sheet', c.ink),
        _Kpi('Leads only', '${d.leadsOnlyAgencies}', 'lead generation', c.brand),
        _Kpi('New', '${d.newAgencies}', 'not yet reviewed', c.accent),
      ]),
      const SectionLabel('Agencies by type'),
      _Bars(entries: d.byType.entries.toList()..sort((a, b) => b.value.compareTo(a.value))),
      const SectionLabel('Hunt'),
      FlhCard(tint: true, child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(d.lastRun == null ? 'No hunt has run yet' : 'Last hunt ${d.lastRun!.startedAt}',
            style: TextStyle(fontWeight: FontWeight.w700, color: c.ink)),
        const SizedBox(height: 4),
        Text(d.lastRun == null ? 'Schedule: ${d.schedule}' : 'Found ${d.lastRun!.found} · Saved ${d.lastRun!.saved} · Duplicates ${d.lastRun!.duplicates}',
            style: TextStyle(color: c.ink, fontSize: 13)),
        const SizedBox(height: 10),
        LinearProgressIndicator(value: d.monthlyCap == 0 ? 1 : (d.queriesUsed / d.monthlyCap).clamp(0, 1).toDouble(), minHeight: 6,
            borderRadius: BorderRadius.circular(3)),
        const SizedBox(height: 4),
        Text('Search budget: ${d.queriesUsed} of ${d.monthlyCap} queries this month', style: TextStyle(color: c.ink, fontSize: 12)),
        if (!d.searchConfigured) Padding(
          padding: const EdgeInsets.only(top: 6),
          child: Text('Google Search is not set up on the server yet.', style: TextStyle(color: c.hot, fontSize: 12, fontWeight: FontWeight.w600)),
        ),
        const SizedBox(height: 10),
        FilledButton(
          onPressed: s.hunting ? null : () async {
            final run = await s.huntNow();
            if (run != null && context.mounted) toast(context, 'Hunt finished: ${run.saved} saved, ${run.duplicates} duplicates');
          },
          child: Text(s.hunting ? 'Hunting…' : 'Hunt now'),
        ),
      ])),
    ];
  }

  static String _n(double v) => v == v.roundToDouble() ? v.toInt().toString() : v.toStringAsFixed(1);
}

class _Grid extends StatelessWidget {
  const _Grid({required this.children});
  final List<Widget> children;
  @override
  Widget build(BuildContext context) => LayoutBuilder(builder: (context, box) {
        final cols = box.maxWidth > 560 ? children.length.clamp(1, 4) : 2;
        final w = (box.maxWidth - 10 * (cols - 1)) / cols;
        return Wrap(spacing: 10, runSpacing: 10, children: [for (final k in children) SizedBox(width: w, child: k)]);
      });
}

class _Kpi extends StatelessWidget {
  const _Kpi(this.label, this.value, this.hint, this.color);
  final String label, value, hint;
  final Color color;
  @override
  Widget build(BuildContext context) => FlhCard(
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Muted(label, size: 12),
          const SizedBox(height: 2),
          Text(value, style: kMono.copyWith(fontSize: 28, fontWeight: FontWeight.w700, color: color)),
          Muted(hint, size: 11),
        ]),
      );
}

class _Bars extends StatelessWidget {
  const _Bars({required this.entries});
  final List<MapEntry<String, int>> entries;
  @override
  Widget build(BuildContext context) {
    final c = FlhColors.of(context);
    if (entries.isEmpty) return const FlhCard(child: Muted('Nothing to show yet.'));
    final max = entries.map((e) => e.value).reduce((a, b) => a > b ? a : b);
    return FlhCard(child: Column(children: [
      for (final e in entries) Padding(
        padding: const EdgeInsets.symmetric(vertical: 4),
        child: Row(children: [
          SizedBox(width: 104, child: Text(e.key, maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 13))),
          Expanded(child: LayoutBuilder(builder: (context, box) => Align(
            alignment: Alignment.centerLeft,
            child: Container(height: 10, width: box.maxWidth * e.value / max,
                decoration: BoxDecoration(color: c.brand, borderRadius: BorderRadius.circular(5))),
          ))),
          SizedBox(width: 32, child: Text('${e.value}', textAlign: TextAlign.end, style: kMono.copyWith(fontSize: 13, fontWeight: FontWeight.w700))),
        ]),
      ),
    ]));
  }
}
