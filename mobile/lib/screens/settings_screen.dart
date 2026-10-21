import 'package:flutter/material.dart';

import '../i18n.dart';
import '../settings.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  late final TextEditingController _server =
      TextEditingController(text: Settings.instance.serverUrl);

  @override
  void dispose() {
    _server.dispose();
    super.dispose();
  }

  Future<void> _saveServer() async {
    await Settings.instance.setServerUrl(_server.text);
    if (!mounted) return;
    FocusScope.of(context).unfocus();
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(t('settings.server.saved'))),
    );
  }

  @override
  Widget build(BuildContext context) {
    final s = Settings.instance;
    final text = Theme.of(context).textTheme;
    return Scaffold(
      appBar: AppBar(title: Text(t('settings.title'))),
      body: ListView(padding: const EdgeInsets.all(16), children: [
        Text(t('settings.language'), style: text.titleMedium),
        Text(t('settings.language.hint'), style: text.bodySmall),
        const SizedBox(height: 8),
        SegmentedButton<String>(
          segments: [
            for (final e in languageNames.entries)
              ButtonSegment(value: e.key, label: Text(e.value)),
          ],
          selected: {s.language},
          onSelectionChanged: (sel) => s.setLanguage(sel.first),
        ),
        const SizedBox(height: 28),

        Text(t('settings.theme'), style: text.titleMedium),
        const SizedBox(height: 8),
        SegmentedButton<ThemeMode>(
          segments: [
            ButtonSegment(value: ThemeMode.system, label: Text(t('settings.theme.system'))),
            ButtonSegment(value: ThemeMode.light, label: Text(t('settings.theme.light'))),
            ButtonSegment(value: ThemeMode.dark, label: Text(t('settings.theme.dark'))),
          ],
          selected: {s.themeMode},
          onSelectionChanged: (sel) => s.setThemeMode(sel.first),
        ),
        const SizedBox(height: 28),

        Text(t('settings.server'), style: text.titleMedium),
        Text(t('settings.server.hint'), style: text.bodySmall),
        const SizedBox(height: 8),
        TextField(
          controller: _server,
          keyboardType: TextInputType.url,
          autocorrect: false,
          textInputAction: TextInputAction.done,
          onSubmitted: (_) => _saveServer(),
          decoration: InputDecoration(
            hintText: t('settings.server.example'),
            prefixIcon: const Icon(Icons.dns_outlined),
            suffixIcon: IconButton(
              icon: const Icon(Icons.check),
              tooltip: t('action.save'),
              onPressed: _saveServer,
            ),
          ),
        ),
        const SizedBox(height: 28),

        const Divider(),
        const SizedBox(height: 12),
        Text(t('settings.about'), style: text.titleMedium),
        const SizedBox(height: 4),
        Text(t('settings.about.body'), style: text.bodyMedium),
      ]),
    );
  }
}
