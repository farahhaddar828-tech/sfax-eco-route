import 'dart:convert';
import 'dart:typed_data';

import 'package:http/http.dart' as http;
import 'package:http_parser/http_parser.dart';
import 'package:latlong2/latlong.dart';

import 'models.dart';

/// Backend URL, set at build time:
///   flutter run --dart-define=API_URL=http://10.0.2.2:8000   (Android emulator -> host)
const apiUrl = String.fromEnvironment('API_URL', defaultValue: 'http://10.0.2.2:8000');

class ApiException implements Exception {
  ApiException(this.message);
  final String message;
  @override
  String toString() => message;
}

class Api {
  Api._();
  static final Api instance = Api._();
  final _client = http.Client();

  Uri _u(String path, [Map<String, String>? q]) => Uri.parse('$apiUrl$path').replace(queryParameters: q);

  Future<dynamic> _get(String path, [Map<String, String>? q]) async {
    final r = await _client.get(_u(path, q)).timeout(const Duration(seconds: 20));
    return _decode(r);
  }

  Future<dynamic> _send(String method, String path, Object body) async {
    final req = http.Request(method, _u(path))
      ..headers['Content-Type'] = 'application/json'
      ..body = jsonEncode(body);
    final r = await http.Response.fromStream(await _client.send(req).timeout(const Duration(seconds: 60)));
    return _decode(r);
  }

  dynamic _decode(http.Response r) {
    final data = r.body.isEmpty ? null : jsonDecode(utf8.decode(r.bodyBytes));
    if (r.statusCode >= 400) {
      throw ApiException(data is Map && data['detail'] != null ? '${data['detail']}' : 'Erreur ${r.statusCode}');
    }
    return data;
  }

  // ----------------------------------------------------------------- reports
  Future<List<Report>> reports({bool openOnly = true}) async {
    final data = await _get('/api/v1/reports', {'open_only': '$openOnly', 'limit': '300'}) as List;
    return data.map((e) => Report.fromJson(e)).toList();
  }

  Future<Map<String, dynamic>> createReport({
    String? category,
    required String description,
    required LatLng pos,
    required int urgency,
    String? photoUrl,
  }) async =>
      await _send('POST', '/api/v1/reports', {
        if (category != null) 'category': category,
        'description': description,
        'lat': pos.latitude,
        'lon': pos.longitude,
        'citizen_urgency': urgency,
        if (photoUrl != null) 'photo_url': photoUrl,
      }) as Map<String, dynamic>;

  Future<void> upvote(String id) => _send('POST', '/api/v1/reports/$id/upvote', {});

  Future<String> uploadPhoto(Uint8List bytes, String filename) async {
    final req = http.MultipartRequest('POST', _u('/api/v1/reports/photos'))
      ..files.add(http.MultipartFile.fromBytes('file', bytes,
          filename: filename, contentType: MediaType('image', 'jpeg')));
    final r = await http.Response.fromStream(await req.send());
    return (_decode(r) as Map)['photo_url'] as String;
  }

  Future<Map<String, dynamic>> triage(String text) async =>
      await _send('POST', '/api/v1/assistant/triage', {'text': text}) as Map<String, dynamic>;

  // --------------------------------------------------------------- analytics
  Future<Map<String, dynamic>> dashboard() async => await _get('/api/v1/analytics/dashboard') as Map<String, dynamic>;
  Future<List<dynamic>> hotspots() async => await _get('/api/v1/analytics/hotspots') as List;
  Future<List<dynamic>> roadHealth() async => await _get('/api/v1/analytics/road-health') as List;
  Future<List<dynamic>> slaBreaches() async => await _get('/api/v1/analytics/sla-breaches') as List;

  // ------------------------------------------------------------------- graph
  Future<Map<String, dynamic>> graphStats() async => await _get('/api/v1/graph/stats') as Map<String, dynamic>;

  Future<Map<String, dynamic>> closureImpact(LatLng p) async => await _get('/api/v1/graph/closure-impact',
      {'lat': '${p.latitude}', 'lon': '${p.longitude}', 'samples': '40'}) as Map<String, dynamic>;

  Future<Map<String, dynamic>> route(LatLng a, LatLng b) async => await _send('POST', '/api/v1/graph/route', {
        'origin': [a.latitude, a.longitude],
        'destination': [b.latitude, b.longitude],
      }) as Map<String, dynamic>;

  // --------------------------------------------------------------- assistant
  Future<Map<String, dynamic>> chat(List<Map<String, String>> messages, LatLng? pos) async =>
      await _send('POST', '/api/v1/assistant/chat', {
        'messages': messages,
        if (pos != null) 'lat': pos.latitude,
        if (pos != null) 'lon': pos.longitude,
      }) as Map<String, dynamic>;
}
