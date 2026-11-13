import 'package:material_ui/material_ui.dart';
import 'package:provider/provider.dart';
import '../models.dart';
import '../state/app_state.dart';
import '../theme.dart';
import '../widgets/common.dart';

class LeadsScreen extends StatefulWidget {
  const LeadsScreen({super.key});
  @override
  State<LeadsScreen> createState() => _LeadsScreenState();
}

class _LeadsScreenState extends State<LeadsScreen> {
  String _quality = 'All', _search = '';

  @override
  Widget build(BuildContext context) {
    final s = context.watch<AppState>();
    final needle = _search.toLowerCase();
    final items = s.leads.where((l) =>
        l.status != 'Skipped' &&
        (_quality == 'All' || l.quality == _quality) &&
        (needle.isEmpty || '${l.name} ${l.city} ${l.brand} ${l.profession}'.toLowerCase().contains(needle))).toList()
      ..sort((a, b) => (b.budgetCr ?? 0).compareTo(a.budgetCr ?? 0));
    return RefreshIndicator(
      onRefresh: s.refreshAll,
      child: ListView(padding: const EdgeInsets.fromLTRB(16, 12, 16, 24), children: [
        const Text('Leads', style: TextStyle(fontSize: 26, fontWeight: FontWeight.w800)),
        const SizedBox(height: 10),
        TextField(
          onChanged: (v) => setState(() => _search = v),
          decoration: const InputDecoration(hintText: 'Search city, brand or profile', prefixIcon: Icon(Icons.search)),
        ),
        const SizedBox(height: 10),
        ChipChoices(options: const ['All', 'Hot', 'Warm', 'Cold'], value: _quality, onChanged: (v) => setState(() => _quality = v)),
        const SizedBox(height: 6),
        SwitchListTile(
          contentPadding: EdgeInsets.zero, dense: true, title: const Text('B2B HNI only'),
          subtitle: const Muted('Budget at or above the HNI line, business owners and senior roles'),
          value: !s.showAllLeads, onChanged: (v) => s.setShowAll(!v),
        ),
        if (items.isEmpty) const Padding(padding: EdgeInsets.all(32), child: Center(child: Muted('No leads match. Clear the search or filter.', size: 14))),
        for (final l in items) Padding(padding: const EdgeInsets.only(top: 10), child: LeadTile(l)),
      ]),
    );
  }
}

class LeadTile extends StatelessWidget {
  const LeadTile(this.lead, {super.key});
  final Lead lead;
  @override
  Widget build(BuildContext context) {
    final c = FlhColors.of(context);
    return FlhCard(
      onTap: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => LeadDetailScreen(leadId: lead.id))),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
          Expanded(child: Text(lead.name, maxLines: 2, overflow: TextOverflow.ellipsis, style: const TextStyle(fontWeight: FontWeight.w700))),
          const SizedBox(width: 8), QualityPill(lead.quality),
        ]),
        const SizedBox(height: 2),
        Muted('${lead.city} · ${lead.brand}'),
        const SizedBox(height: 8),
        Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
          Text(lead.budgetText, style: kMono.copyWith(fontWeight: FontWeight.w700, color: c.accent)),
          Muted(lead.status),
        ]),
      ]),
    );
  }
}

class LeadDetailScreen extends StatelessWidget {
  const LeadDetailScreen({super.key, required this.leadId});
  final String leadId;

  Future<void> _pickDate(BuildContext context, AppState s, Lead l) async {
    final now = DateTime.now();
    final d = await showDatePicker(context: context, initialDate: now.add(const Duration(days: 3)),
        firstDate: now.subtract(const Duration(days: 1)), lastDate: now.add(const Duration(days: 365)));
    if (d != null) await s.setFollowUp(l.id, formatDate(d));
  }

