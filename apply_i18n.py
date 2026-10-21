"""Apply the settings + localisation slice to Eco-Route.

Run with:  py apply_i18n.py
Idempotent - re-running reports what is already applied rather than failing.
"""
import pathlib, sys

ROOT = pathlib.Path(r"C:\dev\eco-route")

NEW_FILES = {
    "mobile/lib/settings.dart": """\
import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'api.dart';

/// App-wide settings, persisted on the device.
///
/// A plain [ChangeNotifier] rather than a state-management package: there are
/// three values and one listener (the root widget), so anything bigger would be
/// scaffolding for its own sake.
class Settings extends ChangeNotifier {
  Settings._();

  static final Settings instance = Settings._();

  static const _kLang = 'lang';
  static const _kTheme = 'theme';
  static const _kServer = 'server';

  /// 'fr' | 'en' | 'ar'. Arabic also flips the whole layout right-to-left,
  /// which Flutter handles once the locale is set on MaterialApp.
  String language = 'fr';
  ThemeMode themeMode = ThemeMode.system;

  /// Overrides the API_URL compiled in at build time. Without this, every change
  /// of the PC's IP address means rebuilding and reinstalling the APK.
  String serverUrl = '';

  SharedPreferences? _prefs;

  Future<void> load() async {
    _prefs = await SharedPreferences.getInstance();
    language = _prefs?.getString(_kLang) ?? 'fr';
    final t = _prefs?.getString(_kTheme);
    themeMode = t == 'light'
        ? ThemeMode.light
        : t == 'dark'
            ? ThemeMode.dark
            : ThemeMode.system;
    serverUrl = _prefs?.getString(_kServer) ?? '';
    applyServerUrl();
  }

  Locale get locale => Locale(language);

  bool get isRtl => language == 'ar';

  /// Point the API client at the configured server, or back at the build-time default.
  void applyServerUrl() => setApiBase(serverUrl.trim().isEmpty ? null : serverUrl.trim());

  Future<void> setLanguage(String code) async {
    if (language == code) return;
    language = code;
    await _prefs?.setString(_kLang, code);
    notifyListeners();
  }

  Future<void> setThemeMode(ThemeMode mode) async {
    if (themeMode == mode) return;
    themeMode = mode;
    await _prefs?.setString(
        _kTheme,
        mode == ThemeMode.light
            ? 'light'
            : mode == ThemeMode.dark
                ? 'dark'
                : 'system');
    notifyListeners();
  }

  Future<void> setServerUrl(String url) async {
    serverUrl = url.trim();
    await _prefs?.setString(_kServer, serverUrl);
    applyServerUrl();
    notifyListeners();
  }
}
""",
    "mobile/lib/i18n.dart": """\
import 'settings.dart';

/// Minimal string table for French, English and Tunisian-facing Arabic.
///
/// Deliberately a plain map rather than ARB files with code generation: no
/// build_runner step, no generated sources in the repo, and adding a language is
/// one more entry. If this grows past a few hundred keys, move to ARB.
///
/// Keys missing from a language fall back to French, so a partial translation
/// degrades to something readable instead of showing the raw key.
const Map<String, Map<String, String>> _strings = {
  'fr': {
    'app.title': 'Sfax Eco-Route',
    'tab.map': 'Carte',
    'tab.dashboard': 'Tableau de bord',
    'tab.assistant': 'Assistant',
    'action.report': 'Signaler',
    'action.refresh': 'Actualiser',
    'action.save': 'Enregistrer',
    'action.cancel': 'Annuler',
    'settings.title': 'Paramètres',
    'settings.language': 'Langue',
    'settings.language.hint': "Change la langue de l'application et des réponses de l'assistant",
    'settings.theme': 'Thème',
    'settings.theme.system': 'Système',
    'settings.theme.light': 'Clair',
    'settings.theme.dark': 'Sombre',
    'settings.server': 'Adresse du serveur',
    'settings.server.hint': 'Laissez vide pour utiliser le serveur par défaut',
    'settings.server.example': 'ex. http://192.168.0.26:8000',
    'settings.server.saved': 'Adresse du serveur enregistrée',
    'settings.about': 'À propos',
    'settings.about.body':
        'Projet personnel. Les signalements sont rattachés au réseau routier réel de Grand Sfax '
            '(OpenStreetMap) et classés par un modèle de priorité explicable.',
  },
  'en': {
    'app.title': 'Sfax Eco-Route',
    'tab.map': 'Map',
    'tab.dashboard': 'Dashboard',
    'tab.assistant': 'Assistant',
    'action.report': 'Report',
    'action.refresh': 'Refresh',
    'action.save': 'Save',
    'action.cancel': 'Cancel',
    'settings.title': 'Settings',
    'settings.language': 'Language',
    'settings.language.hint': "Changes the app's language and the assistant's replies",
    'settings.theme': 'Theme',
    'settings.theme.system': 'System',
    'settings.theme.light': 'Light',
    'settings.theme.dark': 'Dark',
    'settings.server': 'Server address',
    'settings.server.hint': 'Leave empty to use the default server',
    'settings.server.example': 'e.g. http://192.168.0.26:8000',
    'settings.server.saved': 'Server address saved',
    'settings.about': 'About',
    'settings.about.body':
        'Personal project. Reports are snapped onto the real Grand Sfax road network '
            '(OpenStreetMap) and ranked by an explainable priority model.',
  },
  'ar': {
    'app.title': 'صفاقس إيكو-روت',
    'tab.map': 'الخريطة',
    'tab.dashboard': 'لوحة المتابعة',
    'tab.assistant': 'المساعد',
    'action.report': 'الإبلاغ',
    'action.refresh': 'تحديث',
    'action.save': 'حفظ',
    'action.cancel': 'إلغاء',
    'settings.title': 'الإعدادات',
    'settings.language': 'اللغة',
    'settings.language.hint': 'تغيّر لغة التطبيق وردود المساعد',
    'settings.theme': 'المظهر',
    'settings.theme.system': 'حسب النظام',
    'settings.theme.light': 'فاتح',
    'settings.theme.dark': 'داكن',
    'settings.server': 'عنوان الخادم',
    'settings.server.hint': 'اتركه فارغًا لاستعمال الخادم الافتراضي',
    'settings.server.example': 'مثال: http://192.168.0.26:8000',
    'settings.server.saved': 'تم حفظ عنوان الخادم',
    'settings.about': 'حول التطبيق',
    'settings.about.body':
        'مشروع شخصي. تُسقط البلاغات على شبكة الطرقات الحقيقية لصفاقس الكبرى '
            '(OpenStreetMap) وتُرتّب حسب نموذج أولوية قابل للتفسير.',
  },
};

/// Look up a translated string for the currently selected language.
String t(String key) {
  final lang = Settings.instance.language;
  return _strings[lang]?[key] ?? _strings['fr']?[key] ?? key;
}

/// The languages offered in Settings, each labelled in its own language.
const languageNames = {'fr': 'Français', 'en': 'English', 'ar': 'العربية'};
""",
    "mobile/lib/screens/settings_screen.dart": """\
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
""",
}

