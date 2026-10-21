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
