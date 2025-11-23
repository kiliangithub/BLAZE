import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';

import 'package:coingraze/colors.dart';
import 'package:coingraze/providers/protected_content.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http/http.dart' as http;
import 'package:url_launcher/url_launcher.dart';

class BchPaymentDetailsScreen extends ConsumerStatefulWidget {
  final int grainAmount;
  final double euroAmount;

  const BchPaymentDetailsScreen({
    super.key,
    required this.grainAmount,
    required this.euroAmount,
  });

  @override
  ConsumerState<BchPaymentDetailsScreen> createState() =>
      _BchPaymentDetailsScreenState();
}

class _BchPaymentDetailsScreenState
    extends ConsumerState<BchPaymentDetailsScreen> {
  double? _bchAmount;
  bool _isLoading = true;
  String? _error;

  Uint8List? _qrBytes;
  bool _isQrLoading = false;
  String? _qrError;
  bool _qrRequested = false;
  String? _qrName;

  static const _lockDuration = Duration(minutes: 20);
  late DateTime _expiryTime;
  Duration _remaining = _lockDuration;
  Timer? _timer;

  @override
  void initState() {
    super.initState();
    _expiryTime = DateTime.now().add(_lockDuration);
    _startCountdown();
    _fetchBchAmount();
  }

  void _maybeFetchQrCode() {
    if (_qrRequested) return;

    final protected = ref.read(protectedContentProvider);
    final data = protected.maybeWhen(
      data: (d) => d,
      orElse: () => const <String, dynamic>{},
    );

    if (data.isEmpty) {
      return;
    }

    final dynamic idRaw = data['userId'] ?? data['id'];
    int? userId;
    if (idRaw is int) {
      userId = idRaw;
    } else if (idRaw is String) {
      userId = int.tryParse(idRaw);
    }
    if (userId == null) {
      return;
    }

    _qrRequested = true;
    _fetchQrCode(userId);
  }

  void _startCountdown() {
    _timer?.cancel();
    _timer = Timer.periodic(const Duration(seconds: 1), (timer) {
      final now = DateTime.now();
      final remaining = _expiryTime.difference(now);
      if (!mounted) return;
      setState(() {
        if (remaining.isNegative) {
          _remaining = Duration.zero;
          _timer?.cancel();
        } else {
          _remaining = remaining;
        }
      });
    });
  }

  Future<void> _fetchBchAmount() async {
    setState(() {
      _isLoading = true;
      _error = null;
    });

    try {
      final eurParam = widget.euroAmount.toStringAsFixed(2);
      final uri = Uri.parse(
        'https://api.compay.be/buy/bch_from_eur?EUR_amount=$eurParam',
      );
      final response = await http.get(uri);

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body) as Map<String, dynamic>;
        final bch = (data['bch'] as num).toDouble();
        if (!mounted) return;
        setState(() {
          _bchAmount = bch;
          _isLoading = false;
        });
      } else {
        if (!mounted) return;
        setState(() {
          _error = 'Failed to load BCH rate';
          _isLoading = false;
        });
      }
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = 'Failed to load BCH rate';
        _isLoading = false;
      });
    }
  }

  Future<void> _fetchQrCode(int userId) async {
    setState(() {
      _isQrLoading = true;
      _qrError = null;
    });

    try {
      final eurParam = widget.euroAmount.toStringAsFixed(2);
      final uri = Uri.parse(
        'https://api.compay.be/buy/user/$userId/qr?EUR_amount=$eurParam',
      );
      final response = await http.get(uri);

      if (response.statusCode == 200) {
        if (!mounted) return;
        // Try to derive a filename from the Content-Disposition header, if present.
        String? filename;
        final cd = response.headers['content-disposition'];
        if (cd != null) {
          final parts = cd.split(';');
          for (final part in parts) {
            final trimmed = part.trim();
            final lower = trimmed.toLowerCase();
            if (lower.startsWith('filename*=')) {
              // RFC 5987 style: filename*=utf-8''<percent-encoded>
              var value = trimmed.substring('filename*='.length).trim();
              if (value.startsWith('"') && value.endsWith('"')) {
                value = value.substring(1, value.length - 1);
              }
              // Strip charset/lang part (e.g. utf-8'')
              final idx = value.indexOf("''");
              if (idx != -1) {
                value = value.substring(idx + 2);
              }
              // Value is percent-encoded, in our case double-encoded; decode twice.
              try {
                value = Uri.decodeComponent(value);
                value = Uri.decodeComponent(value);
              } catch (_) {
                // If decoding fails, just keep the raw value.
              }
              filename = value;
              break;
            } else if (lower.startsWith('filename=')) {
              var value = trimmed.substring('filename='.length).trim();
              if (value.startsWith('"') && value.endsWith('"')) {
                value = value.substring(1, value.length - 1);
              }
              filename = value;
              break;
            }
          }
        }

        setState(() {
          _qrBytes = response.bodyBytes;
          // Only show a name below the QR if we actually got one from the server.
          _qrName = filename;
          _isQrLoading = false;
        });
      } else {
        if (!mounted) return;
        setState(() {
          _qrError = 'Failed to load QR code';
          _isQrLoading = false;
        });
      }
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _qrError = 'Failed to load QR code';
        _isQrLoading = false;
      });
    }
  }

  String _formatDuration(Duration d) {
    final totalSeconds = d.inSeconds;
    final minutes = totalSeconds ~/ 60;
    final seconds = totalSeconds % 60;
    final mm = minutes.toString().padLeft(2, '0');
    final ss = seconds.toString().padLeft(2, '0');
    return '$mm:$ss';
  }

  String _displayQrPrefix() {
    if (_qrName == null) return '';
    var base = _qrName!;
    // Strip extension for display only.
    if (base.endsWith('.png')) {
      base = base.substring(0, base.length - 4);
    }
    // Consider only the part before the query string.
    final qIndex = base.indexOf('?');
    final beforeQuery = qIndex != -1 ? base.substring(0, qIndex) : base;
    if (beforeQuery.isEmpty) return '';

    // Always show the first 17 characters (or less if the string is shorter).
    const prefixLen = 17;
    final actualPrefixLen =
        beforeQuery.length <= prefixLen ? beforeQuery.length : prefixLen;
    return beforeQuery.substring(0, actualPrefixLen);
  }

  String _displayQrSuffix() {
    if (_qrName == null) return '';
    var base = _qrName!;
    if (base.endsWith('.png')) {
      base = base.substring(0, base.length - 4);
    }
    final qIndex = base.indexOf('?');
    final beforeQuery = qIndex != -1 ? base.substring(0, qIndex) : base;
    if (beforeQuery.isEmpty) return '';

    const suffixLen = 4;
    final len = beforeQuery.length;
    final actualLen = len < suffixLen ? len : suffixLen;
    return beforeQuery.substring(len - actualLen);
  }

  String _displayQrDots() {
    // Always exactly three dots between prefix and suffix.
    return '...';
  }

  void _copyQrName(BuildContext context) {
    if (_qrName == null) return;
    final nameNoExt =
        _qrName!.endsWith('.png')
            ? _qrName!.substring(0, _qrName!.length - 4)
            : _qrName!;
    Clipboard.setData(ClipboardData(text: nameNoExt));
  }

  Future<void> _openInWallet(BuildContext context) async {
    if (_qrName == null) return;
    // Full URI without the .png extension, including any query params.
    var full = _qrName!;
    if (full.endsWith('.png')) {
      full = full.substring(0, full.length - 4);
    }
    final uri = Uri.tryParse(full);
    if (uri == null) return;

    // Check if any installed app can handle it (Android/iOS/web).
    if (await canLaunchUrl(uri)) {
      // Try to open with any capable wallet/app on the device.
      await launchUrl(uri, mode: LaunchMode.externalApplication);
    } else {
      if (!mounted) return;
      showDialog(
        context: context,
        builder:
            (ctx) => AlertDialog(
              backgroundColor: AppColors.lightGreen,
              title: const Text(
                'No wallet found',
                style: TextStyle(color: Colors.white),
              ),
              content: const Text(
                'No app on this device could open the payment link. '
                'Please install a Bitcoin Cash wallet and try again.',
                style: TextStyle(color: Colors.white),
              ),
              actions: [
                TextButton(
                  onPressed: () => Navigator.of(ctx).pop(),
                  child: const Text(
                    'OK',
                    style: TextStyle(color: Colors.white),
                  ),
                ),
              ],
            ),
      );
    }
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    _maybeFetchQrCode();
    return Scaffold(
      backgroundColor: AppColors.darkGreen,
      appBar: AppBar(
        backgroundColor: AppColors.lightGreen,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back, color: Colors.white),
          onPressed: () => Navigator.pop(context),
        ),
        title: const Text(
          'Bitcoin Cash payment',
          style: TextStyle(color: Colors.white),
        ),
      ),
      body: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Image.asset('assets/grain.png', height: 40, width: 40),
                const SizedBox(width: 8),
                Text(
                  '${widget.grainAmount}',
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 32,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Center(
              child: Text(
                '€ ${widget.euroAmount.toStringAsFixed(0)}',
                style: const TextStyle(
                  color: AppColors.ligthGray,
                  fontSize: 20,
                  fontWeight: FontWeight.w500,
                ),
              ),
            ),
            const SizedBox(height: 16),
            if (_isLoading)
              const Center(
                child: CircularProgressIndicator(
                  valueColor: AlwaysStoppedAnimation<Color>(Colors.white),
                ),
              )
            else if (_error != null)
              Center(
                child: Column(
                  children: [
                    Text(
                      _error!,
                      style: const TextStyle(
                        color: AppColors.error,
                        fontSize: 14,
                      ),
                    ),
                    const SizedBox(height: 8),
                    TextButton(
                      onPressed: _fetchBchAmount,
                      child: const Text(
                        'Retry',
                        style: TextStyle(color: Colors.white),
                      ),
                    ),
                  ],
                ),
              )
            else
              Center(
                child: Text(
                  '${_bchAmount?.toStringAsFixed(8)} BCH',
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 24,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
            const SizedBox(height: 12),
            Center(
              child:
                  _remaining > Duration.zero
                      ? Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          const Text(
                            'This price is locked for ',
                            style: TextStyle(
                              color: Colors.white70,
                              fontSize: 14,
                            ),
                          ),
                          SizedBox(
                            width: 48,
                            child: Text(
                              _formatDuration(_remaining),
                              textAlign: TextAlign.left,
                              style: const TextStyle(
                                color: Colors.white70,
                                fontSize: 14,
                              ),
                            ),
                          ),
                        ],
                      )
                      : const Text(
                        'Price lock expired',
                        style: TextStyle(color: Colors.white70, fontSize: 14),
                      ),
            ),
            const SizedBox(height: 24),
            if (_isQrLoading)
              const Center(
                child: CircularProgressIndicator(
                  valueColor: AlwaysStoppedAnimation<Color>(Colors.white),
                ),
              )
            else if (_qrError != null)
              Center(
                child: Text(
                  _qrError!,
                  style: const TextStyle(color: AppColors.error, fontSize: 14),
                ),
              )
            else if (_qrBytes != null)
              Center(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    InkWell(
                      borderRadius: BorderRadius.circular(16),
                      onTap: () => _copyQrName(context),
                      child: Image.memory(
                        _qrBytes!,
                        width: 200,
                        height: 200,
                        fit: BoxFit.contain,
                      ),
                    ),
                    const SizedBox(height: 8),
                    if (_qrName != null)
                      SizedBox(
                        width: 200, // match QR image width
                        child: InkWell(
                          borderRadius: BorderRadius.circular(8),
                          onTap: () => _copyQrName(context),
                          child: Row(
                            mainAxisSize: MainAxisSize.max,
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              // Left-aligned prefix, no padding
                              Flexible(
                                child: Text(
                                  _displayQrPrefix(),
                                  maxLines: 1,
                                  overflow: TextOverflow.clip,
                                  style: const TextStyle(
                                    color: Colors.white70,
                                    fontSize: 14,
                                  ),
                                ),
                              ),
                              // Dots directly after prefix, no extra space
                              Text(
                                _displayQrDots(),
                                maxLines: 1,
                                style: const TextStyle(
                                  color: Colors.white70,
                                  fontSize: 14,
                                ),
                              ),
                              // Suffix immediately next to the icon
                              Row(
                                mainAxisSize: MainAxisSize.min,
                                children: [
                                  Text(
                                    _displayQrSuffix(),
                                    maxLines: 1,
                                    style: const TextStyle(
                                      color: Colors.white70,
                                      fontSize: 14,
                                    ),
                                  ),
                                  const SizedBox(width: 4),
                                  const Icon(
                                    Icons.copy,
                                    size: 16,
                                    color: Colors.white70,
                                  ),
                                ],
                              ),
                            ],
                          ),
                        ),
                      ),
                    const SizedBox(height: 72),
                    Center(
                      child: ElevatedButton(
                        style: ElevatedButton.styleFrom(
                          backgroundColor: AppColors.vividGreen,
                          minimumSize: const Size(200, 44),
                          shape: const StadiumBorder(),
                        ),
                        onPressed: () => _openInWallet(context),
                        child: const Text(
                          'Open in wallet',
                          style: TextStyle(
                            color: Colors.white,
                            fontSize: 16,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ),
                    ),
                  ],
                ),
              ),
          ],
        ),
      ),
    );
  }
}
