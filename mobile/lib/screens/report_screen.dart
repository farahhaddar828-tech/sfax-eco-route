import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:image_picker/image_picker.dart';
import 'package:latlong2/latlong.dart';

import '../api.dart';
import '../location.dart';
import '../models.dart';

class ReportScreen extends StatefulWidget {
  const ReportScreen({super.key, this.draft});
  final ReportDraft? draft;
  @override
  State<ReportScreen> createState() => _ReportScreenState();
}

class _ReportScreenState extends State<ReportScreen> {
  final _desc = TextEditingController();
  String? _category; // null = let the AI decide
  double _urgency = 50;
  LatLng? _pos;
  Uint8List? _photo;
  bool _sending = false, _triaging = false;
  Map<String, dynamic>? _aiHint;

  @override
  void initState() {
    super.initState();
    final d = widget.draft;
    if (d != null) {
      _desc.text = d.description;
      _category = d.category;
      _urgency = d.urgency.toDouble();
      _pos = d.pos;
    }
    if (_pos == null) currentPosition().then((p) => mounted ? setState(() => _pos ??= p ?? sfaxCenter) : null);
  }

  Future<void> _askAi() async {
    if (_desc.text.trim().length < 5) return;
    setState(() => _triaging = true);
    try {
      final t = await Api.instance.triage(_desc.text);
      setState(() {
        _aiHint = t;
        _category ??= t['category'];
        // AI can raise the urgency, never lower what the citizen chose
        final ai = (t['suggested_urgency'] as num).toDouble();
        if (ai > _urgency) _urgency = ai > 100 ? 100 : ai;
      });
    } catch (_) {
      // triage is a convenience; the server re-triages anyway
    } finally {
      if (mounted) setState(() => _triaging = false);
    }
  }

  Future<void> _pickPhoto(ImageSource src) async {
    final x = await ImagePicker().pickImage(source: src, maxWidth: 1600, imageQuality: 75);
    if (x != null) {
      final bytes = await x.readAsBytes();
      setState(() => _photo = bytes);
    }
  }

  Future<void> _submit() async {
    if (_desc.text.trim().length < 3 || _pos == null) return;
    setState(() => _sending = true);
    try {
      String? photoUrl;
      if (_photo != null) photoUrl = await Api.instance.uploadPhoto(_photo!, 'photo.jpg');
      final res = await Api.instance.createReport(
          category: _category, description: _desc.text.trim(), pos: _pos!, urgency: _urgency.round(), photoUrl: photoUrl);
      if (!mounted) return;
      await _showResult(res);
      if (mounted) Navigator.pop(context, true);
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Échec : $e')));
    } finally {
      if (mounted) setState(() => _sending = false);
    }
  }

