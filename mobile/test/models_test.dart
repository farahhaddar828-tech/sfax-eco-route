import 'package:eco_route/i18n.dart';
import 'package:eco_route/models.dart';
import 'package:eco_route/settings.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  // Settings is a singleton, so a test that switches language and does not put
  // it back changes the result of whichever test runs next.
  tearDown(() => Settings.instance.language = 'fr');

  test('report parses backend JSON', () {
    final r = Report.fromJson({
      'id': 'x',
      'category': 'road',
      'description': 'trou',
      'lat': 34.74,
      'lon': 10.76,
      'zone': 'Sfax Médina',
      'road_name': 'Route de Tunis',
      'priority_score': 72.5,
      'priority_label': 'high',
      'status': 'triaged',
      'upvotes': 2,
      'created_at': '2026-10-16T18:00:00+00:00',
    });
    expect(r.pos.latitude, 34.74);
    expect(catLabel(r.category), 'Routes');
    expect(priorityText(r.priorityLabel), 'Élevée');
  });

  test('assistant draft parses tool arguments', () {
    final d = ReportDraft.fromJson({'category': 'flooding', 'description': 'rue inondée', 'urgency': 85});
    expect(d.urgency, 85);
    expect(d.pos, isNull);
  });

  test('every category has a distinct key and an icon', () {
    expect(categories.length, 10);
    expect(categories.map((c) => c.key).toSet().length, categories.length);
    // An unknown key must not throw; it falls back to the last entry, 'other'.
    expect(categoryOf('no-such-category').key, 'other');
    expect(catIcon('road'), categoryOf('road').icon);
  });

  test('labels follow the selected language', () {
    Settings.instance.language = 'fr';
    expect(catLabel('road'), 'Routes');
    expect(priorityText('critical'), 'Critique');

    Settings.instance.language = 'en';
    expect(catLabel('road'), 'Roads');
    expect(priorityText('critical'), 'Critical');

    Settings.instance.language = 'ar';
    expect(catLabel('road'), 'الطرقات');
    expect(priorityText('critical'), 'حرجة');
  });

  test('no user-facing string falls back to French in English or Arabic', () {
    // A missing key falls back to French silently, which is how the map mode
    // chips stayed French. One key per screen, asserted present and different.
    const keys = [
      'map.mode.reports',
      'map.hint.origin',
      'report.title',
      'report.submit',
      'dash.title',
      'dash.hotspots',
      'assistant.title',
      'assistant.hint',
      'pick.confirm',
    ];
    Settings.instance.language = 'fr';
    final french = {for (final k in keys) k: t(k)};
    for (final lang in ['en', 'ar']) {
      Settings.instance.language = lang;
      for (final k in keys) {
        expect(t(k), isNot(k), reason: '$k is missing from every language');
        expect(t(k), isNot(french[k]), reason: '$k is not translated into $lang');
      }
    }
  });

  test('tp fills placeholders', () {
    Settings.instance.language = 'en';
    final s = tp('map.closure.title', {'road': 'Route de Tunis'});
    expect(s.contains('Route de Tunis'), isTrue);
    expect(s.contains('{road}'), isFalse);
  });

  test('bidi isolates a name without changing its text', () {
    const name = 'شارع بنزرت';
    final wrapped = bidi(name);
    // The isolate characters are invisible, so the name itself must survive
    // untouched; only the surrounding sentence's layout changes.
    expect(wrapped.contains(name), isTrue);
    expect(wrapped.codeUnitAt(0), 0x2068); // First Strong Isolate
    expect(wrapped.codeUnits.last, 0x2069); // Pop Directional Isolate
    expect(wrapped.replaceAll('\u2068', '').replaceAll('\u2069', ''), name);
    // Null and numbers must not crash a label built from backend JSON.
    expect(bidi(null).contains('null'), isTrue);
  });

  test('priority colours are distinct and an unknown band is safe', () {
    final colours = ['critical', 'high', 'medium', 'low'].map(priorityColor).toSet();
    expect(colours.length, 4);
    expect(priorityColor('something-new'), priorityColor('low'));
    expect(priorityText('something-new'), priorityText('low'));
  });
}
