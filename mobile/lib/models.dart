import 'package:flutter/material.dart';
import 'package:latlong2/latlong.dart';

const sfaxCenter = LatLng(34.7406, 10.7603);

class CategoryInfo {
  const CategoryInfo(this.key, this.label, this.emoji);
  final String key;
  final String label;
  final String emoji;
}

const categories = <CategoryInfo>[
  CategoryInfo('waste', 'Déchets', '🗑️'),
  CategoryInfo('road', 'Routes', '🛣️'),
  CategoryInfo('lighting', 'Éclairage', '💡'),
  CategoryInfo('traffic', 'Circulation', '🚦'),
  CategoryInfo('school', 'Écoles', '🏫'),
  CategoryInfo('flooding', 'Inondation', '🌊'),
  CategoryInfo('water', "Fuite d'eau", '🚰'),
  CategoryInfo('pollution', 'Pollution', '🏭'),
  CategoryInfo('green', 'Espaces verts', '🌳'),
  CategoryInfo('other', 'Autre', '📍'),
];

CategoryInfo categoryOf(String key) =>
    categories.firstWhere((c) => c.key == key, orElse: () => categories.last);

Color priorityColor(String label) => switch (label) {
      'critical' => const Color(0xFFB3261E),
      'high' => const Color(0xFFE07B1A),
      'medium' => const Color(0xFFC9A227),
      _ => const Color(0xFF4F7A3A),
    };

String priorityFr(String label) => switch (label) {
      'critical' => 'Critique',
      'high' => 'Élevée',
      'medium' => 'Moyenne',
      _ => 'Faible',
    };

class Report {
  Report({
    required this.id,
    required this.category,
    required this.description,
    required this.pos,
    required this.zone,
    required this.roadName,
    required this.priorityScore,
    required this.priorityLabel,
    required this.status,
    required this.upvotes,
    required this.createdAt,
    this.aiSummary,
    this.photoUrl,
  });

  factory Report.fromJson(Map<String, dynamic> j) => Report(
        id: j['id'],
        category: j['category'],
        description: j['description'],
        pos: LatLng((j['lat'] as num).toDouble(), (j['lon'] as num).toDouble()),
        zone: j['zone'] ?? '',
        roadName: j['road_name'] ?? '',
        priorityScore: (j['priority_score'] as num).toDouble(),
        priorityLabel: j['priority_label'],
        status: j['status'],
        upvotes: j['upvotes'] ?? 0,
        createdAt: DateTime.parse(j['created_at']),
        aiSummary: j['ai_summary'],
        photoUrl: j['photo_url'],
      );

  final String id, category, description, zone, roadName, priorityLabel, status;
  final LatLng pos;
  final double priorityScore;
  final int upvotes;
  final DateTime createdAt;
  final String? aiSummary, photoUrl;
}

/// Draft passed from the assistant to the report form.
class ReportDraft {
  const ReportDraft({this.category, this.description = '', this.urgency = 50, this.pos});
  factory ReportDraft.fromJson(Map<String, dynamic> j) => ReportDraft(
        category: j['category'],
        description: j['description'] ?? '',
        urgency: (j['urgency'] ?? j['citizen_urgency'] ?? 50) as int,
        pos: j['lat'] != null ? LatLng((j['lat'] as num).toDouble(), (j['lon'] as num).toDouble()) : null,
      );
  final String? category;
  final String description;
  final int urgency;
  final LatLng? pos;
}
