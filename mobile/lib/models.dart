import 'package:flutter/material.dart';
import 'package:latlong2/latlong.dart';

const sfaxCenter = LatLng(34.7406, 10.7603);

/// A report category: a stable key, and the icon that stands for it.
///
/// The label is deliberately *not* stored here — it comes from `catLabel(key)`
/// in i18n.dart, so the category list carries no language of its own.
///
/// Icons rather than emoji: an emoji is drawn by whatever font the device
/// happens to ship, so it changed shape from phone to phone and was illegible
/// at marker size. A Material icon is a vector in the app's own font: crisp at
/// 16 px and it takes the colour it is given.
class CategoryInfo {
  const CategoryInfo(this.key, this.icon);
  final String key;
  final IconData icon;
}

const categories = <CategoryInfo>[
  CategoryInfo('waste', Icons.delete_outline),
  CategoryInfo('road', Icons.edit_road),
  CategoryInfo('lighting', Icons.lightbulb_outline),
  CategoryInfo('traffic', Icons.traffic),
  CategoryInfo('school', Icons.school_outlined),
  CategoryInfo('flooding', Icons.water_drop_outlined),
  CategoryInfo('water', Icons.plumbing),
  CategoryInfo('pollution', Icons.factory),
  CategoryInfo('green', Icons.park_outlined),
  CategoryInfo('other', Icons.place_outlined),
];

CategoryInfo categoryOf(String key) =>
    categories.firstWhere((c) => c.key == key, orElse: () => categories.last);

/// Shortcut for the icon of a category key.
IconData catIcon(String key) => categoryOf(key).icon;

/// The one colour dimension in the app. Priority is the thing a reader needs to
/// judge at a glance, so priority owns colour and nothing else competes for it:
/// category is carried by icon shape alone.
Color priorityColor(String label) => switch (label) {
      'critical' => const Color(0xFFB3261E),
      'high' => const Color(0xFFE07B1A),
      'medium' => const Color(0xFFC9A227),
      _ => const Color(0xFF4F7A3A),
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
