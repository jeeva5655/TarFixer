
import 'dart:ui';
import 'package:flutter/material.dart';
import '../services/api_service.dart';
import 'dashboard_screen.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _emailController = TextEditingController();
  final _passwordController = TextEditingController();
  final _api = ApiService();
  bool _isLoading = false;
  bool _obscurePassword = true;

  Future<void> _handleLogin() async {
    setState(() => _isLoading = true);

    try {
      final email = _emailController.text.trim();
      final password = _passwordController.text;

      if (email.isEmpty || password.isEmpty) {
        throw Exception('Please enter email and password');
      }

      final data = await _api.login(email, password);
      
      final token = data['token'];
      final userType = data['user_type'];
      
      // Store token
      await _api.setToken(token, userType, email);

      if (!mounted) return;
      
      // Navigate to Dashboard
      Navigator.pushReplacement(
        context,
        MaterialPageRoute(
          builder: (context) => DashboardScreen(userType: userType, email: email),
        ),
      );
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(e.toString().replaceAll('Exception: ', '')),
          backgroundColor: Colors.red.withOpacity(0.8),
        ),
      );
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Stack(
        fit: StackFit.expand,
        children: [
          // Background Image
          Image.asset(
            'assets/bg.jpg',
            fit: BoxFit.cover,
          ),
          
          // Dark Overlay for better contrast
          Container(
            color: Colors.black.withOpacity(0.3),
          ),

          // Content
          Center(
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(24.0),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                   // Neon "Welcome to TarFixer" Text
                  ShaderMask(
                    shaderCallback: (bounds) => const LinearGradient(
                      colors: [Colors.cyanAccent, Colors.greenAccent],
                      begin: Alignment.topLeft,
                      end: Alignment.bottomRight,
                    ).createShader(bounds),
                    child: const Text(
                      'Welcome to TarFixer',
                      textAlign: TextAlign.center,
                      style: TextStyle(
                        fontSize: 28,
                        fontWeight: FontWeight.bold,
                        color: Colors.white,
                        shadows: [
                          BoxShadow(
                            color: Colors.cyanAccent,
                            blurRadius: 10,
                            spreadRadius: 2,
                          ),
                        ],
                      ),
                    ),
                  ),
                  
                  const SizedBox(height: 40),

                  // Glassmorphism Card
                  ClipRRect(
                    borderRadius: BorderRadius.circular(20),
                    child: BackdropFilter(
                      filter: ImageFilter.blur(sigmaX: 10, sigmaY: 10),
                      child: Container(
                        padding: const EdgeInsets.all(32),
                        decoration: BoxDecoration(
                          color: Colors.black.withOpacity(0.4), // Dark translucent background
                          borderRadius: BorderRadius.circular(20),
                          border: Border.all(color: Colors.white.withOpacity(0.1)),
                          boxShadow: [
                            BoxShadow(
                              color: Colors.black.withOpacity(0.2),
                              blurRadius: 20,
                              spreadRadius: 5,
                            ),
                          ],
                        ),
                        child: Column(
                          children: [
                            const Text(
                              'Sign In',
                              style: TextStyle(
                                fontSize: 24,
                                fontWeight: FontWeight.bold,
                                color: Colors.white,
                              ),
                            ),
                            const SizedBox(height: 24),
                            
                            // Email Field
                            _buildTextField(
                              controller: _emailController,
                              hintText: 'Email address',
                              icon: Icons.email_outlined,
                            ),
                            const SizedBox(height: 16),
                            
                            // Password Field
                            _buildTextField(
                              controller: _passwordController,
                              hintText: 'Password',
                              icon: Icons.lock_outline,
                              isPassword: true,
                              obscureText: _obscurePassword,
                              onToggleVisibility: () {
                                setState(() {
                                  _obscurePassword = !_obscurePassword;
                                });
                              },
                            ),
                            
                            Align(
                              alignment: Alignment.centerRight,
                              child: TextButton(
                                onPressed: () {}, // TODO: Implement Forgot Password
                                child: const Text(
                                  'Forgot Password?',
                                  style: TextStyle(color: Colors.white70, fontSize: 12),
                                ),
                              ),
                            ),

                            const SizedBox(height: 16),

                            // Sign In Button
                            SizedBox(
                              width: double.infinity,
                              height: 48,
                              child: ElevatedButton(
                                onPressed: _isLoading ? null : _handleLogin,
                                style: ElevatedButton.styleFrom(
                                  backgroundColor: Colors.white,
                                  foregroundColor: Colors.black,
                                  shape: RoundedRectangleBorder(
                                    borderRadius: BorderRadius.circular(8),
                                  ),
                                ),
                                child: _isLoading
                                    ? const SizedBox(
                                        height: 24, width: 24,
                                        child: CircularProgressIndicator(strokeWidth: 2, color: Colors.black),
                                      )
                                    : const Text('Sign In', style: TextStyle(fontWeight: FontWeight.bold)),
                              ),
                            ),

                            const SizedBox(height: 16),
                            const Text('OR', style: TextStyle(color: Colors.white60, fontSize: 12)),
                            const SizedBox(height: 16),

                            // Google Sign In Button (Mock)
                            SizedBox(
                              width: double.infinity,
                              height: 48,
                              child: ElevatedButton.icon(
                                onPressed: () {}, // Not implemented in Flutter demo
                                icon: const Icon(Icons.g_mobiledata, size: 28, color: Colors.red), 
                                label: const Text('Continue with Google'),
                                style: ElevatedButton.styleFrom(
                                  backgroundColor: Colors.white,
                                  foregroundColor: Colors.black,
                                  shape: RoundedRectangleBorder(
                                    borderRadius: BorderRadius.circular(8),
                                  ),
                                ),
                              ),
                            ),
                             
                            const SizedBox(height: 16),
                            
                            const Text(
                               'Google Sign-In is for Public Users only.\nOfficers & Workers use email/password.',
                               textAlign: TextAlign.center,
                               style: TextStyle(fontSize: 10, color: Colors.white54),
                             ),

                          ],
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildTextField({
    required TextEditingController controller,
    required String hintText,
    required IconData icon,
    bool isPassword = false,
    bool obscureText = false,
    VoidCallback? onToggleVisibility,
  }) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(hintText, style: const TextStyle(color: Colors.white70, fontSize: 12)),
        const SizedBox(height: 4),
        TextField(
          controller: controller,
          obscureText: obscureText,
          style: const TextStyle(color: Colors.black87),
          decoration: InputDecoration(
            hintText: hintText,
            hintStyle: TextStyle(color: Colors.grey[500]),
            fillColor: const Color(0xFFF0F0F0), // Light grey/white background
            filled: true,
            contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
            border: OutlineInputBorder(
              borderRadius: BorderRadius.circular(8),
              borderSide: BorderSide.none,
            ),
            suffixIcon: isPassword
                ? IconButton(
                    icon: Icon(
                      obscureText ? Icons.visibility_off : Icons.visibility,
                      color: Colors.grey,
                    ),
                    onPressed: onToggleVisibility,
                  )
                : null,
          ),
        ),
      ],
    );
  }
}
