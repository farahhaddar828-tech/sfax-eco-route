import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:http/http.dart' as http;
import 'package:latlong2/latlong.dart';

import '../i18n.dart';
import '../location.dart';

/// One geocoding hit from Nominatim.
class _Place {
  _Place(this.label, this.pos);
  final String label;
  final LatLng pos;
}

/// Full-screen location picker.
///
/// The pin is painted at the centre of the screen and never moves; the map
/// slides underneath it. That is far easier one-handed than asking someone to
/// tap an exact point on a 200 px map, which is what this replaces.
///
/// Search uses Nominatim, OpenStreetMap's own geocoder: no API key, and the
/// query is bounded to the Grand Sfax box so results stay local.
class PickLocationScreen extends StatefulWidget {
  const PickLocationScreen({super.key, required this.initial});

  final LatLng initial;

  @override
  State<PickLocationScreen> createState() => _PickLocationScreenState();
}

class _PickLocationScreenState extends State<PickLocationScreen> {
  final _map = MapController();
  final _query = TextEditingController();
  Timer? _debounce;
  List<_Place> _results = [];
  bool _searching = false;
  String? _chosenLabel;
  bool _locating = false;

  @override
  void dispose() {
    _debounce?.cancel();
    _query.dispose();
    super.dispose();
  }

  void _onQueryChanged(String q) {
    _debounce?.cancel();
    if (q.trim().length < 3) {
      setState(() => _results = []);
      return;
    }
    // Nominatim asks for at most one request a second, so never search per keystroke.
    _debounce = Timer(const Duration(milliseconds: 600), () => _search(q.trim()));
  }

  Future<void> _search(String q) async {
    setState(() => _searching = true);
    try {
      final uri = Uri.https('nominatim.openstreetmap.org', '/search', {
        'q': q,
        'format': 'jsonv2',
        'limit': '8',
        // lon_min, lat_max, lon_max, lat_min - the Grand Sfax bounding box
        'viewbox': '10.40,35.00,11.00,34.50',
        'bounded': '1',
        'accept-language': 'fr',
      });
      final r = await http.get(uri, headers: {
        // Nominatim rejects requests without a real identifying User-Agent.
        'User-Agent': 'SfaxEcoRoute/2.0 (civic reporting app; Sfax, Tunisia)',
      }).timeout(const Duration(seconds: 12));
      if (!mounted) return;
      if (r.statusCode != 200) {
        setState(() => _results = []);
        return;
      }
      final list = (jsonDecode(utf8.decode(r.bodyBytes)) as List)
          .map((e) => _Place(
                (e['display_name'] ?? '').toString(),
                LatLng(double.parse(e['lat'].toString()), double.parse(e['lon'].toString())),
              ))
          .toList();
      setState(() => _results = list);
    } catch (_) {
      if (mounted) setState(() => _results = []);
    } finally {
      if (mounted) setState(() => _searching = false);
    }
  }

  void _goTo(_Place p) {
    FocusScope.of(context).unfocus();
    _map.move(p.pos, 17);
    setState(() {
      _results = [];
      _chosenLabel = p.label;
      _query.text = p.label.split(',').first;
    });
  }

