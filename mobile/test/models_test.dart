import 'package:eco_route/models.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
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
    expect(categoryOf(r.category).label, 'Routes');
    expect(priorityFr(r.priorityLabel), 'Élevée');
  });

  test('assistant draft parses tool arguments', () {
    final d = ReportDraft.fromJson({'category': 'flooding', 'description': 'rue inondée', 'urgency': 85});
    expect(d.urgency, 85);
    expect(d.pos, isNull);
  });
}