PATCHES = [
    ("pubspec: flutter_localizations", "mobile/pubspec.yaml",
     "dependencies:\n  flutter:\n    sdk: flutter\n  flutter_map: ^7.0.2",
     "dependencies:\n  flutter:\n    sdk: flutter\n  flutter_localizations:\n    sdk: flutter\n  flutter_map: ^7.0.2"),
    ("pubspec: shared_preferences", "mobile/pubspec.yaml",
     "  image_picker: ^1.1.2",
     "  image_picker: ^1.1.2\n  shared_preferences: ^2.3.2"),
    ("api: overridable base URL", "mobile/lib/api.dart",
     "const apiUrl = String.fromEnvironment('API_URL', defaultValue: 'http://10.0.2.2:8000');",
     "const _buildTimeApiUrl = String.fromEnvironment('API_URL', defaultValue: 'http://10.0.2.2:8000');\n\n/// Base URL actually used for requests. Settings can override the build-time\n/// value, so a change of the server's IP no longer means rebuilding the APK.\nString apiUrl = _buildTimeApiUrl;\n\n/// Pass null or an empty string to fall back to the build-time URL.\nvoid setApiBase(String? url) =>\n    apiUrl = (url == null || url.isEmpty) ? _buildTimeApiUrl : url;"),
    ("api: lang on chat", "mobile/lib/api.dart",
     "  Future<Map<String, dynamic>> chat(List<Map<String, String>> messages, LatLng? pos) async =>\n      await _send('POST', '/api/v1/assistant/chat', {\n        'messages': messages,\n        if (pos != null) 'lat': pos.latitude,\n        if (pos != null) 'lon': pos.longitude,\n      }) as Map<String, dynamic>;",
     "  /// [lang] is the language chosen in Settings: the backend pins the assistant's\n  /// reply to it rather than inferring it from the question.\n  Future<Map<String, dynamic>> chat(List<Map<String, String>> messages, LatLng? pos,\n          {String? lang}) async =>\n      await _send('POST', '/api/v1/assistant/chat', {\n        'messages': messages,\n        if (pos != null) 'lat': pos.latitude,\n        if (pos != null) 'lon': pos.longitude,\n        if (lang != null) 'lang': lang,\n      }) as Map<String, dynamic>;"),
    ("assistant screen: import settings", "mobile/lib/screens/assistant_screen.dart",
     "import '../api.dart';",
     "import '../api.dart';\nimport '../settings.dart';"),
    ("assistant screen: send the language", "mobile/lib/screens/assistant_screen.dart",
     "final r = await Api.instance.chat(history, _pos);",
     "final r = await Api.instance.chat(history, _pos, lang: Settings.instance.language);"),
    ("main: imports", "mobile/lib/main.dart",
     "import 'package:flutter/material.dart';\n\nimport 'models.dart';",
     "import 'package:flutter/material.dart';\nimport 'package:flutter_localizations/flutter_localizations.dart';\n\nimport 'i18n.dart';\nimport 'models.dart';"),
    ("main: boot and settings route", "mobile/lib/main.dart",
     "import 'screens/report_screen.dart';\n\nvoid main() => runApp(const EcoRouteApp());",
     "import 'screens/report_screen.dart';\nimport 'screens/settings_screen.dart';\nimport 'settings.dart';\n\nFuture<void> main() async {\n  WidgetsFlutterBinding.ensureInitialized();\n  await Settings.instance.load();\n  runApp(const EcoRouteApp());\n}"),
    ("main: locale and theme mode", "mobile/lib/main.dart",
     "  @override\n  Widget build(BuildContext context) => MaterialApp(\n        title: 'Sfax Eco-Route',\n        debugShowCheckedModeBanner: false,\n        theme: _theme(Brightness.light),\n        darkTheme: _theme(Brightness.dark),\n        home: const Shell(),\n      );",
     "  @override\n  Widget build(BuildContext context) => AnimatedBuilder(\n        // Rebuild the whole app when the language or theme changes. Setting\n        // `locale` is what flips Arabic to a right-to-left layout.\n        animation: Settings.instance,\n        builder: (_, __) => MaterialApp(\n          title: t('app.title'),\n          debugShowCheckedModeBanner: false,\n          theme: _theme(Brightness.light),\n          darkTheme: _theme(Brightness.dark),\n          themeMode: Settings.instance.themeMode,\n          locale: Settings.instance.locale,\n          supportedLocales: const [Locale('fr'), Locale('en'), Locale('ar')],\n          localizationsDelegates: const [\n            GlobalMaterialLocalizations.delegate,\n            GlobalWidgetsLocalizations.delegate,\n            GlobalCupertinoLocalizations.delegate,\n          ],\n          home: const Shell(),\n        ),\n      );"),
    ("main: translate the FAB", "mobile/lib/main.dart",
     "              icon: const Icon(Icons.add_location_alt_outlined),\n              label: const Text('Signaler'),",
     "              icon: const Icon(Icons.add_location_alt_outlined),\n              label: Text(t('action.report')),"),
    ("main: translate the tabs", "mobile/lib/main.dart",
     "        destinations: const [\n          NavigationDestination(icon: Icon(Icons.map_outlined), selectedIcon: Icon(Icons.map), label: 'Carte'),\n          NavigationDestination(\n              icon: Icon(Icons.insights_outlined), selectedIcon: Icon(Icons.insights), label: 'Tableau de bord'),\n          NavigationDestination(\n              icon: Icon(Icons.support_agent_outlined), selectedIcon: Icon(Icons.support_agent), label: 'Assistant'),\n        ],",
     "        destinations: [\n          NavigationDestination(\n              icon: const Icon(Icons.map_outlined), selectedIcon: const Icon(Icons.map), label: t('tab.map')),\n          NavigationDestination(\n              icon: const Icon(Icons.insights_outlined),\n              selectedIcon: const Icon(Icons.insights),\n              label: t('tab.dashboard')),\n          NavigationDestination(\n              icon: const Icon(Icons.support_agent_outlined),\n              selectedIcon: const Icon(Icons.support_agent),\n              label: t('tab.assistant')),\n        ],"),
    ("map screen: imports", "mobile/lib/screens/map_screen.dart",
     "import '../api.dart';",
     "import '../api.dart';\nimport '../i18n.dart';"),
    ("map screen: settings route import", "mobile/lib/screens/map_screen.dart",
     "import '../models.dart';",
     "import '../models.dart';\nimport 'settings_screen.dart';"),
    ("map screen: settings button", "mobile/lib/screens/map_screen.dart",
     "        title: const Text('Sfax Eco-Route'),\n        actions: [IconButton(onPressed: refresh, icon: const Icon(Icons.refresh), tooltip: 'Actualiser')],",
     "        title: Text(t('app.title')),\n        actions: [\n          IconButton(onPressed: refresh, icon: const Icon(Icons.refresh), tooltip: t('action.refresh')),\n          IconButton(\n            onPressed: () => Navigator.of(context)\n                .push(MaterialPageRoute(builder: (_) => const SettingsScreen())),\n            icon: const Icon(Icons.settings_outlined),\n            tooltip: t('settings.title'),\n          ),\n        ],"),
    ("backend: lang on ChatRequest", "backend/app/schemas.py",
     "class ChatRequest(BaseModel):\n    messages: list[ChatMessage]\n    lat: float | None = None\n    lon: float | None = None",
     "class ChatRequest(BaseModel):\n    messages: list[ChatMessage]\n    lat: float | None = None\n    lon: float | None = None\n    # UI language chosen in Settings: pins the reply language instead of letting\n    # the model guess from the question.\n    lang: str | None = Field(None, max_length=8)"),
    ("backend: language clause", "backend/app/ai/assistant.py",
     "async def ask(db: Session, history: list[dict], user_pos: tuple[float, float] | None) -> AgentResult:\n    llm = LLM()\n    tools = build_tools(db, user_pos)\n    if llm.enabled:\n        try:\n            ctx = f\"\\nPosition de l'utilisateur : {user_pos}.\" if user_pos else \"\"\n            return await llm.run_agent(SYSTEM_PROMPT + ctx, history, tools)",
     "LANGUAGE_NAMES = {\"fr\": \"francais\", \"en\": \"anglais\", \"ar\": \"arabe\"}\n\n\ndef language_clause(lang: str | None) -> str:\n    \"\"\"Pin the reply language when the user picked one in the app's settings.\n\n    Without this the prompt only says 'answer in the user's language', which a\n    small model reads off the question rather than off the chosen setting.\n    \"\"\"\n    name = LANGUAGE_NAMES.get((lang or \"\").strip().lower())\n    if not name:\n        return \"\"\n    return (f\"\\nL'utilisateur a choisi la langue: {name}. Reponds UNIQUEMENT en {name}, \"\n            \"quelle que soit la langue de sa question.\")\n\n\nasync def ask(db: Session, history: list[dict], user_pos: tuple[float, float] | None,\n              lang: str | None = None) -> AgentResult:\n    llm = LLM()\n    tools = build_tools(db, user_pos)\n    if llm.enabled:\n        try:\n            ctx = f\"\\nPosition de l'utilisateur : {user_pos}.\" if user_pos else \"\"\n            return await llm.run_agent(SYSTEM_PROMPT + ctx + language_clause(lang), history, tools)"),
    ("backend: pass lang through", "backend/app/api/assistant.py",
     "res = await assistant.ask(db, [m.model_dump() for m in body.messages[-12:]], pos)",
     "res = await assistant.ask(db, [m.model_dump() for m in body.messages[-12:]], pos, body.lang)"),
]

