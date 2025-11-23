import 'package:coingraze/colors.dart';
import 'package:flutter/material.dart';

class GrainNotificationScreen extends StatelessWidget {
  final int gained;
  final int total;

  const GrainNotificationScreen({
    super.key,
    required this.gained,
    required this.total,
  });

  void _goToDiscover(BuildContext context) {
    // Pop all overlays and return to the main tabs (Discover tab is index 0).
    Navigator.of(context).pushNamedAndRemoveUntil('/', (route) => false);
  }

  @override
  Widget build(BuildContext context) {
    return WillPopScope(
      onWillPop: () async {
        _goToDiscover(context);
        return false;
      },
      child: GestureDetector(
        behavior: HitTestBehavior.deferToChild,
        onTap: () => _goToDiscover(context),
        child: Scaffold(
          backgroundColor: AppColors.organge.withOpacity(0.85),
          appBar: AppBar(backgroundColor: Colors.transparent, elevation: 0),
          body: SafeArea(
            child: Center(
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 24.0),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(
                      'Grain Added!',
                      style: TextStyle(
                        color: Colors.white,
                        fontSize: 28,
                        fontWeight: FontWeight.bold,
                      ),
                      textAlign: TextAlign.center,
                    ),
                    const SizedBox(height: 24),
                    Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Image.asset('assets/grain.png', height: 36, width: 36),
                        const SizedBox(width: 8),
                        Text(
                          '+$gained',
                          style: TextStyle(
                            color: AppColors.yellow,
                            fontSize: 32,
                            fontWeight: FontWeight.w900,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 16),
                    Text(
                      'New balance: $total grain',
                      style: const TextStyle(
                        color: Colors.white70,
                        fontSize: 18,
                      ),
                      textAlign: TextAlign.center,
                    ),
                    const SizedBox(height: 32),
                    const Text(
                      'Tap anywhere to continue',
                      style: TextStyle(color: Colors.white54, fontSize: 16),
                      textAlign: TextAlign.center,
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
