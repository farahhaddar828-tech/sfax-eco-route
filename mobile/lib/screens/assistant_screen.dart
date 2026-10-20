import 'package:flutter/material.dart';
import 'package:latlong2/latlong.dart';

import '../api.dart';
import '../location.dart';
import '../models.dart';

class AssistantScreen extends StatefulWidget {
  const AssistantScreen({super.key, required this.onUseDraft});
  final void Function(ReportDraft draft) onUseDraft;
  @override
  State<AssistantScreen> createState() => _AssistantScreenState();
}

class _Msg {
  _Msg(this.role, this.text, {this.draft, this.tools = const []});
  final String role, text;
  final ReportDraft? draft;
  final List<String> tools;
}

class _AssistantScreenState extends State<AssistantScreen> {
  final _input = TextEditingController();
  final _scroll = ScrollController();
  final List<_Msg> _msgs = [];
  bool _thinking = false;
  LatLng? _pos;

  static const _suggestions = [
    'Un câble électrique est tombé dans ma rue',
    'La route est inondée, je dois aller au centre-ville',
    'Le feu est en panne au carrefour, c\'est dangereux ?',
    'Quels problèmes sont signalés autour de moi ?',
  ];

  @override
  void initState() {
    super.initState();
    currentPosition().then((p) => _pos = p);
  }

  Future<void> _send(String text) async {
    if (text.trim().isEmpty || _thinking) return;
    _input.clear();
    setState(() {
      _msgs.add(_Msg('user', text.trim()));
      _thinking = true;
    });
    _toBottom();
    try {
      final history = [for (final m in _msgs) {'role': m.role, 'content': m.text}];
      final r = await Api.instance.chat(history, _pos);
      final draft = r['report_draft'] as Map<String, dynamic>?;
      setState(() => _msgs.add(_Msg('assistant', r['reply'] ?? '',
          draft: draft == null ? null : ReportDraft.fromJson(draft),
          tools: List<String>.from(r['tools_used'] ?? const []))));
    } catch (e) {
      setState(() => _msgs.add(_Msg('assistant', "Je n'arrive pas à joindre le serveur ($e).")));
    } finally {
      if (mounted) setState(() => _thinking = false);
      _toBottom();
    }
  }

  void _toBottom() => WidgetsBinding.instance.addPostFrameCallback((_) {
        if (_scroll.hasClients) {
          _scroll.animateTo(_scroll.position.maxScrollExtent,
              duration: const Duration(milliseconds: 250), curve: Curves.easeOut);
        }
      });

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return Scaffold(
      appBar: AppBar(title: const Text('Assistant Eco-Route')),
      body: Column(children: [
        Expanded(
          child: _msgs.isEmpty
              ? ListView(padding: const EdgeInsets.all(20), children: [
                  Icon(Icons.support_agent, size: 56, color: cs.primary),
                  const SizedBox(height: 12),
                  const Text(
                    "Décrivez ce que vous voyez. Je vous dis si c'est dangereux, qui appeler, "
                    'comment contourner, et je prépare le signalement.',
                    textAlign: TextAlign.center,
                  ),
                  const SizedBox(height: 20),
                  for (final s in _suggestions)
                    Padding(
                      padding: const EdgeInsets.only(bottom: 8),
                      child: ActionChip(label: Text(s), onPressed: () => _send(s)),
                    ),
                  const SizedBox(height: 12),
                  Text('En cas de danger immédiat : 198 Protection civile · 190 SAMU · 197 Police',
                      textAlign: TextAlign.center, style: TextStyle(color: cs.error)),
                ])
              : ListView.builder(
                  controller: _scroll,
                  padding: const EdgeInsets.all(12),
                  itemCount: _msgs.length + (_thinking ? 1 : 0),
                  itemBuilder: (_, i) {
                    if (i == _msgs.length) {
                      return const Align(
                          alignment: Alignment.centerLeft,
                          child: Padding(padding: EdgeInsets.all(12), child: CircularProgressIndicator()));
                    }
                    final m = _msgs[i];
                    final mine = m.role == 'user';
                    return Align(
                      alignment: mine ? Alignment.centerRight : Alignment.centerLeft,
                      child: Container(
                        constraints: BoxConstraints(maxWidth: MediaQuery.of(context).size.width * .82),
                        margin: const EdgeInsets.symmetric(vertical: 4),
                        padding: const EdgeInsets.all(12),
                        decoration: BoxDecoration(
                          color: mine ? cs.primary : cs.surfaceContainerHighest,
                          borderRadius: BorderRadius.circular(16),
                        ),
                        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                          SelectableText(m.text, style: TextStyle(color: mine ? cs.onPrimary : cs.onSurface)),
                          if (m.tools.isNotEmpty)
                            Padding(
                              padding: const EdgeInsets.only(top: 6),
                              child: Text('🔧 ${m.tools.toSet().join(', ')}',
                                  style: Theme.of(context).textTheme.bodySmall),
                            ),
                          if (m.draft != null)
                            Padding(
                              padding: const EdgeInsets.only(top: 8),
                              child: FilledButton.tonalIcon(
                                onPressed: () => widget.onUseDraft(m.draft!),
                                icon: const Icon(Icons.edit_note),
                                label: Text('Créer le signalement ${categoryOf(m.draft!.category ?? 'other').emoji}'),
                              ),
                            ),
                        ]),
                      ),
                    );
                  },
                ),
        ),
        SafeArea(
          top: false,
          child: Padding(
            padding: const EdgeInsets.fromLTRB(12, 4, 12, 8),
            child: Row(children: [
              Expanded(
                child: TextField(
                  controller: _input,
                  minLines: 1,
                  maxLines: 4,
                  textInputAction: TextInputAction.send,
                  onSubmitted: _send,
                  decoration: const InputDecoration(hintText: 'Votre message…', isDense: true),
                ),
              ),
              const SizedBox(width: 8),
              IconButton.filled(onPressed: () => _send(_input.text), icon: const Icon(Icons.send)),
            ]),
          ),
        ),
      ]),
    );
  }
}
