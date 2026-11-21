import 'package:material_ui/material_ui.dart';
import 'package:url_launcher/url_launcher.dart';
import '../theme.dart';

/// Hot / Warm / Cold. Colour always comes with the word.
class QualityPill extends StatelessWidget {
  const QualityPill(this.quality, {super.key});
  final String quality;
  @override
  Widget build(BuildContext context) {
    final color = FlhColors.of(context).quality(quality);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
      decoration: BoxDecoration(border: Border.all(color: color, width: 1.5), borderRadius: BorderRadius.circular(99)),
      child: Text(quality.isEmpty ? 'Not rated' : quality, style: TextStyle(color: color, fontSize: 11, fontWeight: FontWeight.w700)),
    );
  }
}

class FlhCard extends StatelessWidget {
  const FlhCard({super.key, required this.child, this.onTap, this.padding = const EdgeInsets.all(12), this.tint = false});
  final Widget child;
  final VoidCallback? onTap;
  final EdgeInsets padding;
  final bool tint;
  @override
  Widget build(BuildContext context) {
    final c = FlhColors.of(context);
    return Material(
      color: tint ? c.brandTint : c.surface200,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(kRadiusMd), side: BorderSide(color: tint ? c.brandTint : c.hairline)),
      child: InkWell(
        borderRadius: BorderRadius.circular(kRadiusMd), onTap: onTap,
        child: Padding(padding: padding, child: child),
      ),
    );
  }
}

class SectionLabel extends StatelessWidget {
  const SectionLabel(this.text, {super.key});
  final String text;
  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.only(top: 20, bottom: 8),
        child: Text(text.toUpperCase(),
            style: TextStyle(fontSize: 12, fontWeight: FontWeight.w700, letterSpacing: 0.8, color: FlhColors.of(context).muted)),
      );
}

class Muted extends StatelessWidget {
  const Muted(this.text, {super.key, this.size = 12});
  final String text;
  final double size;
  @override
  Widget build(BuildContext context) => Text(text, style: TextStyle(fontSize: size, color: FlhColors.of(context).muted));
}

/// A row of single-choice chips.
class ChipChoices extends StatelessWidget {
  const ChipChoices({super.key, required this.options, required this.value, required this.onChanged});
  final List<String> options;
  final String value;
  final ValueChanged<String> onChanged;
  @override
  Widget build(BuildContext context) => Wrap(spacing: 8, runSpacing: 8, children: [
        for (final o in options)
          ChoiceChip(label: Text(o), selected: o == value, onSelected: (_) => onChanged(o), showCheckmark: false),
      ]);
}

class ErrorBanner extends StatelessWidget {
  const ErrorBanner(this.message, {super.key, this.onClose});
  final String message;
  final VoidCallback? onClose;
  @override
  Widget build(BuildContext context) {
    final c = FlhColors.of(context);
    return Container(
      margin: const EdgeInsets.fromLTRB(16, 8, 16, 0),
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(border: Border.all(color: c.hot), borderRadius: BorderRadius.circular(kRadiusMd)),
      child: Row(children: [
        Expanded(child: Text(message, style: TextStyle(color: c.hot, fontSize: 13, fontWeight: FontWeight.w600))),
        if (onClose != null) IconButton(onPressed: onClose, icon: Icon(Icons.close, color: c.hot, size: 18)),
      ]),
    );
  }
}

class FieldRow extends StatelessWidget {
  const FieldRow(this.label, this.value, {super.key});
  final String label, value;
  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 6),
        child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          SizedBox(width: 96, child: Muted(label, size: 13)),
          Expanded(child: SelectableText(value.isEmpty ? 'Not shown' : value, style: const TextStyle(fontSize: 14))),
        ]),
      );
}

/// Opens only http(s), tel and mailto links. Anything else from the Sheet is ignored.
Future<void> openLink(BuildContext context, String raw, {String scheme = 'https'}) async {
  var url = raw.trim();
  if (url.isEmpty) return;
  if (scheme == 'https' && !RegExp(r'^https?://', caseSensitive: false).hasMatch(url)) url = 'https://$url';
  if (scheme == 'tel') url = 'tel:${url.replaceAll(RegExp(r'[^0-9+]'), '')}';
  if (scheme == 'mailto') url = 'mailto:$url';
  if (scheme == 'wa') url = 'https://wa.me/${url.replaceAll(RegExp(r'[^0-9]'), '')}';
  final uri = Uri.tryParse(url);
  const ok = {'http', 'https', 'tel', 'mailto'};
  if (uri == null || !ok.contains(uri.scheme)) return;
  final launched = await launchUrl(uri, mode: LaunchMode.externalApplication).catchError((_) => false);
  if (!launched && context.mounted) {
    ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Could not open that link.')));
  }
}

void toast(BuildContext context, String message) =>
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(message), behavior: SnackBarBehavior.floating));
