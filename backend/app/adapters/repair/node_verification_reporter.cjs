// Structured Node test events retain the thrown exception type; stack text does not.
const escape = value => String(value ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;");
module.exports = async function* (events) {
  yield '<?xml version="1.0" encoding="utf-8"?><testsuites><testsuite>';
  for await (const event of events) {
    if (!["test:pass", "test:fail"].includes(event.type)) continue;
    const { name, details = {}, skip, todo } = event.data;
    yield `<testcase name="${escape(name)}">`;
    if (skip || todo) yield '<skipped/>';
    else if (event.type === "test:fail") {
      const thrown = details.error?.cause ?? details.error;
      const assertion = thrown?.name === "AssertionError" && thrown?.code === "ERR_ASSERTION";
      const type = assertion ? "AssertionError" : "ExecutionError";
      yield `<failure type="${type}" message="${escape(thrown?.message)}">${escape(thrown?.stack)}</failure>`;
    }
    yield '</testcase>';
  }
  yield '</testsuite></testsuites>';
};
