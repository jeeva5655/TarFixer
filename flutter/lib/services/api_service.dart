
import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

class ApiService {
  // Use 10.0.2.2 for Android Emulator to access localhost
  // Use your machine's IP for physical device
  // Use https://tar-fixer.vercel.app/api for production
  
  // DEVELOPMENT (Emulator):
  // static const String baseUrl = 'http://10.0.2.2:5000/api';
  
  // PRODUCTION (Vercel):
  static const String baseUrl = 'https://tar-fixer.vercel.app/api';
  
  String? _token;

  Future<String?> getToken() async {
    if (_token != null) return _token;
    final prefs = await SharedPreferences.getInstance();
    _token = prefs.getString('token');
    return _token;
  }

  Future<void> setToken(String token, String userType, String email) async {
    _token = token;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('token', token);
    await prefs.setString('user_type', userType);
    await prefs.setString('email', email);
  }

  Future<void> logout() async {
    _token = null;
    final prefs = await SharedPreferences.getInstance();
    await prefs.clear();
  }

  Future<Map<String, dynamic>> login(String email, String password) async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/auth/login'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'email': email, 'password': password}),
      );

      if (response.statusCode == 200) {
        return jsonDecode(response.body);
      } else {
        throw Exception('Login failed: ${response.statusCode} ${response.body}');
      }
    } catch (e) {
      throw Exception('Connection error: $e');
    }
  }

  Future<Map<String, dynamic>> getAdminStats() async {
    final token = await getToken();
    final response = await http.get(
      Uri.parse('$baseUrl/admin/stats'),
      headers: {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer $token',
      },
    );

    if (response.statusCode == 200) {
      return jsonDecode(response.body);
    } else {
      throw Exception('Failed to load stats: ${response.statusCode}');
    }
  }

  Future<Map<String, dynamic>> getWorkerStats() async {
    final token = await getToken();
    final response = await http.get(
      Uri.parse('$baseUrl/worker/stats'),
      headers: {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer $token',
      },
    );

    if (response.statusCode == 200) {
      return jsonDecode(response.body);
    } else {
      throw Exception('Failed to load stats: ${response.statusCode}');
    }
  }
}
