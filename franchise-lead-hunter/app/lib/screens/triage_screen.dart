import 'package:material_ui/material_ui.dart';
import 'package:provider/provider.dart';
import '../models.dart';
import '../state/app_state.dart';
import '../theme.dart';
import '../widgets/common.dart';

/// Design B: swipe right to keep, left to skip. Buttons do the same for anyone who prefers taps.
class TriageScreen extends StatelessWidget {
  const TriageScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final s = context.watch<AppState>();
    final q = s.triageQueue;
    return RefreshIndicator(
      onRefresh: s.refreshAll,
      child: ListView(padding: const EdgeInsets.fromLTRB(16, 12, 16, 24), children: [
        Row(children: [
          const Expanded(child: Text('Triage', style: TextStyle(fontSize: 26, fontWeight: FontWeight.w800))),
          Muted(q.isEmpty ? 'All done' : '${q.length} to review'),
        ]),
        if (q.isEmpty) ...[
          const SizedBox(height: 48),
          const Center(child: Text('You are all caught up', style: TextStyle(fontSize: 17, fontWeight: FontWeight.w700))),
          const SizedBox(height: 8),
          Center(child: Muted('${s.keptLeads.length} kept, ${s.skippedLeads.length} skipped', size: 14)),
          const SizedBox(height: 16),
          Center(child: FilledButton(
            onPressed: s.hunting ? null : () => s.huntNow(),
            child: Text(s.hunting ? 'Hunting…' : 'Hunt now'),
          )),
        ] else ...[
          const SizedBox(height: 14),
          SizedBox(height: 400, child: _Stack(queue: q)),
          const SizedBox(height: 8),
          Row(mainAxisAlignment: MainAxisAlignment.center, children: [
            OutlinedButton(
              style: OutlinedButton.styleFrom(foregroundColor: FlhColors.of(context).hot, minimumSize: const Size(96, 48)),
              onPressed: () => s.swipe(q.first, keep: false), child: const Text('Skip')),
            const SizedBox(width: 12),
            TextButton(onPressed: s.canUndo ? s.undo : null, child: const Text('Undo')),
            const SizedBox(width: 12),
            FilledButton(style: FilledButton.styleFrom(minimumSize: const Size(96, 48)),
              onPressed: () => s.swipe(q.first, keep: true), child: const Text('Keep')),
          ]),
          const SizedBox(height: 10),
          const Center(child: Muted('Drag the card right to keep, left to skip')),
        ],
      ]),
    );
  }
}

class _Stack extends StatelessWidget {
  const _Stack({required this.queue});
  final List<Lead> queue;
  @override
  Widget build(BuildContext context) {
    final s = context.read<AppState>();
    final cards = queue.take(3).toList();
    return Stack(children: [
      for (var i = cards.length - 1; i >= 0; i--)
        Positioned.fill(
          top: i * 12.0,
          child: i == 0
              ? _SwipeCard(key: ValueKey(cards[0].id), lead: cards[0], onDecision: (keep) => s.swipe(cards[0], keep: keep))
              : Transform.scale(scale: 1 - i * 0.05, child: Opacity(opacity: i == 1 ? 0.65 : 0.35, child: _LeadFace(lead: cards[i]))),
        ),
    ]);
  }
}

class _SwipeCard extends StatefulWidget {
  const _SwipeCard({super.key, required this.lead, required this.onDecision});
  final Lead lead;
  final ValueChanged<bool> onDecision;
  @override
  State<_SwipeCard> createState() => _SwipeCardState();
}

class _SwipeCardState extends State<_SwipeCard> with SingleTickerProviderStateMixin {
  double _dx = 0;
  late final AnimationController _anim = AnimationController(vsync: this, duration: const Duration(milliseconds: 220));
  double _from = 0, _to = 0;

  @override
  void dispose() { _anim.dispose(); super.dispose(); }

  void _fling(double target, bool keep) {
    _from = _dx; _to = target;
    _anim.forward(from: 0).whenComplete(() { if (mounted) widget.onDecision(keep); });
    _anim.addListener(() => setState(() => _dx = _from + (_to - _from) * Curves.easeOut.transform(_anim.value)));
  }

  @override
  Widget build(BuildContext context) {
    final w = MediaQuery.sizeOf(context).width;
    final c = FlhColors.of(context);
    final keepOpacity = (_dx / 90).clamp(0.0, 1.0), skipOpacity = (-_dx / 90).clamp(0.0, 1.0);
    return GestureDetector(
      onHorizontalDragUpdate: (d) { if (!_anim.isAnimating) setState(() => _dx += d.delta.dx); },
      onHorizontalDragEnd: (d) {
        if (_anim.isAnimating) return;
        if (_dx.abs() > 100 || d.primaryVelocity != null && d.primaryVelocity!.abs() > 900) {
          final keep = _dx > 0 || (_dx == 0 && (d.primaryVelocity ?? 0) > 0);
          _fling(keep ? w : -w, keep);
        } else {
          setState(() => _dx = 0);
        }
      },
      child: Transform.translate(
        offset: Offset(_dx, 0),
        child: Transform.rotate(angle: _dx / 1800, child: Stack(children: [
          _LeadFace(lead: widget.lead),
          Positioned(top: 18, right: 18, child: Opacity(opacity: keepOpacity, child: _Stamp('KEEP', c.brand))),
          Positioned(top: 18, left: 18, child: Opacity(opacity: skipOpacity, child: _Stamp('SKIP', c.hot))),
        ])),
      ),
    );
  }
}

class _Stamp extends StatelessWidget {
  const _Stamp(this.text, this.color);
  final String text;
  final Color color;
  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 3),
        decoration: BoxDecoration(border: Border.all(color: color, width: 2), borderRadius: BorderRadius.circular(8)),
        child: Text(text, style: TextStyle(color: color, fontWeight: FontWeight.w800, letterSpacing: 1.2)),
      );
}

class _LeadFace extends StatelessWidget {
  const _LeadFace({required this.lead});
  final Lead lead;
  @override
  Widget build(BuildContext context) {
    final c = FlhColors.of(context);
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(color: c.surface200, border: Border.all(color: c.hairline), borderRadius: BorderRadius.circular(kRadiusLg)),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
          QualityPill(lead.quality), Flexible(child: Muted('${lead.source.isEmpty ? 'Sheet' : lead.source} · ${lead.dateReceived}')),
        ]),
        const SizedBox(height: 14),
        Text(lead.budgetText, style: kMono.copyWith(fontSize: 34, fontWeight: FontWeight.w700, color: c.accent)),
        const Muted('Budget'),
        const SizedBox(height: 14),
        Text(lead.name, maxLines: 3, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 19, fontWeight: FontWeight.w700, height: 1.25)),
        const SizedBox(height: 4),
        Muted('${lead.city} · ${lead.brand}', size: 13),
        const SizedBox(height: 12),
        Wrap(spacing: 6, runSpacing: 6, children: [
          if (lead.profession.isNotEmpty) _Tag(lead.profession),
          if (lead.segment.isNotEmpty) _Tag(lead.segment),
        ]),
        const Spacer(),
        const Muted('Phone and email: not shown on source'),
      ]),
    );
  }
}

class _Tag extends StatelessWidget {
  const _Tag(this.text);
  final String text;
  @override
  Widget build(BuildContext context) {
    final c = FlhColors.of(context);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(color: c.surface100, border: Border.all(color: c.hairline), borderRadius: BorderRadius.circular(99)),
      child: Text(text, style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600)),
    );
  }
}