  Future<void> _useMyLocation() async {
    setState(() => _locating = true);
    final p = await currentPosition();
    if (!mounted) return;
    setState(() => _locating = false);
    if (p == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(t('pick.nolocation'))),
      );
      return;
    }
    _map.move(p, 17);
    setState(() => _chosenLabel = t('pick.mylocation'));
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return Scaffold(
      appBar: AppBar(title: const Text("Choisir l'emplacement")),
      body: Stack(children: [
        FlutterMap(
          mapController: _map,
          options: MapOptions(
            initialCenter: widget.initial,
            initialZoom: 17,
            minZoom: 11,
            maxZoom: 19,
          ),
          children: [
            TileLayer(
              urlTemplate: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
              userAgentPackageName: 'tn.ecoroute.app',
            ),
            const RichAttributionWidget(
              attributions: [TextSourceAttribution('© OpenStreetMap contributors')],
            ),
          ],
        ),

        // The pin sits in the dead centre and does not move with the map.
        IgnorePointer(
          child: Center(
            child: Padding(
              // lift it by half its height so the point, not the middle, marks the spot
              padding: const EdgeInsets.only(bottom: 44),
              child: Icon(Icons.location_pin, size: 48, color: cs.error),
            ),
          ),
        ),

        // Search field and results, floating over the map.
        Positioned(
          left: 12,
          right: 12,
          top: 12,
          child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
            Material(
              elevation: 3,
              borderRadius: BorderRadius.circular(14),
              child: TextField(
                controller: _query,
                textInputAction: TextInputAction.search,
                onChanged: _onQueryChanged,
                onSubmitted: (q) => q.trim().length >= 3 ? _search(q.trim()) : null,
                decoration: InputDecoration(
                  hintText: t('pick.search'),
                  prefixIcon: const Icon(Icons.search),
                  suffixIcon: _searching
                      ? const Padding(
                          padding: EdgeInsets.all(14),
                          child: SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2)),
                        )
                      : (_query.text.isEmpty
                          ? null
                          : IconButton(
                              icon: const Icon(Icons.clear),
                              onPressed: () => setState(() {
                                _query.clear();
                                _results = [];
                              }),
                            )),
                  border: OutlineInputBorder(borderRadius: BorderRadius.circular(14), borderSide: BorderSide.none),
                  filled: true,
                  fillColor: Theme.of(context).colorScheme.surface,
                ),
              ),
            ),
            if (_results.isNotEmpty)
              Container(
                margin: const EdgeInsets.only(top: 6),
                constraints: const BoxConstraints(maxHeight: 260),
                decoration: BoxDecoration(
                  color: Theme.of(context).colorScheme.surface,
                  borderRadius: BorderRadius.circular(14),
                  boxShadow: const [BoxShadow(blurRadius: 6, color: Color(0x33000000))],
                ),
                child: ListView.separated(
                  shrinkWrap: true,
                  itemCount: _results.length,
                  separatorBuilder: (_, __) => const Divider(height: 1),
                  itemBuilder: (_, i) {
                    final parts = _results[i].label.split(',');
                    return ListTile(
                      dense: true,
                      leading: const Icon(Icons.place_outlined),
                      title: Text(parts.first, maxLines: 1, overflow: TextOverflow.ellipsis),
                      subtitle: Text(parts.skip(1).join(',').trim(),
                          maxLines: 1, overflow: TextOverflow.ellipsis),
                      onTap: () => _goTo(_results[i]),
                    );
                  },
                ),
              ),
          ]),
        ),

        // My-location button, clear of the confirm bar.
        Positioned(
          right: 12,
          bottom: 104,
          child: FloatingActionButton.small(
            heroTag: 'pick-my-location',
            onPressed: _locating ? null : _useMyLocation,
            tooltip: t('pick.mylocation'),
            child: _locating
                ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2))
                : const Icon(Icons.my_location),
          ),
        ),

        // Confirm bar.
        Positioned(
          left: 12,
          right: 12,
          bottom: 16,
          child: Material(
            elevation: 4,
            borderRadius: BorderRadius.circular(16),
            color: Theme.of(context).colorScheme.surface,
            child: Padding(
              padding: const EdgeInsets.fromLTRB(16, 12, 12, 12),
              child: Row(children: [
                Expanded(
                  child: Text(
                    _chosenLabel ?? t('pick.hint'),
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: Theme.of(context).textTheme.bodyMedium,
                  ),
                ),
                const SizedBox(width: 8),
                FilledButton.icon(
                  onPressed: () => Navigator.of(context).pop(_map.camera.center),
                  icon: const Icon(Icons.check),
                  label: Text(t('pick.confirm')),
                ),
              ]),
            ),
          ),
        ),
      ]),
    );
  }
}
