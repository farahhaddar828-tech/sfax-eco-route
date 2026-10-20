import 'package:flutter/material.dart';

import '../api.dart';
import '../models.dart';

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key});
  @override
  State<DashboardScreen> createState() => DashboardScreenState();
}

class DashboardScreenState extends State<DashboardScreen> {
  Map<String, dynamic>? _d, _graph;
  List<dynamic> _hot = [], _health = [], _sla = [];
  String? _error;

  @override
  void initState() {
    super.initState();
    refresh();
  }

  Future<void> refresh() async {
    try {
      final api = Api.instance;
      final res = await Future.wait([api.dashboard(), api.hotspots(), api.roadHealth(), api.slaBreaches(), api.graphStats()]);
      if (!mounted) return;
      setState(() {
        _d = res[0] as Map<String, dynamic>;
        _hot = res[1] as List;
        _health = res[2] as List;
        _sla = res[3] as List;
        _graph = res[4] as Map<String, dynamic>;
        _error = null;
      });
    } catch (e) {
      if (mounted) setState(() => _error = '$e');
    }
  }

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context).textTheme;
    final cs = Theme.of(context).colorScheme;
    return Scaffold(
      appBar: AppBar(title: const Text('Tableau de bord citoyen')),
      body: RefreshIndicator(
        onRefresh: refresh,
        child: _d == null
            ? ListView(children: [
                Padding(
                    padding: const EdgeInsets.all(32),
                    child: Center(child: _error != null ? Text(_error!) : const CircularProgressIndicator())),
              ])
            : ListView(padding: const EdgeInsets.fromLTRB(16, 8, 16, 100), children: [
                Row(children: [
                  _kpi('${_d!['open']}', 'Ouverts', cs.primary),
                  _kpi('${_d!['urgent']}', 'Urgents', priorityColor('critical')),
                  _kpi('${_d!['sla_breached']}', 'Hors délai', priorityColor('high')),
                ]),
                Row(children: [
                  _kpi('${_d!['resolved']}', 'Résolus', priorityColor('low')),
                  _kpi(_d!['mean_time_to_resolve_h'] == null ? '–' : '${_d!['mean_time_to_resolve_h']} h',
                      'Délai moyen', cs.secondary),
                  _kpi('${_d!['urgent_rate_pct']} %', "Taux d'urgence", cs.tertiary),
                ]),
                _section('Par catégorie', [
                  for (final e in (_d!['by_category'] as Map).entries)
                    _bar(e.value['label'], e.value['count'] as int, _d!['open'] as int),
                ]),
                _section('🔥 Zones chaudes (clusters DBSCAN)', [
                  if (_hot.isEmpty) const Text('Aucun cluster pour le moment.'),
                  for (final h in _hot.take(6))
                    ListTile(
                      contentPadding: EdgeInsets.zero,
                      leading: CircleAvatar(
                          backgroundColor: priorityColor(h['mean_priority'] >= 55 ? 'high' : 'medium'),
                          child: Text('${h['count']}', style: const TextStyle(color: Colors.white))),
                      title: Text(h['zone']),
                      subtitle: Text((h['categories'] as Map)
                          .entries
                          .map((e) => '${categoryOf(e.key).emoji} ${e.value}')
                          .join('  ')),
                      trailing: Text('P ${h['mean_priority']}'),
                    ),
                ]),
                _section('🛣️ Indice de santé des routes', [
                  if (_health.isEmpty) const Text('Aucun problème ouvert sur une route nommée.'),
                  for (final r in _health.take(8))
                    _bar('${r['road']} · ${r['open_issues']} pb', (r['health_index'] as num).round(), 100,
                        color: (r['health_index'] as num) < 50 ? priorityColor('critical') : priorityColor('low')),
                ]),
                if (_sla.isNotEmpty)
                  _section('⏱️ Délais dépassés', [
                    for (final s in _sla.take(6))
                      ListTile(
                        contentPadding: EdgeInsets.zero,
                        leading: Text(categoryOf(s['category']).emoji, style: const TextStyle(fontSize: 24)),
                        title: Text(s['road'] ?? ''),
                        subtitle: Text(s['service']),
                        trailing: Text('+${(s['remaining_hours'] as num).abs().round()} h',
                            style: TextStyle(color: priorityColor('critical'))),
                      ),
                  ]),
                if (_graph != null)
                  _section('🕸️ Réseau routier analysé', [
                    Text('${_graph!['nodes']} intersections · ${_graph!['edges']} tronçons · ${_graph!['total_km']} km'),
                    Text('${_graph!['named_roads']} routes nommées · ${_graph!['bridges']} tronçons sans alternative'),
                    Text('Redondance (nombre cyclomatique) : ${_graph!['cyclomatic_number']}', style: t.bodySmall),
                  ]),
              ]),
      ),
    );
  }

  Widget _kpi(String v, String label, Color c) => Expanded(
        child: Card(
          color: c,
          child: Padding(
            padding: const EdgeInsets.symmetric(vertical: 18, horizontal: 8),
            child: Column(children: [
              Text(v, style: const TextStyle(fontSize: 26, fontWeight: FontWeight.bold, color: Colors.white)),
              Text(label, style: const TextStyle(color: Colors.white), textAlign: TextAlign.center),
            ]),
          ),
        ),
      );

  Widget _section(String title, List<Widget> children) => Card(
        margin: const EdgeInsets.only(top: 12),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(title, style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 8),
            ...children,
          ]),
        ),
      );

  Widget _bar(String label, int value, int max, {Color? color}) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 4),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [Expanded(child: Text(label, overflow: TextOverflow.ellipsis)), Text('$value')]),
          const SizedBox(height: 4),
          LinearProgressIndicator(
              value: max == 0 ? 0 : value / max, minHeight: 8, color: color, borderRadius: BorderRadius.circular(4)),
        ]),
      );
}