  Future<void> _editNotes(BuildContext context, AppState s, Lead l) async {
    final ctl = TextEditingController(text: l.notes);
    final saved = await showModalBottomSheet<String>(
      context: context, isScrollControlled: true,
      builder: (ctx) => Padding(
        padding: EdgeInsets.fromLTRB(16, 16, 16, MediaQuery.viewInsetsOf(ctx).bottom + 16),
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          TextField(controller: ctl, maxLines: 6, maxLength: 2000, decoration: const InputDecoration(labelText: 'Notes')),
          const SizedBox(height: 8),
          SizedBox(width: double.infinity, child: FilledButton(onPressed: () => Navigator.pop(ctx, ctl.text), child: const Text('Save notes'))),
        ]),
      ),
    );
    ctl.dispose();
    if (saved != null) await s.setLeadNotes(l.id, saved);
  }

  @override
  Widget build(BuildContext context) {
    final s = context.watch<AppState>();
    final i = s.leads.indexWhere((x) => x.id == leadId);
    if (i < 0) return Scaffold(appBar: AppBar(), body: const Center(child: Muted('This lead is no longer in the list.', size: 14)));
    final l = s.leads[i];
    final c = FlhColors.of(context);
    return Scaffold(
      appBar: AppBar(title: const Text('Lead')),
      body: ListView(padding: const EdgeInsets.fromLTRB(16, 4, 16, 32), children: [
        Text(l.name, style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w800, height: 1.2)),
        const SizedBox(height: 8),
        Row(children: [QualityPill(l.quality), const SizedBox(width: 8), Muted(l.segment)]),
        const SizedBox(height: 12),
        FlhCard(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Muted('Budget'),
          Text(l.budgetText, style: kMono.copyWith(fontSize: 28, fontWeight: FontWeight.w700, color: c.accent)),
        ])),
        const SizedBox(height: 10),
        FlhCard(child: Column(children: [
          FieldRow('Brand', l.brand), FieldRow('City', l.city), FieldRow('Profession', l.profession),
          FieldRow('Source', l.source), FieldRow('Received', l.dateReceived), FieldRow('Owner', l.owner),
          FieldRow('Follow-up', l.nextFollowUp.isEmpty ? 'Not set' : l.nextFollowUp),
        ])),
        const SectionLabel('Status'),
        ChipChoices(options: leadStatuses, value: l.status, onChanged: (v) => s.setLeadStatus(l.id, v)),
        const SectionLabel('Notes'),
        FlhCard(onTap: () => _editNotes(context, s, l), child: SizedBox(width: double.infinity,
            child: Text(l.notes.isEmpty ? 'Tap to add notes' : l.notes, style: const TextStyle(fontSize: 14, height: 1.4)))),
        const SizedBox(height: 16),
        if (l.phone.isEmpty && l.email.isEmpty)
          OutlinedButton(onPressed: null, child: const Text('Contact hidden on source')),
        if (l.phone.isNotEmpty) Padding(padding: const EdgeInsets.only(bottom: 8), child: Row(children: [
          Expanded(child: FilledButton(onPressed: () => openLink(context, l.phone, scheme: 'tel'), child: const Text('Call'))),
          const SizedBox(width: 8),
          Expanded(child: OutlinedButton(onPressed: () => openLink(context, l.phone, scheme: 'wa'), child: const Text('WhatsApp'))),
        ])),
        if (l.email.isNotEmpty) Padding(padding: const EdgeInsets.only(bottom: 8),
            child: SizedBox(width: double.infinity, child: OutlinedButton(onPressed: () => openLink(context, l.email, scheme: 'mailto'), child: Text('Email ${l.email}')))),
        if (l.sourceUrl.isNotEmpty) SizedBox(width: double.infinity,
            child: OutlinedButton(onPressed: () => openLink(context, l.sourceUrl), child: const Text('Open source profile'))),
        const SizedBox(height: 8),
        SizedBox(width: double.infinity, child: FilledButton(onPressed: () => _pickDate(context, s, l), child: const Text('Set follow-up date'))),
      ]),
    );
  }
}