APPEND = [
    ("backend/tests/test_hardening.py", "\n\ndef test_language_clause_pins_the_chosen_language():\n    from app.ai.assistant import language_clause\n\n    assert \"arabe\" in language_clause(\"ar\")\n    assert \"anglais\" in language_clause(\"en\")\n    assert \"UNIQUEMENT\" in language_clause(\"fr\")\n\n\ndef test_language_clause_is_empty_when_nothing_is_chosen():\n    from app.ai.assistant import language_clause\n\n    for value in (None, \"\", \"   \", \"klingon\"):\n        assert language_clause(value) == \"\"\n\n\ndef test_chat_accepts_a_language(client):\n    r = client.post(\"/api/v1/assistant/chat\",\n                    json={\"messages\": [{\"role\": \"user\", \"content\": \"bonjour\"}], \"lang\": \"ar\"})\n    assert r.status_code == 200, r.text\n"),
]


def main() -> int:
    for rel, body in NEW_FILES.items():
        p = ROOT / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8", newline="\n")
        print("  wrote:", rel)
    for label, rel, old, new in PATCHES:
        p = ROOT / rel
        if not p.exists():
            print("  MISSING FILE:", rel); return 1
        t = p.read_text(encoding="utf-8")
        if new in t:
            print("  already applied:", label); continue
        n = t.count(old)
        if n != 1:
            print(f"  FAILED ({n} matches, expected 1): {label}"); return 1
        p.write_text(t.replace(old, new, 1), encoding="utf-8", newline="\n")
        print("  ok:", label)
    for rel, body in APPEND:
        p = ROOT / rel
        t = p.read_text(encoding="utf-8")
        if body.strip().splitlines()[0] in t:
            print("  already appended:", rel); continue
        p.write_text(t.rstrip("\n") + "\n" + body, encoding="utf-8", newline="\n")
        print("  appended:", rel)
    print("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
