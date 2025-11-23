import 'dart:convert';

import 'package:coingraze/colors.dart';
import 'package:coingraze/screens/secondary/payment_options.dart';
import 'package:flutter/cupertino.dart';
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:flutter/services.dart';
import 'package:http/http.dart' as http;

class BuyMoreScreen extends StatefulWidget {
  const BuyMoreScreen({super.key});

  @override
  State<BuyMoreScreen> createState() => _BuyMoreScreenState();
}

class _BuyMoreScreenState extends State<BuyMoreScreen> {
  int? _selectedIndex;
  final TextEditingController _controller = TextEditingController();
  int? _grainPurchaseAmount;
  double _euroAmount = 20;
  double? grainMultiplier1;
  double? grainMultiplier2;
  double? grainMultiplier3;
  double boxLength = 90;

  final FocusNode _focusNode = FocusNode();
  bool _isFocused = false;

  @override
  void initState() {
    super.initState();
    _selectedIndex = 1;
    _focusNode.addListener(_onFocusChange);
    _controller.addListener(() {
      setState(() {
        updateGrainPurchaseAmount();
      });
    });
    _fetchGrainMultipliers();
  }

  void _onFocusChange() {
    setState(() {
      _isFocused = _focusNode.hasFocus;
      if (_isFocused) {
        _selectedIndex = 3;
        updateGrainPurchaseAmount();
      } else {
        if (int.tryParse(_controller.text) == null) {
          if (_selectedIndex == 3) {
            boxLength = 40;
          } else {
            boxLength = 90;
          }
        }
      }
    });
  }

  void updateGrainPurchaseAmount() {
    final customText = _controller.text;
    final customInputValue = int.tryParse(customText);
    int? parsedCustomAmount;
    if (_selectedIndex == 3) {
      parsedCustomAmount = customInputValue;
    }

    setState(() {
      if (_selectedIndex == 0) {
        _euroAmount = 10;
        if (customInputValue == null) {
          boxLength = 90;
        }
        _grainPurchaseAmount = _calculateGrainsFromEuro(_euroAmount);
      }
      if (_selectedIndex == 1) {
        _euroAmount = 20;
        if (customInputValue == null) {
          boxLength = 90;
        }
        _grainPurchaseAmount = _calculateGrainsFromEuro(_euroAmount);
      }
      if (_selectedIndex == 2) {
        _euroAmount = 50;
        if (customInputValue == null) {
          boxLength = 90;
        }
        _grainPurchaseAmount = _calculateGrainsFromEuro(_euroAmount);
      }
      if (_selectedIndex == 3) {
        if (parsedCustomAmount == null) {
          _euroAmount = 0;
          _grainPurchaseAmount = 0;
          boxLength = 40;
        } else {
          _euroAmount = parsedCustomAmount.toDouble();
          _grainPurchaseAmount = _calculateGrainsFromEuro(_euroAmount);
        }
        if (customText.length.toDouble() == 1) {
          boxLength = 40;
        }
        if (customText.length.toDouble() == 2) {
          boxLength = 52;
        }
        if (customText.length.toDouble() == 3) {
          boxLength = 64;
        }
        if (customText.length.toDouble() == 4) {
          boxLength = 76;
        }
        if (customText.length.toDouble() == 5) {
          boxLength = 88;
        }
      }
    });
  }

  Future<void> _fetchGrainMultipliers() async {
    const String endpoint = 'https://api.compay.be/buy/multipliers';
    try {
      final response = await http.get(Uri.parse(endpoint));
      if (response.statusCode != 200) {
        debugPrint(
          'Failed to fetch grain multipliers. Status: ${response.statusCode}',
        );
        return;
      }
      final Map<String, dynamic> payload =
          jsonDecode(response.body) as Map<String, dynamic>;

      if (!mounted) return;

      setState(() {
        grainMultiplier1 = _parseMultiplier(
          payload['grain_multiplier1'],
          grainMultiplier1,
        );
        grainMultiplier2 = _parseMultiplier(
          payload['grain_multiplier2'],
          grainMultiplier2,
        );
        grainMultiplier3 = _parseMultiplier(
          payload['grain_multiplier3'],
          grainMultiplier3,
        );
      });

      updateGrainPurchaseAmount();
    } catch (error) {
      debugPrint('Error fetching grain multipliers: $error');
    }
  }

  double? _parseMultiplier(dynamic value, double? fallback) {
    if (value is num) {
      return value.toDouble();
    }
    if (value is String) {
      final parsed = double.tryParse(value);
      if (parsed != null) {
        return parsed;
      }
    }
    return fallback;
  }

  int? _calculateGrainsFromEuro(double euroAmount) {
    final multiplier = _getMultiplierForEuro(euroAmount);
    if (multiplier == null) {
      return null;
    }
    return (euroAmount * multiplier).round();
  }

  double? _getMultiplierForEuro(double euroAmount) {
    if (euroAmount < 20) {
      return grainMultiplier1;
    }
    if (euroAmount < 50) {
      return grainMultiplier2;
    }
    return grainMultiplier3;
  }

