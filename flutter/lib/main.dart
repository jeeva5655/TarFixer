
import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'screens/login_screen.dart';
import 'screens/dashboard_screen.dart';
import 'services/api_service.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  
  final prefs = await SharedPreferences.getInstance();
  final token = prefs.getString('token');
  final userType = prefs.getString('user_type');
  final email = prefs.getString('email');

  runApp(TarFixerApp(
    initialRoute: token != null && userType != null ? '/dashboard' : '/login',
    userType: userType,
    email: email
  ));
}

class TarFixerApp extends StatelessWidget {
  final String initialRoute;
  final String? userType;
  final String? email;

  const TarFixerApp({super.key, required this.initialRoute, this.userType, this.email});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'TarFixer',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        primarySwatch: Colors.blue,
        useMaterial3: true,
        scaffoldBackgroundColor: Colors.grey[100],
        appBarTheme: const AppBarTheme(
          centerTitle: true,
          elevation: 0,
          backgroundColor: Colors.white,
          foregroundColor: Colors.black,
        ),
      ),
      home: initialRoute == '/dashboard' 
          ? DashboardScreen(userType: userType!, email: email!) 
          : const LoginScreen(),
    );
  }
}
