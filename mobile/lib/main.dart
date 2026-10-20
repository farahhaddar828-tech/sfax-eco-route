import 'package:flutter/material.dart';

import 'models.dart';
import 'screens/assistant_screen.dart';
import 'screens/dashboard_screen.dart';
import 'screens/map_screen.dart';
import 'screens/report_screen.dart';

void main() => runApp(const EcoRouteApp());

const brandGreen = Color(0xFF567D3A);

class EcoRouteApp extends StatelessWidget {
  const EcoRouteApp({super.key});

  ThemeData _theme(Brightness b) => ThemeData(
        useMaterial3: true,
        colorScheme: ColorScheme.fromSeed(seedColor: brandGreen, brightness: b),
        cardTheme: const CardThemeData(
          elevation: 0,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.all(Radius.circular(16))),
        ),
        inputDecorationTheme: const InputDecorationTheme(
          border: OutlineInputBorder(borderRadius: BorderRadius.all(Radius.circular(14))),
          filled: true,
        ),
      );

  @override
  Widget build(BuildContext context) => MaterialApp(
        title: 'Sfax Eco-Route',
        debugShowCheckedModeBanner: false,
        theme: _theme(Brightness.light),
        darkTheme: _theme(Brightness.dark),
        home: const Shell(),
      );
}

class Shell extends StatefulWidget {
  const Shell({super.key});
  @override
  State<Shell> createState() => _ShellState();
}

class _ShellState extends State<Shell> {
  int _tab = 0;
  final _mapKey = GlobalKey<MapScreenState>();
  final _dashKey = GlobalKey<DashboardScreenState>();

  Future<void> openReport([ReportDraft? draft]) async {
    final created = await Navigator.of(context).push<bool>(
      MaterialPageRoute(builder: (_) => ReportScreen(draft: draft)),
    );
    if (created == true) {
      _mapKey.currentState?.refresh();
      _dashKey.currentState?.refresh();
    }
  }

  @override
  Widget build(BuildContext context) {
    final pages = [
      MapScreen(key: _mapKey),
      DashboardScreen(key: _dashKey),
      AssistantScreen(onUseDraft: openReport),
    ];
    return Scaffold(
      body: IndexedStack(index: _tab, children: pages),
      floatingActionButton: _tab == 2
          ? null
          : FloatingActionButton.extended(
              onPressed: openReport,
              icon: const Icon(Icons.add_location_alt_outlined),
              label: const Text('Signaler'),
            ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _tab,
        onDestinationSelected: (i) => setState(() => _tab = i),
        destinations: const [
          NavigationDestination(icon: Icon(Icons.map_outlined), selectedIcon: Icon(Icons.map), label: 'Carte'),
          NavigationDestination(
              icon: Icon(Icons.insights_outlined), selectedIcon: Icon(Icons.insights), label: 'Tableau de bord'),
          NavigationDestination(
              icon: Icon(Icons.support_agent_outlined), selectedIcon: Icon(Icons.support_agent), label: 'Assistant'),
        ],
      ),
    );
  }
}