  Future<void> _showResult(Map<String, dynamic> r) {
    final label = r['priority_label'] as String;
    final breakdown = (r['priority_breakdown'] as Map?) ?? {};
    final cost = r['cost_estimate_tnd'] as List?;
    const names = {
      'severity': 'Gravité du type',
      'citizen': 'Votre urgence',
      'criticality': 'Importance de la route',
      'crowd': 'Confirmations',
      'age': 'Ancienneté',
    };
    return showDialog(
      context: context,
      builder: (_) => AlertDialog(
        icon: Icon(r['merged_into_existing'] == true ? Icons.group_add : Icons.check_circle,
            color: priorityColor(label), size: 40),
        title: Text(r['merged_into_existing'] == true ? 'Déjà signalé — confirmation ajoutée' : 'Signalement envoyé'),
        content: SingleChildScrollView(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, mainAxisSize: MainAxisSize.min, children: [
            Text('${categoryOf(r['category']).emoji} ${categoryOf(r['category']).label} — ${r['road_name']}'),
            Text('${r['zone']}', style: Theme.of(context).textTheme.bodySmall),
            const SizedBox(height: 12),
            Text('Priorité ${priorityFr(label)} : ${r['priority_score']}/100',
                style: TextStyle(fontWeight: FontWeight.bold, color: priorityColor(label))),
            const SizedBox(height: 6),
            for (final e in breakdown.entries)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 2),
                child: Row(children: [
                  Expanded(child: Text(names[e.key] ?? e.key)),
                  SizedBox(
                      width: 90,
                      child: LinearProgressIndicator(value: (e.value['value'] as num).toDouble(), minHeight: 6)),
                  SizedBox(width: 40, child: Text('+${e.value['points']}', textAlign: TextAlign.right)),
                ]),
              ),
            const Divider(height: 20),
            Text('Transmis à : ${r['responsible_service']}'),
            Text('Délai cible : ${r['sla_hours']} h'),
            if (cost != null && cost[1] > 0) Text('Coût estimé : ${cost[0]}–${cost[1]} TND'),
          ]),
        ),
        actions: [FilledButton(onPressed: () => Navigator.pop(context), child: const Text('OK'))],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return Scaffold(
      appBar: AppBar(title: const Text('Nouveau signalement')),
      body: ListView(padding: const EdgeInsets.all(16), children: [
        Text('Décrivez le problème', style: Theme.of(context).textTheme.titleSmall),
        const SizedBox(height: 8),
        TextField(
          controller: _desc,
          minLines: 3,
          maxLines: 6,
          decoration: InputDecoration(
            hintText: 'Ex : gros trou au milieu de la route, dangereux pour les motos…\n(français, darija ou anglais)',
            suffixIcon: IconButton(
              tooltip: "Analyser avec l'IA",
              onPressed: _triaging ? null : _askAi,
              icon: _triaging
                  ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2))
                  : const Icon(Icons.auto_awesome),
            ),
          ),
          onEditingComplete: _askAi,
        ),
        if (_aiHint != null)
          Padding(
            padding: const EdgeInsets.only(top: 8),
            child: Card(
              color: _aiHint!['danger_to_people'] == true ? cs.errorContainer : cs.secondaryContainer,
              child: ListTile(
                leading: Icon(_aiHint!['danger_to_people'] == true ? Icons.warning_amber : Icons.auto_awesome),
                title: Text(_aiHint!['summary'] ?? ''),
                subtitle: Text(_aiHint!['danger_to_people'] == true
                    ? 'Danger possible pour les personnes : si urgent, appelez le 198 (Protection civile) ou le 190 (SAMU).'
                    : 'Catégorie suggérée : ${categoryOf(_aiHint!['category']).label}'),
              ),
            ),
          ),
        const SizedBox(height: 20),
        Text('Type de problème', style: Theme.of(context).textTheme.titleSmall),
        const SizedBox(height: 8),
        Wrap(spacing: 8, runSpacing: 8, children: [
          ChoiceChip(
            label: const Text('✨ Auto (IA)'),
            selected: _category == null,
            onSelected: (_) => setState(() => _category = null),
          ),
          for (final c in categories)
            ChoiceChip(
              label: Text('${c.emoji} ${c.label}'),
              selected: _category == c.key,
              onSelected: (_) => setState(() => _category = c.key),
            ),
        ]),
        const SizedBox(height: 20),
        Text('Emplacement — touchez la carte pour ajuster', style: Theme.of(context).textTheme.titleSmall),
        const SizedBox(height: 8),
        ClipRRect(
          borderRadius: BorderRadius.circular(16),
          child: SizedBox(
            height: 200,
            child: _pos == null
                ? const Center(child: CircularProgressIndicator())
                : FlutterMap(
                    options: MapOptions(
                        initialCenter: _pos!, initialZoom: 16, onTap: (_, p) => setState(() => _pos = p)),
                    children: [
                      TileLayer(
                          urlTemplate: 'https://basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png',
                          userAgentPackageName: 'tn.ecoroute.app'),
                      MarkerLayer(markers: [
                        Marker(
                            point: _pos!,
                            width: 40,
                            height: 40,
                            alignment: Alignment.topCenter,
                            child: Icon(Icons.location_pin, size: 40, color: cs.error)),
                      ]),
                    ],
                  ),
          ),
        ),
        const SizedBox(height: 20),
        Row(children: [
          Text("Niveau d'urgence", style: Theme.of(context).textTheme.titleSmall),
          const Spacer(),
          Text('${_urgency.round()} / 100', style: TextStyle(color: cs.primary, fontWeight: FontWeight.bold)),
        ]),
        Slider(value: _urgency, max: 100, divisions: 20, onChanged: (v) => setState(() => _urgency = v)),
        const SizedBox(height: 12),
        if (_photo != null)
          Stack(children: [
            ClipRRect(
                borderRadius: BorderRadius.circular(16),
                child: Image.memory(_photo!, height: 180, width: double.infinity, fit: BoxFit.cover)),
            Positioned(
                right: 4,
                top: 4,
                child: IconButton.filled(onPressed: () => setState(() => _photo = null), icon: const Icon(Icons.close))),
          ])
        else
          Row(children: [
            Expanded(
                child: OutlinedButton.icon(
                    onPressed: () => _pickPhoto(ImageSource.camera),
                    icon: const Icon(Icons.photo_camera_outlined),
                    label: const Text('Photo'))),
            const SizedBox(width: 12),
            Expanded(
                child: OutlinedButton.icon(
                    onPressed: () => _pickPhoto(ImageSource.gallery),
                    icon: const Icon(Icons.photo_library_outlined),
                    label: const Text('Galerie'))),
          ]),
        const SizedBox(height: 24),
        FilledButton.icon(
          style: FilledButton.styleFrom(minimumSize: const Size.fromHeight(54)),
          onPressed: _sending ? null : _submit,
          icon: _sending
              ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2))
              : const Icon(Icons.send),
          label: const Text('Envoyer le signalement'),
        ),
      ]),
    );
  }
}
