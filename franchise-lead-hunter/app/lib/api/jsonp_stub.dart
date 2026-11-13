/// Phone apps and tests use normal HTTP. The script-tag transport only exists in the browser build.
Future<String> jsonpGet(Uri url, Duration timeout) => throw UnsupportedError('JSONP is for the web build only');
