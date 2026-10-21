import 'package:flutter/material.dart';

import '../api.dart';
import '../i18n.dart';
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
    // Named `tt`, not `t`: `t` is the translation function from i18n.dart and a
    // local of the same name would shadow it everywhere in this method.
    final tt = Theme.of(context).textTheme;
    final cs = Theme.of(context).colorScheme;
    return Scaffold(
      appBar: AppBar(title: Text(t('dash.title'))),
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
                  _kpi('${_d!['open']}', t('dash.open'), cs.primary),
                  _kpi('${_d!['urgent']}', t('dash.urgent'), priorityColor('critical')),
                  _kpi('${_d!['sla_breached']}', t('dash.overdue'), priorityColor('high')),
                ]),
                Row(children: [
                  _kpi('${_d!['resolved']}', t('dash.resolved'), priorityColor('low')),
                  _kpi(_d!['mean_time_to_resolve_h'] == null ? '–' : '${_d!['mean_time_to_resolve_h']} h',
                      t('dash.meantime'), cs.secondary),
                  _kpi('${_d!['urgent_rate_pct']} %', t('dash.urgentrate'), cs.tertiary),
                ]),
                _section(Icons.donut_small_outlined, t('dash.bycategory'), [
                  // The server also sends a French `label`; the key is what the
                  // app translates, so the server's label is ignored here.
                  for (final e in (_d!['by_category'] as Map).entries)
                    _bar(catLabel(e.key), e.value['count'] as int, _d!['open'] as int,
                        icon: catIcon(e.key)),
                ]),
                _section(Icons.local_fire_department_outlined, t('dash.hotspots'), [
                  if (_hot.isEmpty) Text(t('dash.hotspots.empty')),
                  for (final h in _hot.take(6))
                    ListTile(
                      contentPadding: EdgeInsets.zero,
                      leading: CircleAvatar(
                          backgroundColor: priorityColor(h['mean_priority'] >= 55 ? 'high' : 'medium'),
                          child: Text('${h['count']}', style: const TextStyle(color: Colors.white))),
                      title: Text(h['zone']),
                      subtitle: Padding(
                        padding: const EdgeInsets.only(top: 4),
                        child: Wrap(spacing: 12, children: [
                          for (final e in (h['categories'] as Map).entries)
                            Row(mainAxisSize: MainAxisSize.min, children: [
                              Icon(catIcon(e.key), size: 15, color: cs.onSurfaceVariant),
                              const SizedBox(width: 3),
                              Text('${e.value}'),
                            ]),
                        ]),
                      ),
                      trailing: Text('P ${h['mean_priority']}'),
                    ),
                ]),
                _section(Icons.route_outlined, t('dash.roadhealth'), [
                  if (_health.isEmpty) Text(t('dash.roadhealth.empty')),
                  for (final r in _health.take(8))
                    _bar("${r['road']} · ${r['open_issues']} ${t('dash.issues.short')}",
                        (r['health_index'] as num).round(), 100,
                        color: (r['health_index'] as num) < 50 ? priorityColor('critical') : priorityColor('low')),
                ]),
                if (_sla.isNotEmpty)
                  _section(Icons.timer_outlined, t('dash.sla'), [
                    for (final s in _sla.take(6))
                      ListTile(
                        contentPadding: EdgeInsets.zero,
                        leading: Icon(catIcon(s['category']), color: priorityColor('critical')),
                        title: Text(s['road'] ?? ''),
                        subtitle: Text(s['service']),
                        trailing: Text('+${(s['remaining_hours'] as num).abs().round()} h',
                            style: TextStyle(color: priorityColor('critical'))),
                      ),
                  ]),
                if (_graph != null)
                  _section(Icons.hub_outlined, t('dash.network'), [
                    Text('${_graph!['nodes']} ${t('dash.network.nodes')} · '
                        '${_graph!['edges']} ${t('dash.network.edges')} · ${_graph!['total_km']} km'),
                    Text('${_graph!['named_roads']} ${t('dash.network.roads')} · '
                        '${_graph!['bridges']} ${t('dash.network.bridges')}'),
                    Text('${t('dash.network.redundancy')} : ${_graph!['cyclomatic_number']}', style: tt.bodySmall),
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

  /// The icon identifies the section at a glance while scrolling; it sits in
  /// the heading rather than inside the title string, so it keeps its own size
  /// and colour and never arrives as a stray glyph in a sentence.
  Widget _section(IconData icon, String title, List<Widget> children) => Card(
        margin: const EdgeInsets.only(top: 12),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Row(children: [
              Icon(icon, size: 19, color: Theme.of(context).colorScheme.primary),
              const SizedBox(width: 8),
              Expanded(child: Text(title, style: Theme.of(context).textTheme.titleMedium)),
            ]),
            const SizedBox(height: 10),
            ...children,
          ]),
        ),
      );

  Widget _bar(String label, int value, int max, {Color? color, IconData? icon}) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 4),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            if (icon != null) ...[
              Icon(icon, size: 16, color: Theme.of(context).colorScheme.onSurfaceVariant),
              const SizedBox(width: 6),
            ],
            Expanded(child: Text(label, overflow: TextOverflow.ellipsis)),
            Text('$value'),
          ]),
          const SizedBox(height: 4),
          LinearProgressIndicator(
              value: max == 0 ? 0 : value / max, minHeight: 8, color: color, borderRadius: BorderRadius.circular(4)),
        ]),
      );
}
