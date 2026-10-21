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
