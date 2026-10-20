import 'package:geolocator/geolocator.dart';
import 'package:latlong2/latlong.dart';

/// Returns the device position, or null if permission/service is unavailable.
Future<LatLng?> currentPosition() async {
  try {
    if (!await Geolocator.isLocationServiceEnabled()) return null;
    var perm = await Geolocator.checkPermission();
    if (perm == LocationPermission.denied) perm = await Geolocator.requestPermission();
    if (perm == LocationPermission.denied || perm == LocationPermission.deniedForever) return null;
    final p = await Geolocator.getCurrentPosition(
        locationSettings: const LocationSettings(accuracy: LocationAccuracy.high, timeLimit: Duration(seconds: 15)));
    return LatLng(p.latitude, p.longitude);
  } catch (_) {
    return null;
  }
}
