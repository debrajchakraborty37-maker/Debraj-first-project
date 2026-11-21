import 'package:material_ui/material_ui.dart';
import 'package:provider/provider.dart';
import '../state/app_state.dart';
import '../theme.dart';
import '../widgets/common.dart';
import '../models.dart';

class AgenciesScreen extends StatefulWidget {
  const AgenciesScreen({super.key});
  @override
  State<AgenciesScreen> createState() => _AgenciesScreenState();
}

class _AgenciesScreenState extends State<AgenciesScreen> {
  String _filter = 'All';

  @override
  Widget build(BuildContext context) {
    final s = context.watch<AppState>();
    final items = s.agencies.where((a) => _filter == 'All' || a.leadsOnly == 'Yes').toList();
    final c = FlhColors.of(context);
    return RefreshIndicator(
      onRefresh: s.refreshAll,
      child: ListView(padding: const EdgeInsets.fromLTRB(16, 12, 16, 24), children: [
        const Text('Agencies', style: TextStyle(fontSize: 26, fontWeight: FontWeight.w800)),
        const SizedBox(height: 10),
        ChipChoices(options: const ['All', 'Leads only'], value: _filter, onChanged: (v) => setState(() => _filter = v)),
        if (items.isEmpty) const Padding(padding: EdgeInsets.all(32), child: Center(child: Muted('No agencies yet.', size: 14))),
        for (final a in items) Padding(
          padding: const EdgeInsets.only(top: 10),
          child: FlhCard(
            onTap: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => AgencyDetailScreen(agencyId: a.id))),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
                Expanded(child: Text(a.name, style: const TextStyle(fontWeight: FontWeight.w700))),
                Muted(a.city.split(',').first),
              ]),
              Muted(a.type),
              const SizedBox(height: 8),
              Text(a.pricing.isEmpty ? 'Pricing not stated' : a.pricing, style: kMono.copyWith(fontSize: 13, fontWeight: FontWeight.w700, color: c.accent)),
            ]),
          ),
        ),
      ]),
    );
  }
}

class AgencyDetailScreen extends StatelessWidget {
  const AgencyDetailScreen({super.key, required this.agencyId});
  final String agencyId;

  @override
  Widget build(BuildContext context) {
    final s = context.watch<AppState>();
    final i = s.agencies.indexWhere((x) => x.id == agencyId);
    if (i < 0) return Scaffold(appBar: AppBar(), body: const Center(child: Muted('This agency is no longer in the list.', size: 14)));
    final a = s.agencies[i];
    return Scaffold(
      appBar: AppBar(title: const Text('Agency')),
      body: ListView(padding: const EdgeInsets.fromLTRB(16, 4, 16, 32), children: [
        Text(a.name, style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w800)),
        const SizedBox(height: 4),
        Muted(a.type, size: 14),
        const SizedBox(height: 12),
        FlhCard(child: Column(children: [
          FieldRow('City', a.city), FieldRow('Leads only', a.leadsOnly), FieldRow('Pricing', a.pricing),
          FieldRow('Phone', a.phone), FieldRow('Email', a.email), FieldRow('Website', a.website), FieldRow('Added', a.dateAdded),
        ])),
        const SectionLabel('Services and claims'),
        FlhCard(child: SizedBox(width: double.infinity, child: Text(a.services.isEmpty ? 'Not stated' : a.services, style: const TextStyle(fontSize: 14, height: 1.4)))),
        const Padding(padding: EdgeInsets.only(top: 6), child: Muted('Claims come from the agency\'s own site and are unverified.')),
        const SectionLabel('Status'),
        ChipChoices(options: leadStatuses, value: a.status, onChanged: (v) => s.patchAgency(a.id, {'status': v})),
        const SizedBox(height: 16),
        if (a.phone.isNotEmpty) Padding(padding: const EdgeInsets.only(bottom: 8),
            child: SizedBox(width: double.infinity, child: FilledButton(onPressed: () => openLink(context, a.phone, scheme: 'tel'), child: const Text('Call')))),
        if (a.email.isNotEmpty) Padding(padding: const EdgeInsets.only(bottom: 8),
            child: SizedBox(width: double.infinity, child: OutlinedButton(onPressed: () => openLink(context, a.email, scheme: 'mailto'), child: Text('Email ${a.email}')))),
        if (a.website.isNotEmpty) Padding(padding: const EdgeInsets.only(bottom: 8),
            child: SizedBox(width: double.infinity, child: OutlinedButton(onPressed: () => openLink(context, a.website), child: const Text('Open website')))),
        if (a.linkedin.startsWith('http')) SizedBox(width: double.infinity,
            child: OutlinedButton(onPressed: () => openLink(context, a.linkedin), child: const Text('Open LinkedIn'))),
      ]),
    );
  }
}