  @override
  void dispose() {
    _focusNode.removeListener(_onFocusChange);
    _controller.removeListener(() {});
    _focusNode.dispose();
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: () {
        // Always remove focus when tapped outside of any interactive element
        FocusScope.of(context).unfocus();
      },
      child: Scaffold(
        backgroundColor: AppColors.darkGreen,
        appBar: AppBar(
          backgroundColor: AppColors.lightGreen,
          leading: IconButton(
            onPressed: () async {
              Navigator.pop(context);
            },
            icon: Icon(Icons.arrow_back, color: Colors.white),
          ),
          title: Row(
            children: [
              Text('Buy More', style: TextStyle(color: Colors.white)),
              SizedBox(width: 10),
              Image.asset('assets/grain.png', height: 20, width: 20),
            ],
          ),
        ),
        body: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(15, 15, 0, 0),
              child: Text(
                'Select amount',
                style: TextStyle(color: AppColors.ligthGray, fontSize: 16),
              ),
            ),
            GridView.builder(
              shrinkWrap: true,
              padding: EdgeInsets.all(15),
              gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
                crossAxisCount: 2, // Number of columns
                crossAxisSpacing: 15, // Horizontal spacing
                mainAxisSpacing: 15, // Vertical spacing
                childAspectRatio: 1.5,
              ),
              itemCount: 4, // Number of items
              itemBuilder: (context, index) {
                // Check if current item is selected
                bool isSelected = _selectedIndex == index;

                return GestureDetector(
                  onTap: () {
                    setState(() {
                      _selectedIndex = index;
                      updateGrainPurchaseAmount();
                      if (index == 3) {
                        FocusScope.of(context).requestFocus(_focusNode);
                      } else {
                        _focusNode.unfocus();
                      }
                    });
                  },
                  child: Container(
                    decoration: BoxDecoration(
                      color: AppColors.lightGreen,
                      borderRadius: BorderRadius.circular(15),
                      border: Border.all(
                        color:
                            isSelected
                                ? AppColors.vividGreen
                                : AppColors.lightGreen,
                        width: 2,
                      ),
                    ),
                    child: Center(
                      child: Builder(
                        builder: (context) {
                          if (index == 0) {
                            return Text(
                              '€ 10',
                              style: TextStyle(
                                fontSize: 18,
                                color:
                                    isSelected
                                        ? AppColors.vividGreen
                                        : Colors.white,
                                fontWeight:
                                    isSelected
                                        ? FontWeight.bold
                                        : FontWeight.normal,
                              ),
                            );
                          } else if (index == 1) {
                            return Text(
                              '€ 20',
                              style: TextStyle(
                                fontSize: 18,
                                color:
                                    isSelected
                                        ? AppColors.vividGreen
                                        : Colors.white,
                                fontWeight:
                                    isSelected
                                        ? FontWeight.bold
                                        : FontWeight.normal,
                              ),
                            );
                          } else if (index == 2) {
                            return Text(
                              '€ 50',
                              style: TextStyle(
                                fontSize: 18,
                                color:
                                    isSelected
                                        ? AppColors.vividGreen
                                        : Colors.white,
                                fontWeight:
                                    isSelected
                                        ? FontWeight.bold
                                        : FontWeight.normal,
                              ),
                            );
                          } else if (index == 3) {
                            return SizedBox(
                              width: boxLength,
                              child: CupertinoTextField(
                                inputFormatters: [
                                  FilteringTextInputFormatter.allow(
                                    RegExp(r'^[0-9]+$'),
                                  ),
                                ],
                                controller: _controller,
                                maxLength: 5,
                                decoration: BoxDecoration(
                                  color: AppColors.lightGreen,
                                ),
                                style: GoogleFonts.inter(
                                  fontSize: 18,
                                  color:
                                      isSelected
                                          ? AppColors.vividGreen
                                          : Colors.white,
                                  fontWeight:
                                      isSelected
                                          ? FontWeight.bold
                                          : FontWeight.normal,
                                ),
                                keyboardType: TextInputType.numberWithOptions(
                                  decimal:
                                      false, // Allows for integer-only input
                                ),
                                focusNode: _focusNode,
                                placeholder: 'Amount', //'Bedrag'
                                placeholderStyle: TextStyle(
                                  fontFamily: "inter",
                                  fontSize: 18,
                                  color:
                                      isSelected
                                          ? AppColors.lightGreen
                                          : Colors.white,
                                ),
                                prefix: // Adjust padding as needed
                                    Text(
                                  '€',
                                  style: TextStyle(
                                    fontSize: 18,
                                    color:
                                        isSelected
                                            ? AppColors.vividGreen
                                            : Colors.white,
                                  ),
                                ),
                              ),
                            );
                          } else {
                            return SizedBox.shrink();
                          }
                        },
                      ),
                    ),
                  ),
                );
              },
            ),
            Padding(
              padding: const EdgeInsets.all(8.0),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Image.asset('assets/grain.png', height: 40, width: 40),
                  Text(
                    '${_grainPurchaseAmount ?? '--'}',
                    style: TextStyle(
                      color: Colors.white,
                      fontSize: 44,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ],
              ),
            ),
            SizedBox(height: 10),
            Align(
              alignment: Alignment.center,
              child: ElevatedButton(
                style: ElevatedButton.styleFrom(
                  overlayColor: Colors.black,
                  splashFactory: InkRipple.splashFactory,
                  backgroundColor: AppColors.vividGreen,
                  minimumSize: const Size(180, 50),
                  maximumSize: const Size(180, 50),
                ),
                onPressed: () {
                  if (_euroAmount < 2) {
                    //check for null value and make sure nothing goes wrong
                    showDialog(
                      context: context,
                      builder:
                          (ctx) => const AlertDialog(title: Text('Minimum €2')),
                    );
                    return;
                  }
                  Navigator.of(context).push(
                    CupertinoPageRoute(
                      builder:
                          (context) => PaymentOptionsScreen(
                            grainAmount: _grainPurchaseAmount ?? 0,
                            euroAmount: _euroAmount,
                          ),
                    ),
                  );
                },
                child: const Text(
                  'Continue',
                  style: TextStyle(color: Colors.white, fontSize: 22),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
