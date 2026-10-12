// Reuse QLCoder authors' client; no bespoke JSON-RPC implementation.
import {readFileSync} from 'node:fs';
import {pathToFileURL} from 'node:url';
const config = JSON.parse(readFileSync(process.argv[2], 'utf8'));
const {CodeQLLanguageServer} = await import(pathToFileURL(config.client).href);
const server = new CodeQLLanguageServer({codeqlPath: config.codeql, verbose: config.verbose ?? false});
const timeout = setTimeout(() => {process.stderr.write('LSP probe timed out\n'); process.exit(2);}, 70000);
try {
  await server.start(config.workspaces);
  const results = [];
  for (const document of config.documents) {
    const uri = pathToFileURL(document.path).href;
    await server.openDocument(uri, readFileSync(document.path, 'utf8'));
    for (const position of document.positions) {
      results.push({file: document.path, ...position,
        hover: await server.getHover(uri, position.line, position.character)});
    }
  }
  process.stdout.write(JSON.stringify({status: 'completed', results}));
  await server.stop();
  clearTimeout(timeout);
  process.exit(0);
} catch (error) {
  process.stderr.write(String(error));
  process.exit(1);
}
