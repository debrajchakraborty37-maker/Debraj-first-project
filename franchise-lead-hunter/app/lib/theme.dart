import 'package:material_ui/material_ui.dart';

/// Colours from the Franchise Lead Hunter design system (light and dark values).
class FlhColors {
  final Color surface100, surface200, ink, muted, hairline, brand, onBrand, brandTint, accent, onAccent, hot, warm, cold;
  const FlhColors({
    required this.surface100, required this.surface200, required this.ink, required this.muted, required this.hairline,
    required this.brand, required this.onBrand, required this.brandTint, required this.accent, required this.onAccent,
    required this.hot, required this.warm, required this.cold,
  });

  static const dark = FlhColors(
    surface100: Color(0xFF14181A), surface200: Color(0xFF1E2427), ink: Color(0xFFEEF2F0), muted: Color(0xFFA3B0AC),
    hairline: Color(0xFF2E373A), brand: Color(0xFF4CC3B5), onBrand: Color(0xFF0B1513), brandTint: Color(0xFF173A36),
    accent: Color(0xFFF2B73C), onAccent: Color(0xFF1D1500), hot: Color(0xFFFF8A5B), warm: Color(0xFFF2B73C), cold: Color(0xFF8DB8EF),
  );
  static const light = FlhColors(
    surface100: Color(0xFFF6F4EF), surface200: Color(0xFFFFFFFF), ink: Color(0xFF14211F), muted: Color(0xFF566360),
    hairline: Color(0xFFD9D4C8), brand: Color(0xFF0F5C55), onBrand: Color(0xFFFFFFFF), brandTint: Color(0xFFDCEFEC),
    accent: Color(0xFFE8A317), onAccent: Color(0xFF1D1500), hot: Color(0xFFB93A0A), warm: Color(0xFF8A5A00), cold: Color(0xFF2F5F95),
  );

  static FlhColors of(BuildContext context) =>
      Theme.of(context).brightness == Brightness.dark ? dark : light;

  Color quality(String q) => q == 'Hot' ? hot : q == 'Warm' ? warm : cold;
}

const kRadiusMd = 14.0, kRadiusLg = 24.0;
const kMono = TextStyle(fontFamily: 'monospace', fontFeatures: [FontFeature.tabularFigures()]);

ThemeData buildTheme(Brightness b) {
  final c = b == Brightness.dark ? FlhColors.dark : FlhColors.light;
  final scheme = ColorScheme(
    brightness: b, primary: c.brand, onPrimary: c.onBrand, secondary: c.accent, onSecondary: c.onAccent,
    error: c.hot, onError: c.onBrand, surface: c.surface100, onSurface: c.ink,
    surfaceContainerHighest: c.surface200, outline: c.hairline, onSurfaceVariant: c.muted,
  );
  return ThemeData(
    useMaterial3: true, colorScheme: scheme, scaffoldBackgroundColor: c.surface100,
    appBarTheme: AppBarTheme(backgroundColor: c.surface100, foregroundColor: c.ink, elevation: 0, scrolledUnderElevation: 0),
    navigationBarTheme: NavigationBarThemeData(
      backgroundColor: c.surface200, indicatorColor: c.brandTint,
      labelTextStyle: WidgetStatePropertyAll(TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: c.muted)),
    ),
    dividerColor: c.hairline,
    inputDecorationTheme: InputDecorationTheme(
      filled: true, fillColor: c.surface200,
      border: OutlineInputBorder(borderRadius: BorderRadius.circular(kRadiusMd), borderSide: BorderSide(color: c.hairline)),
      enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(kRadiusMd), borderSide: BorderSide(color: c.hairline)),
    ),
  );
}
