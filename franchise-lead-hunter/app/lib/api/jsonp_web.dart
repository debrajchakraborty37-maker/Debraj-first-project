import 'dart:async';
import 'dart:js_interop';
import 'dart:js_interop_unsafe';
import 'package:web/web.dart' as web;

int _counter = 0;

/// Loads [url] (with a callback name added) as a script tag. Browsers allow this from any page,
/// so it works with Google Apps Script without any CORS setup. The reply is the JSON text.
Future<String> jsonpGet(Uri url, Duration timeout) {
  final done = Completer<String>();
  final name = 'flhCb${DateTime.now().millisecondsSinceEpoch}_${_counter++}';
  final script = web.document.createElement('script') as web.HTMLScriptElement;
  Timer? timer;

  void cleanup() {
    timer?.cancel();
    globalContext.delete(name.toJS);
    script.remove();
  }

  globalContext.setProperty(
    name.toJS,
    ((JSString text) {
      if (!done.isCompleted) done.complete(text.toDart);
      cleanup();
    }).toJS,
  );
  script.onerror = ((web.Event _) {
    if (!done.isCompleted) done.completeError(StateError('script blocked or unreachable'));
    cleanup();
  }).toJS;
  timer = Timer(timeout, () {
    if (!done.isCompleted) done.completeError(TimeoutException('no answer'));
    cleanup();
  });
  script.src = url.replace(queryParameters: {...url.queryParameters, 'callback': name}).toString();
  web.document.head!.append(script);
  return done.future;
}
