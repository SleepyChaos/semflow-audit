# Flask route shortcuts: constrained modeling evidence

Source: https://flask.palletsprojects.com/en/stable/api/
Reviewed 2026-10-03. Applies to Flask >=2.0. This is an original factual summary; it contains no benchmark source code or answers.

flask.Flask.get and flask.Blueprint.get register a GET handler using the same semantics as route with GET methods. flask.Flask.post and flask.Blueprint.post register a POST handler using the same semantics as route with POST methods. These decorators were added in Flask 2.0. Their rule argument is a URL pattern; the decorated function is a request handler.

In fixed codeql/python-all@4.0.10, Flask::FlaskRouteSetup models route setup. Flask::FlaskApp::instance() and Flask::Blueprint::instance() identify the corresponding library receivers. A DataFlow::CallCfgNode can identify a call to the receiver member. getUrlPatternArg returns positional argument 0 or keyword rule. getARequestHandler uses Function.getADecorator().getAFlowNode() = node. Extending FlaskRouteSetup allows the existing framework model to treat handler returns as HTTP responses; the pinned reflected XSS query retains its source, propagation and sanitizer logic.

This bounded model supports actual Flask receivers, not arbitrary same-name get/post methods. It does not add arbitrary sinks, assert exploitability, or replace independent positive/negative validation. Response MIME types and escaping semantics still require examination and testing.
