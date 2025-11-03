import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:http/http.dart' as http;
import 'package:http_parser/http_parser.dart'; 
import 'dart:convert'; 
import 'dart:io'; 
import 'package:flutter_spinkit/flutter_spinkit.dart'; 
import 'results_page.dart';

const String apiUrl = "http://10.10.30.8:8000/process_receipt/";

void main() {
  runApp(const MyApp());
}

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Fiş Tarayıcı',
      theme: ThemeData(
        primarySwatch: Colors.blue,
        useMaterial3: true,
      ),
      home: const OcrScannerPage(),
    );
  }
}

class OcrScannerPage extends StatefulWidget {
  const OcrScannerPage({super.key});

  @override
  State<OcrScannerPage> createState() => _OcrScannerPageeState();
}

class _OcrScannerPageeState extends State<OcrScannerPage> {
  final ImagePicker _picker = ImagePicker();
  XFile? _imageFile; 
  bool _isLoading = false; 
  
  Map<String, dynamic>? _extractedData;
  late Map<String, TextEditingController> _controllers;

  @override
  void initState() {
    super.initState();
    _controllers = {};
  }

  @override
  void dispose() {
    
    _controllers.forEach((key, controller) {
      controller.dispose();
    });
    super.dispose();
  }

  Future<void> _pickImage(ImageSource source) async {
    try {
      final XFile? pickedFile = await _picker.pickImage(source: source);
      if (pickedFile != null) {
        setState(() {
          _imageFile = pickedFile;
          _extractedData = null; 
          _controllers.clear(); 
        });
        _processImage(pickedFile);
      }
    } catch (e) {
      print("Resim seçme hatası: $e");
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text("Resim seçilemedi: $e")),
      );
    }
  }
  Future<void> _processImage(XFile image) async {
    setState(() {
      _isLoading = true;
    });
    try {
      var request = http.MultipartRequest('POST', Uri.parse(apiUrl));
      
      request.files.add(await http.MultipartFile.fromPath(
        'file', 
        image.path,
        contentType: MediaType('image', image.path.split('.').last), 
      ));

      var streamedResponse = await request.send();
      var response = await http.Response.fromStream(streamedResponse);

      setState(() {
        _isLoading = false;
      });

      if (response.statusCode == 200) {
        final Map<String, dynamic> data = jsonDecode(utf8.decode(response.bodyBytes));
        
        setState(() {
          _extractedData = data;
          _controllers = {
            for (var entry in data.entries)
              entry.key: TextEditingController(text: entry.value.toString()),
          };
        });
      } else {
        print("API Hatası: ${response.body}");
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text("API Hatası: ${response.body}")),
        );
      }
    } catch (e) {
      setState(() {
        _isLoading = false;
      });
      print("Sunucuya bağlanma hatası: $e");
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text("Sunucuya bağlanılamadı. IP adresinizi ($apiUrl) kontrol edin: $e")),
      );
    }
  }
  Widget _buildResults() {
    if (_extractedData == null) {
      return const SizedBox.shrink(); 
    }
    String? lineItemsKey;
    if(_extractedData!.containsKey("Alınan Ürünler")) {
      lineItemsKey = "Alınan Ürünler";
    } else if (_extractedData!.containsKey("Sipariş Kalemleri")) {
      lineItemsKey = "Sipariş Kalemleri";
    }

    return Expanded(
      child: ListView(
        children: [
          ..._extractedData!.entries
            .where((entry) => entry.key != lineItemsKey) 
            .map((entry) {
              if (_controllers[entry.key] == null) return const SizedBox.shrink();

              return Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16.0, vertical: 8.0),
                child: TextFormField(
                  controller: _controllers[entry.key], 
                  decoration: InputDecoration(
                    labelText: entry.key,
                    border: OutlineInputBorder(),
                  ),
                ),
              );
          }).toList(),
          
          if(lineItemsKey != null && _controllers[lineItemsKey] != null)
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16.0, vertical: 8.0),
              child: TextFormField( 
                controller: _controllers[lineItemsKey], 
                decoration: InputDecoration(
                  labelText: lineItemsKey,
                  border: OutlineInputBorder(),
                  alignLabelWithHint: true, 
                ),
                maxLines: null, 
                keyboardType: TextInputType.multiline, 
              ),
            ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Fiş Tarayıcı'),
      ),
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.start,
          children: <Widget>[
            Padding(
              padding: const EdgeInsets.all(16.0),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                children: [
                  ElevatedButton.icon(
                    icon: const Icon(Icons.camera_alt),
                    label: const Text('Kamera'),
                    onPressed: () => _pickImage(ImageSource.camera),
                  ),
                  ElevatedButton.icon(
                    icon: const Icon(Icons.photo_library),
                    label: const Text('Galeri'),
                    onPressed: () => _pickImage(ImageSource.gallery),
                  ),
                ],
              ),
            ),
            if (_isLoading)
              const Padding(
                padding: EdgeInsets.all(32.0),
                child: SpinKitFadingCircle(
                  color: Colors.blue,
                  size: 50.0,
                ),
              ),

            if (!_isLoading && _extractedData != null)
              _buildResults(),

            if (!_isLoading && _extractedData != null)
              Padding(
                padding: const EdgeInsets.all(16.0),
                child: ElevatedButton(
                  style: ElevatedButton.styleFrom(
                    minimumSize: const Size(double.infinity, 50), 
                  ),
                  onPressed: () {

                    Map<String, String> finalData = {};
                    _controllers.forEach((key, controller) {
                      finalData[key] = controller.text;
                    });

                      String? lineItemsKey;
                      if(_extractedData?.containsKey("Alınan Ürünler") ?? false) lineItemsKey = "Alınan Ürünler";
                      if(_extractedData?.containsKey("Sipariş Kalemleri") ?? false) lineItemsKey = "Sipariş Kalemleri";
                      if(lineItemsKey != null) finalData[lineItemsKey] = _extractedData![lineItemsKey];

                      Navigator.push(
                      context,
                      MaterialPageRoute(
                        builder: (context) => ResultsPage(data: finalData),
                      ),
                      );
                    },
                  child: const Text('Gönder'),
                ),
              )
          ],
        ),
      ),
    );
  }
}

