import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';

import '../api.dart';
import '../i18n.dart';
import '../location.dart';
import '../models.dart';
import 'settings_screen.dart';

enum MapMode { browse, route, closure }

class MapScreen extends StatefulWidget {
  const MapScreen({super.key});
  @override
  State<MapScreen> createState() => MapScreenState();
}

class MapScreenState extends State<MapScreen> {
  final _map = MapController();
  List<Report> _reports = [];
  List<dynamic> _hotspots = [];
  LatLng? _me;
  MapMode _mode = MapMode.browse;
  LatLng? _from, _to;
  Map<String, dynamic>? _route, _closure;
  bool _busy = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    refresh();
    currentPosition().then((p) => mounted ? setState(() => _me = p) : null);
  }

  Future<void> refresh() async {
    try {
      final r = await Api.instance.reports();
      final h = await Api.instance.hotspots();
      if (mounted) setState(() => (_reports = r, _hotspots = h, _error = null));
    } catch (e) {
      if (mounted) setState(() => _error = '${t('map.error.server')} ($e)');
    }
  }

  Future<void> _onTap(LatLng p) async {
    if (_mode == MapMode.route) {
      if (_from == null || _to != null) {
        setState(() => (_from = p, _to = null, _route = null));
        return;
      }
      setState(() => (_to = p, _busy = true));
      try {
        final r = await Api.instance.route(_from!, p);
        if (mounted) setState(() => _route = r);
      } catch (e) {
        _snack('$e');
      } finally {
        if (mounted) setState(() => _busy = false);
      }
    } else if (_mode == MapMode.closure) {
      setState(() => (_busy = true, _closure = null));
      try {
        final c = await Api.instance.closureImpact(p);
        if (mounted) setState(() => _closure = c);
      } catch (e) {
        _snack('$e');
      } finally {
        if (mounted) setState(() => _busy = false);
      }
    }
  }

  void _snack(String m) => ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(m)));

  List<LatLng> _pts(dynamic coords) =>
      (coords as List).map((c) => LatLng((c[0] as num).toDouble(), (c[1] as num).toDouble())).toList();

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return Scaffold(
      appBar: AppBar(
        title: Text(t('app.title')),
        actions: [
          IconButton(onPressed: refresh, icon: const Icon(Icons.refresh), tooltip: t('action.refresh')),
          IconButton(
            onPressed: () => Navigator.of(context)
                .push(MaterialPageRoute(builder: (_) => const SettingsScreen())),
            icon: const Icon(Icons.settings_outlined),
            tooltip: t('settings.title'),
          ),
        ],
      ),
      body: Stack(children: [
        FlutterMap(
          mapController: _map,
          options: MapOptions(initialCenter: _me ?? sfaxCenter, initialZoom: 13, onTap: (_, p) => _onTap(p)),
          children: [
            TileLayer(
              urlTemplate: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
              userAgentPackageName: 'tn.ecoroute.app',
            ),
            CircleLayer(circles: [
              for (final h in _hotspots)
                CircleMarker(
                  point: LatLng((h['lat'] as num).toDouble(), (h['lon'] as num).toDouble()),
                  radius: 250,
                  useRadiusInMeter: true,
                  color: priorityColor('critical').withValues(alpha: .18),
                  borderColor: priorityColor('critical'),
                  borderStrokeWidth: 1.5,
                ),
            ]),
            PolylineLayer(polylines: [
              if (_route != null)
                Polyline(points: _pts(_route!['fastest']['coords']), strokeWidth: 5, color: Colors.grey.shade600),
              if (_route != null)
                Polyline(points: _pts(_route!['eco_route']['coords']), strokeWidth: 6, color: cs.primary),
              if (_closure != null)
                Polyline(points: _pts(_closure!['edge']['coords']), strokeWidth: 8, color: priorityColor('critical')),
              if (_closure != null && (_closure!['detour_coords'] as List).isNotEmpty)
                Polyline(points: _pts(_closure!['detour_coords']), strokeWidth: 5, color: cs.tertiary),
            ]),
            MarkerLayer(markers: [
              for (final r in _reports)
                Marker(
                  point: r.pos,
                  width: 38,
                  height: 38,
                  child: GestureDetector(
                    onTap: () => _showReport(r),
                    child: Container(
                      decoration: BoxDecoration(
                        color: priorityColor(r.priorityLabel),
                        shape: BoxShape.circle,
                        border: Border.all(color: Colors.white, width: 2),
                        boxShadow: const [BoxShadow(blurRadius: 4, color: Colors.black26)],
                      ),
                      alignment: Alignment.center,
                      // Colour says how urgent, shape says what kind. Both read
                      // at a glance without a legend.
                      child: Icon(catIcon(r.category), size: 19, color: Colors.white),
                    ),
                  ),
                ),
              if (_me != null)
                Marker(point: _me!, width: 20, height: 20, child: _dot(Colors.blue)),
              if (_from != null) Marker(point: _from!, width: 20, height: 20, child: _dot(Colors.black)),
              if (_to != null) Marker(point: _to!, width: 20, height: 20, child: _dot(cs.primary)),
            ]),
            const RichAttributionWidget(attributions: [TextSourceAttribution('© OpenStreetMap contributors')]),
          ],
        ),
        Positioned(
          top: 12,
          left: 12,
          right: 12,
          child: SegmentedButton<MapMode>(
            style: SegmentedButton.styleFrom(backgroundColor: cs.surface),
            // Not `const`: these labels have to be rebuilt when the language
            // changes, and a const list freezes them at their first value.
            segments: [
              ButtonSegment(
                  value: MapMode.browse,
                  icon: const Icon(Icons.place_outlined),
                  label: Text(t('map.mode.reports'))),
              ButtonSegment(
                  value: MapMode.route, icon: const Icon(Icons.alt_route), label: Text(t('map.mode.route'))),
              ButtonSegment(
                  value: MapMode.closure, icon: const Icon(Icons.block), label: Text(t('map.mode.closure'))),
            ],
            selected: {_mode},
            onSelectionChanged: (s) => setState(() {
              _mode = s.first;
              _from = _to = null;
              _route = _closure = null;
            }),
          ),
        ),
        if (_busy) const Positioned(top: 70, left: 0, right: 0, child: LinearProgressIndicator()),
        if (_error != null) Positioned(top: 70, left: 12, right: 12, child: _banner(_error!, cs.errorContainer)),
        if (_mode == MapMode.route && _route == null)
          Positioned(top: 70, left: 12, right: 12,
              child: _banner(t(_from == null ? 'map.hint.origin' : 'map.hint.destination'), cs.surface)),
        if (_mode == MapMode.closure && _closure == null)
          Positioned(top: 70, left: 12, right: 12, child: _banner(t('map.hint.closure'), cs.surface)),
        if (_route != null) Positioned(left: 12, right: 12, bottom: 90, child: _routeCard()),
        if (_closure != null) Positioned(left: 12, right: 12, bottom: 90, child: _closureCard()),
      ]),
    );
  }

  Widget _dot(Color c) => Container(
      decoration: BoxDecoration(color: c, shape: BoxShape.circle, border: Border.all(color: Colors.white, width: 3)));

  Widget _banner(String text, Color bg) => Material(
        color: bg,
        elevation: 2,
        borderRadius: BorderRadius.circular(12),
        child: Padding(padding: const EdgeInsets.all(12), child: Text(text)),
      );

  String _min(num s) => '${(s / 60).toStringAsFixed(1)} min';

  /// A legend line whose swatch is the colour of the line it describes, so the
  /// card and the map read as one thing.
  Widget _legend(Color color, String label, String detail) => Padding(
        padding: const EdgeInsets.only(top: 4),
        child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Padding(
            padding: const EdgeInsetsDirectional.only(end: 8, top: 5),
            child: Container(
                width: 14, height: 4, decoration: BoxDecoration(color: color, borderRadius: BorderRadius.circular(2))),
          ),
          Expanded(
            child: Text.rich(TextSpan(children: [
              TextSpan(text: '$label : ', style: const TextStyle(fontWeight: FontWeight.w600)),
              TextSpan(text: detail),
            ])),
          ),
        ]),
      );

  Widget _routeCard() {
    final f = _route!['fastest'], e = _route!['eco_route'];
    final avoided = _route!['hazards_avoided'];
    final cs = Theme.of(context).colorScheme;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, mainAxisSize: MainAxisSize.min, children: [
          Text(t('map.route.title'), style: Theme.of(context).textTheme.titleMedium),
          _legend(
              cs.primary,
              t('map.route.safe'),
              '${_min(e['time_s'])}, ${(e['length_m'] / 1000).toStringAsFixed(1)} km, '
                  '${e['hazards_on_route']} ${t('map.route.issues')}, ${e['co2_g'].round()} g CO₂'),
          _legend(Colors.grey.shade600, t('map.route.fastest'),
              '${_min(f['time_s'])}, ${f['hazards_on_route']} ${t('map.route.issues')}'),
          if (avoided > 0)
            Padding(
              padding: const EdgeInsets.only(top: 6),
              child: Text(
                  '$avoided ${t('map.route.issues')} ${t('map.route.avoided')} +${_min(_route!['extra_time_s'])}',
                  style: TextStyle(color: cs.primary, fontWeight: FontWeight.w600)),
            ),
          if ((e['road_names'] as List).isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(top: 4),
              child: Text("${t('map.route.via')} : ${(e['road_names'] as List).map(bidi).join(' → ')}",
                  style: Theme.of(context).textTheme.bodySmall),
            ),
        ]),
      ),
    );
  }

  Widget _closureCard() {
    final c = _closure!, edge = c['edge'];
    final cut = c['nodes_cut_off'] as int;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, mainAxisSize: MainAxisSize.min, children: [
          Text(tp('map.closure.title', {'road': bidi(edge['name'])}),
              style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 6),
          Text('${t('map.closure.criticality')} : ${(edge['criticality'] * 100).round()} %'
              '${edge['is_bridge'] ? " — ${t('map.closure.nobackup')}" : ''}'),
          if (cut > 0) Text('$cut ${t('map.closure.isolated')}'),
          if (c['detour_extra_m'] != null)
            Text('${t('map.closure.detour')} : +${(c['detour_extra_m'] / 1000).toStringAsFixed(2)} km'
                ' / +${_min(c['detour_extra_s'])}'),
          Text(tp('map.closure.trips', {
            'pct': '${c['sampled_trips_affected_pct']}',
            'delay': _min(c['avg_delay_on_affected_s']),
          })),
        ]),
      ),
    );
  }

  void _showReport(Report r) {
    final cat = categoryOf(r.category);
    showModalBottomSheet(
      context: context,
      showDragHandle: true,
      builder: (_) => Padding(
        padding: const EdgeInsets.fromLTRB(20, 0, 20, 24),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, mainAxisSize: MainAxisSize.min, children: [
          Row(children: [
            Icon(cat.icon, color: priorityColor(r.priorityLabel)),
            const SizedBox(width: 10),
            Expanded(child: Text(catLabel(cat.key), style: Theme.of(context).textTheme.titleLarge)),
          ]),
          Text('${bidi(r.roadName)} · ${bidi(r.zone)}'),
          const SizedBox(height: 8),
          Chip(
            label: Text('${priorityText(r.priorityLabel)} · ${r.priorityScore.round()}/100',
                style: const TextStyle(color: Colors.white)),
            backgroundColor: priorityColor(r.priorityLabel),
          ),
          const SizedBox(height: 8),
          Text(r.description),
          if (r.photoUrl != null) ...[
            const SizedBox(height: 8),
            ClipRRect(
                borderRadius: BorderRadius.circular(12),
                child: Image.network('$apiUrl${r.photoUrl}', height: 160, fit: BoxFit.cover)),
          ],
          const SizedBox(height: 12),
          FilledButton.tonalIcon(
            onPressed: () async {
              Navigator.pop(context);
              await Api.instance.upvote(r.id);
              _snack(t('map.upvote.thanks'));
              refresh();
            },
            icon: const Icon(Icons.thumb_up_alt_outlined),
            label: Text('${t('map.upvote')} (${r.upvotes})'),
          ),
        ]),
      ),
    );
  }
}
