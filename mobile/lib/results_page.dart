import 'package:flutter/material.dart';
import 'package:http/http.dart' as http; 
import 'dart:convert';                   


class ResultsPage extends StatefulWidget {
  final Map<String, String> data;

  const ResultsPage({super.key, required this.data});

  @override
  State<ResultsPage> createState() => _ResultsPageState();
}

class _ResultsPageState extends State<ResultsPage> {

  late TextEditingController _sicilNoController;
  final _formKey = GlobalKey<FormState>(); 
  bool _isLoading = false; 

  // Verilerin gönderileceği URL'yi buraya yazıyoruz.(Şimdilik Webhook.com)
  final String _postUrl = "https://webhook.site/7f0ac2b9-57b0-4971-addd-e82aa568decc"; 

  @override
  void initState() {
    super.initState();
    // Sicil No için fabrika S ile başlıyor ben yazdım değişebilir.
    _sicilNoController = TextEditingController(text: "S"); 
  }

  @override
  void dispose() {
    _sicilNoController.dispose(); 
    super.dispose();
  }
  Future<void> _submitData() async {
    if (!_formKey.currentState!.validate()) {
      return;
    }
    setState(() {
      _isLoading = true;
    });
    try {
      Map<String, String> payload = {
        ...widget.data, 
        "sicilNo": _sicilNoController.text, 
      };

      final response = await http.post(
        Uri.parse(_postUrl),
        headers: {
          "Content-Type": "application/json; charset=UTF-8",
        },
        body: jsonEncode(payload), 
      );
      if (response.statusCode == 200 || response.statusCode == 201) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text("Veri başarıyla gönderildi!"), backgroundColor: Colors.green),
        );
        Navigator.of(context).pop(); 
      } else {
        print("Sunucu Hatası: ${response.body}");
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text("Sunucu Hatası: ${response.body}"), backgroundColor: Colors.red),
        );
      }
    } catch (e) {
      print("Ağ Hatası: $e");
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text("Gönderim hatası: $e"), backgroundColor: Colors.red),
      );
    } finally {
      setState(() {
        _isLoading = false;
      });
    }
  }
  @override
  Widget build(BuildContext context) {
    final entries = widget.data.entries.toList();

    return Scaffold(
      appBar: AppBar(
        title: const Text('Gönderilen Fiş Detayları'),
      ),
      body: Form(
        key: _formKey, 
        child: Column(
          children: [
            Expanded(
              child: ListView.builder(
                itemCount: entries.length,
                itemBuilder: (context, index) {
                  final entry = entries[index];
                  bool isLineItem = entry.key == "Alınan Ürünler" || entry.key == "Sipariş Kalemleri";

                  return Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 16.0, vertical: 8.0),
                    child: ListTile(
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(8),
                        side: BorderSide(color: Colors.grey.shade300),
                      ),
                      title: Text(
                        entry.key,
                        style: const TextStyle(fontWeight: FontWeight.bold, color: Colors.blueAccent),
                      ),
                      subtitle: Text(
                        entry.value,
                        style: isLineItem
                            ? const TextStyle(fontSize: 14, height: 1.5)
                            : const TextStyle(fontSize: 16, color: Colors.black87),
                      ),
                      isThreeLine: isLineItem,
                    ),
                  );
                },
              ),
            ),
            Padding(
              padding: const EdgeInsets.all(16.0),
              child: TextFormField(
                controller: _sicilNoController,
                decoration: const InputDecoration(
                  labelText: 'Sicil No',
                  hintText: 'Örn: S000849',
                  border: OutlineInputBorder(),
                ),
                validator: (value) {
                  if (value == null || value.trim().isEmpty) {
                    return 'Sicil No alanı boş bırakılamaz';
                  }
                  return null;
                },
              ),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 0, 16, 24), 
              child: SizedBox(
                width: double.infinity,
                height: 50,
                child: ElevatedButton(
                  onPressed: _isLoading ? null : _submitData, 
                  child: _isLoading
                      ? const CircularProgressIndicator(color: Colors.white)
                      : const Text(
                          'Verileri Gönder',
                          style: TextStyle(fontSize: 18),
                        ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}