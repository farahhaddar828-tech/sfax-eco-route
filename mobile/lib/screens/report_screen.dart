import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:image_picker/image_picker.dart';
import 'package:latlong2/latlong.dart';

import '../api.dart';
import '../i18n.dart';
import '../location.dart';
import '../settings.dart';
import '../models.dart';
import 'pick_location.dart';

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
      final t = await Api.instance.triage(_desc.text, lang: Settings.instance.language);
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

  Future<void> _pickLocation() async {
    final picked = await Navigator.of(context).push<LatLng>(
      MaterialPageRoute(builder: (_) => PickLocationScreen(initial: _pos ?? sfaxCenter)),
    );
    if (picked != null && mounted) setState(() => _pos = picked);
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
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('${t('report.failed')} : $e')));
    } finally {
      if (mounted) setState(() => _sending = false);
    }
  }

  Future<void> _showResult(Map<String, dynamic> r) {
    final label = r['priority_label'] as String;
    final breakdown = (r['priority_breakdown'] as Map?) ?? {};
    final cost = r['cost_estimate_tnd'] as List?;
    return showDialog(
      context: context,
      builder: (_) => AlertDialog(
        icon: Icon(r['merged_into_existing'] == true ? Icons.group_add : Icons.check_circle,
            color: priorityColor(label), size: 40),
        title: Text(t(r['merged_into_existing'] == true ? 'report.result.merged' : 'report.result.sent')),
        content: SingleChildScrollView(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, mainAxisSize: MainAxisSize.min, children: [
            Row(children: [
              Icon(catIcon(r['category']), size: 18, color: priorityColor(label)),
              const SizedBox(width: 8),
              Expanded(child: Text('${catLabel(r['category'])} — ${bidi(r['road_name'])}')),
            ]),
            Text(bidi(r['zone']), style: Theme.of(context).textTheme.bodySmall),
            const SizedBox(height: 12),
            Text('${t('report.result.priority')} ${priorityText(label)} : ${r['priority_score']}/100',
                style: TextStyle(fontWeight: FontWeight.bold, color: priorityColor(label))),
            const SizedBox(height: 6),
            for (final e in breakdown.entries)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 2),
                child: Row(children: [
                  Expanded(child: Text(t('factor.${e.key}'))),
                  SizedBox(
                      width: 90,
                      child: LinearProgressIndicator(value: (e.value['value'] as num).toDouble(), minHeight: 6)),
                  SizedBox(width: 40, child: Text('+${e.value['points']}', textAlign: TextAlign.right)),
                ]),
              ),
            const Divider(height: 20),
            Text('${t('report.result.service')} : ${bidi(r['responsible_service'])}'),
            Text('${t('report.result.sla')} : ${r['sla_hours']} h'),
            if (cost != null && cost[1] > 0)
              Text('${t('report.result.cost')} : ${cost[0]}–${cost[1]} TND'),
          ]),
        ),
        actions: [FilledButton(onPressed: () => Navigator.pop(context), child: Text(t('action.ok')))],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return Scaffold(
      appBar: AppBar(title: Text(t('report.title'))),
      body: ListView(padding: const EdgeInsets.all(16), children: [
        Text(t('report.describe'), style: Theme.of(context).textTheme.titleSmall),
        const SizedBox(height: 8),
        TextField(
          controller: _desc,
          minLines: 3,
          maxLines: 6,
          decoration: InputDecoration(
            hintText: t('report.hint'),
            suffixIcon: IconButton(
              tooltip: t('report.analyze'),
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
                    ? t('report.ai.danger')
                    : "${t('report.ai.suggested')} : ${catLabel(_aiHint!['category'])}"),
              ),
            ),
          ),
        const SizedBox(height: 20),
        Text(t('report.type'), style: Theme.of(context).textTheme.titleSmall),
        const SizedBox(height: 8),
        // The icon goes in the chip's avatar slot rather than into the label
        // string: Material then sizes and tints it with the chip's selected
        // state, and it cannot be mistaken for part of the text.
        Wrap(spacing: 8, runSpacing: 8, children: [
          ChoiceChip(
            avatar: const Icon(Icons.auto_awesome, size: 18),
            label: Text(t('report.auto')),
            selected: _category == null,
            onSelected: (_) => setState(() => _category = null),
          ),
          for (final c in categories)
            ChoiceChip(
              avatar: Icon(c.icon, size: 18),
              label: Text(catLabel(c.key)),
              selected: _category == c.key,
              onSelected: (_) => setState(() => _category = c.key),
            ),
        ]),
        const SizedBox(height: 20),
        Text(t('report.location'), style: Theme.of(context).textTheme.titleSmall),
        const SizedBox(height: 8),
        InkWell(
          borderRadius: BorderRadius.circular(16),
          onTap: _pos == null ? null : _pickLocation,
          child: ClipRRect(
            borderRadius: BorderRadius.circular(16),
            child: SizedBox(
              height: 200,
              child: _pos == null
                  ? const Center(child: CircularProgressIndicator())
                  : Stack(children: [
                      // Preview only. Tapping opens the full-screen picker, which has a
                      // search bar and a centred pin - this 200 px map was unusable for
                      // actually choosing a point.
                      AbsorbPointer(
                        child: FlutterMap(
                          // initialCenter only applies on first build, so rebuild the
                          // preview whenever the chosen point changes
                          key: ValueKey('${_pos!.latitude},${_pos!.longitude}'),
                          options: MapOptions(initialCenter: _pos!, initialZoom: 16),
                          children: [
                            TileLayer(
                                urlTemplate: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
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
                      Positioned(
                        left: 8,
                        right: 8,
                        bottom: 8,
                        child: FilledButton.tonalIcon(
                          onPressed: _pickLocation,
                          icon: const Icon(Icons.search),
                          label: Text(t('report.location.search')),
                        ),
                      ),
                    ]),
            ),
          ),
        ),
        const SizedBox(height: 20),
        Row(children: [
          Text(t('report.urgency'), style: Theme.of(context).textTheme.titleSmall),
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
                    label: Text(t('report.photo')))),
            const SizedBox(width: 12),
            Expanded(
                child: OutlinedButton.icon(
                    onPressed: () => _pickPhoto(ImageSource.gallery),
                    icon: const Icon(Icons.photo_library_outlined),
                    label: Text(t('report.gallery')))),
          ]),
        const SizedBox(height: 24),
        FilledButton.icon(
          style: FilledButton.styleFrom(minimumSize: const Size.fromHeight(54)),
          onPressed: _sending ? null : _submit,
          icon: _sending
              ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2))
              : const Icon(Icons.send),
          label: Text(t('report.submit')),
        ),
      ]),
    );
  }
}
