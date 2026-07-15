#!/usr/bin/env node
"use strict";

// Symbol-layer extractor for TS/TSX. Invoked by scripts/kg/symbols.py.
// Reads a JSON array of repo-relative file paths from stdin (the bound-files
// list — emission scope), parses them with ts-morph into a single Project,
// and writes a JSON array of symbol records to stdout. Each
// function/method/property record carries:
//
//   calls       — resolved {name, container} for invocations whose target
//                 symbol the TypeScript checker can determine. Falls back to
//                 {name, container: null} when the target is external
//                 (node_modules / lib.d.ts) or otherwise unresolved.
//   implements  — {name, container} for every interface member or base-class
//                 method this method satisfies. Lets symbols.py grow
//                 polymorphic-dispatch edges so reaching an interface member
//                 reaches its implementations.
//   line, end_line — 1-based start and end lines of the declaration span.
//
// CLI args:
//   --compilation-root <dir>   widens the parse scope. Each root is walked
//                              recursively for *.ts/*.tsx (skipping
//                              node_modules / dist / bin / obj); discovered
//                              files join the Project but symbols are emitted
//                              only for files in stdin (the bound set).
//                              Repeatable; comma-separated also accepted.
//                              Default: none — Project = stdin only,
//                              preserving prior behavior when invoked
//                              without flags.
//   --sidecar <path>           write {source_file, source_line, target} JSON
//                              for every invocation in an UNBOUND file that
//                              resolves to a symbol declared in a BOUND
//                              file. Consumed by symbols.py to build
//                              unbound-but-referenced.yaml.
//
// Lib files (lib.d.ts and friends) are skipped — calls into them resolve to
// container null and are treated as external, matching how the Roslyn
// extractor treats framework calls.

const { Project, SyntaxKind } = require("ts-morph");
const fs = require("fs");
const path = require("path");

function readStdin() {
  return new Promise((resolve, reject) => {
    let data = "";
    process.stdin.setEncoding("utf8");
    process.stdin.on("data", (chunk) => (data += chunk));
    process.stdin.on("end", () => resolve(data));
    process.stdin.on("error", reject);
  });
}

function toForwardSlash(p) {
  return p.split(path.sep).join("/");
}

function repoRel(absPath, cwd) {
  return toForwardSlash(path.relative(cwd, absPath));
}

function hasExportModifier(node) {
  const modifiers = typeof node.getModifiers === "function" ? node.getModifiers() : [];
  return modifiers.some((m) => m.getKind() === SyntaxKind.ExportKeyword);
}

function lineOf(node) {
  return node.getStartLineNumber();
}

function endLineOf(node) {
  return node.getEndLineNumber();
}

function shortSignature(node) {
  const text = node.getText();
  const firstBrace = text.indexOf("{");
  const firstNewline = text.indexOf("\n");
  let cut = text.length;
  if (firstBrace > 0) cut = Math.min(cut, firstBrace);
  if (firstNewline > 0) cut = Math.min(cut, firstNewline);
  return text.slice(0, cut).trim();
}

// Walk up declaration ancestry to find the enclosing type-like container
// (class, interface, type literal). Returns the container name or null for
// top-level declarations. Mirrors the C# extractor's "container = declaring
// type" convention so resolve_call_edges can match on (container, name).
function enclosingContainer(decl) {
  let parent = decl.getParent();
  while (parent) {
    const k = parent.getKind();
    if (
      k === SyntaxKind.ClassDeclaration ||
      k === SyntaxKind.InterfaceDeclaration ||
      k === SyntaxKind.ClassExpression
    ) {
      const getName = parent.getName;
      if (typeof getName === "function") {
        const n = getName.call(parent);
        if (n) return n;
      }
    }
    parent = parent.getParent();
  }
  return null;
}

// Resolve a CallExpression to {name, container} using the TS checker. When
// the call target is in node_modules, lib.d.ts, or otherwise unresolved,
// returns {name, container: null} so the orchestrator can still match on
// bare name within the caller's canonical node.
function resolveCallTarget(callExpr) {
  const expr = callExpr.getExpression();
  if (!expr) return null;

  let syntacticName = null;
  const kind = expr.getKind();
  if (kind === SyntaxKind.Identifier) {
    syntacticName = expr.getText();
  } else if (kind === SyntaxKind.PropertyAccessExpression) {
    syntacticName = typeof expr.getName === "function" ? expr.getName() : null;
  } else if (kind === SyntaxKind.SuperKeyword) {
    syntacticName = "super";
  }

  let symbol = null;
  try {
    symbol = expr.getSymbol() || null;
  } catch {
    symbol = null;
  }
  if (!symbol && typeof expr.getSymbolOrThrow === "function") {
    // Some expression kinds (PropertyAccess) need the inner name node to
    // resolve to a callable symbol; ts-morph's getSymbol on the expression
    // can return the namespace symbol instead of the member symbol.
    try {
      if (kind === SyntaxKind.PropertyAccessExpression) {
        const nameNode = typeof expr.getNameNode === "function" ? expr.getNameNode() : null;
        if (nameNode) symbol = nameNode.getSymbol() || null;
      }
    } catch {
      // fall through to syntactic fallback below
    }
  }

  if (!symbol) {
    return syntacticName ? { name: syntacticName, container: null } : null;
  }

  // Aliased symbols (re-exports, default imports) need unwrapping to find
  // the real declaration.
  let resolved = symbol;
  if (typeof resolved.getAliasedSymbol === "function") {
    try {
      const aliased = resolved.getAliasedSymbol();
      if (aliased) resolved = aliased;
    } catch {
      /* alias chain may dead-end on external symbols */
    }
  }

  const decls = resolved.getDeclarations();
  let name = resolved.getName();
  if ((!name || name === "default") && syntacticName) name = syntacticName;
  if (!name) return null;

  let container = null;
  if (decls.length > 0) container = enclosingContainer(decls[0]);
  return { name, container };
}

function collectCalls(node) {
  const seen = new Set();
  const out = [];
  node.forEachDescendant((desc) => {
    if (desc.getKind() !== SyntaxKind.CallExpression) return;
    const ref = resolveCallTarget(desc);
    if (!ref || !ref.name) return;
    const key = `${ref.name}::${ref.container || ""}`;
    if (seen.has(key)) return;
    seen.add(key);
    out.push(ref);
  });
  return out;
}

// Type names that resolve to lib.d.ts or are TS keywords; emitting them
// would pollute type_refs without producing any bound symbol edge. The
// real user types still surface because TypeReferenceNode recursion walks
// into generic type arguments separately.
const BUILTIN_TYPE_NAMES = new Set([
  "Promise", "Array", "ReadonlyArray", "Map", "Set", "WeakMap", "WeakSet",
  "Record", "Partial", "Required", "Readonly", "Pick", "Omit", "Exclude",
  "Extract", "NonNullable", "Parameters", "ReturnType", "Awaited",
  "string", "number", "boolean", "void", "null", "undefined", "any",
  "unknown", "never", "object", "Date", "RegExp", "Error", "Function",
  "Object", "JSX",
]);

function unaliasedSymbol(sym) {
  if (!sym) return null;
  if (typeof sym.getAliasedSymbol === "function") {
    try {
      const aliased = sym.getAliasedSymbol();
      if (aliased) return aliased;
    } catch {
      /* ignore */
    }
  }
  return sym;
}

function isUserTypeSymbol(sym) {
  if (!sym || typeof sym.getDeclarations !== "function") return false;
  const decls = sym.getDeclarations();
  if (!decls || decls.length === 0) return false;
  for (const d of decls) {
    const sf = typeof d.getSourceFile === "function" ? d.getSourceFile() : null;
    if (!sf) return false;
    if (typeof sf.isDeclarationFile === "function" && sf.isDeclarationFile()) {
      return false;
    }
    const fp = typeof sf.getFilePath === "function" ? sf.getFilePath() : "";
    if (fp.includes("/node_modules/")) return false;
  }
  return true;
}

function refFromTypeSymbol(sym) {
  if (!isUserTypeSymbol(sym)) return null;
  const name = sym.getName();
  if (!name || BUILTIN_TYPE_NAMES.has(name)) return null;
  const decls = sym.getDeclarations();
  const decl = decls[0];
  const parent = typeof decl.getParent === "function" ? decl.getParent() : null;
  const parentName =
    parent && typeof parent.getName === "function" ? parent.getName() : null;
  // Avoid emitting a self-shadowing container that's just the declaration's
  // own enclosing module/file.
  const container = parentName && parentName !== name ? parentName : null;
  return { name, container };
}

function collectInstantiations(node) {
  const seen = new Set();
  const out = [];
  node.forEachDescendant((desc) => {
    if (desc.getKind() !== SyntaxKind.NewExpression) return;
    const expr = desc.getExpression();
    if (!expr) return;
    let sym = null;
    try {
      sym = expr.getSymbol() || null;
    } catch {
      return;
    }
    const ref = refFromTypeSymbol(unaliasedSymbol(sym));
    if (!ref) return;
    const key = `${ref.name}::${ref.container || ""}`;
    if (seen.has(key)) return;
    seen.add(key);
    out.push(ref);
  });
  return out;
}

function collectTypeRefs(node) {
  const seen = new Set();
  const out = [];
  node.forEachDescendant((desc) => {
    if (desc.getKind() !== SyntaxKind.TypeReference) return;
    const typeName =
      typeof desc.getTypeName === "function" ? desc.getTypeName() : null;
    if (!typeName) return;
    let sym = null;
    try {
      sym = typeName.getSymbol() || null;
    } catch {
      return;
    }
    const ref = refFromTypeSymbol(unaliasedSymbol(sym));
    if (!ref) return;
    const key = `${ref.name}::${ref.container || ""}`;
    if (seen.has(key)) return;
    seen.add(key);
    out.push(ref);
  });
  return out;
}

// Resolve a heritage clause expression (e.g., implements IFoo, extends Base)
// to the declaration node it points at, unwrapping aliases.
function resolveHeritageTarget(expressionWithTypeArgs) {
  const expr = expressionWithTypeArgs.getExpression();
  if (!expr) return null;
  let symbol = null;
  try {
    symbol = expr.getSymbol() || null;
  } catch {
    return null;
  }
  if (!symbol) return null;
  if (typeof symbol.getAliasedSymbol === "function") {
    try {
      const aliased = symbol.getAliasedSymbol();
      if (aliased) symbol = aliased;
    } catch {
      /* ignore */
    }
  }
  const decls = symbol.getDeclarations();
  return decls.length > 0 ? decls[0] : null;
}

// For a method on a class, emit {name, container} for every interface member
// or base-class method that this method satisfies. resolve_call_edges in
// symbols.py reverses these into dispatch edges (interface member → impl)
// and persists the resolved ids.
function implementsForMethod(methodNode, classDecl) {
  if (!classDecl || typeof classDecl.getName !== "function") return [];
  const methodName = typeof methodNode.getName === "function" ? methodNode.getName() : null;
  if (!methodName) return [];

  const seen = new Set();
  const out = [];

  function recordIfMatching(declNode) {
    if (!declNode) return;
    const k = declNode.getKind();
    if (k !== SyntaxKind.InterfaceDeclaration && k !== SyntaxKind.ClassDeclaration) return;
    const containerName = typeof declNode.getName === "function" ? declNode.getName() : null;
    if (!containerName) return;
    const members = typeof declNode.getMembers === "function" ? declNode.getMembers() : [];
    for (const m of members) {
      const mk = m.getKind();
      if (mk !== SyntaxKind.MethodDeclaration && mk !== SyntaxKind.MethodSignature) continue;
      const mname = typeof m.getName === "function" ? m.getName() : null;
      if (mname !== methodName) continue;
      const key = `${methodName}::${containerName}`;
      if (seen.has(key)) continue;
      seen.add(key);
      out.push({ name: methodName, container: containerName });
    }
  }

  const implementsClauses =
    typeof classDecl.getImplements === "function" ? classDecl.getImplements() : [];
  for (const clause of implementsClauses) {
    recordIfMatching(resolveHeritageTarget(clause));
  }

  // ClassDeclaration.getExtends() returns a single ExpressionWithTypeArguments | undefined.
  const extendsClause =
    typeof classDecl.getExtends === "function" ? classDecl.getExtends() : null;
  if (extendsClause) {
    recordIfMatching(resolveHeritageTarget(extendsClause));
  }

  return out;
}

// Recursive walk of a directory tree returning *.ts and *.tsx files. Skips
// node_modules, dist, bin, obj — none of which contribute to the symbol layer
// and inflating Project size with them slows resolution materially.
function* enumerateTsFiles(rootAbs) {
  let entries;
  try {
    entries = fs.readdirSync(rootAbs, { withFileTypes: true });
  } catch {
    return;
  }
  for (const entry of entries) {
    const full = path.join(rootAbs, entry.name);
    if (entry.isDirectory()) {
      const name = entry.name.toLowerCase();
      if (
        name === "node_modules" ||
        name === "dist" ||
        name === "bin" ||
        name === "obj" ||
        name === ".next" ||
        name === ".turbo"
      ) {
        continue;
      }
      yield* enumerateTsFiles(full);
    } else if (entry.isFile()) {
      const lower = entry.name.toLowerCase();
      if (lower.endsWith(".ts") || lower.endsWith(".tsx")) {
        yield full;
      }
    }
  }
}

function pushFunctionLike(rel, node, container, kind, outputs) {
  const name =
    (typeof node.getName === "function" && node.getName()) ||
    (typeof node.getNameNode === "function" && node.getNameNode()?.getText()) ||
    null;
  if (!name) return;
  const visibility = container ? "public" : hasExportModifier(node) ? "export" : "local";
  outputs.push({
    file: rel,
    name,
    container,
    kind,
    line: lineOf(node),
    end_line: endLineOf(node),
    signature: shortSignature(node),
    visibility,
    calls: collectCalls(node),
    implements: [],
    instantiates: collectInstantiations(node),
    type_refs: collectTypeRefs(node),
  });
}

function emitSourceFile(sourceFile, rel, outputs) {
  sourceFile.forEachChild((child) => {
    const kind = child.getKind();

    if (kind === SyntaxKind.FunctionDeclaration) {
      pushFunctionLike(rel, child, null, "function", outputs);
    } else if (kind === SyntaxKind.ClassDeclaration) {
      const className = typeof child.getName === "function" ? child.getName() : null;
      if (!className) return;
      outputs.push({
        file: rel,
        name: className,
        container: null,
        kind: "class",
        line: lineOf(child),
        end_line: endLineOf(child),
        signature: shortSignature(child),
        visibility: hasExportModifier(child) ? "export" : "local",
        calls: [],
        implements: [],
        instantiates: [],
        type_refs: [],
      });
      for (const member of child.getMembers()) {
        const mk = member.getKind();
        if (mk === SyntaxKind.MethodDeclaration) {
          const methodName = typeof member.getName === "function" ? member.getName() : null;
          if (!methodName) continue;
          outputs.push({
            file: rel,
            name: methodName,
            container: className,
            kind: "method",
            line: lineOf(member),
            end_line: endLineOf(member),
            signature: shortSignature(member),
            visibility: "public",
            calls: collectCalls(member),
            implements: implementsForMethod(member, child),
            instantiates: collectInstantiations(member),
            type_refs: collectTypeRefs(member),
          });
        } else if (mk === SyntaxKind.PropertyDeclaration) {
          const name = typeof member.getName === "function" ? member.getName() : null;
          if (!name) continue;
          outputs.push({
            file: rel,
            name,
            container: className,
            kind: "property",
            line: lineOf(member),
            end_line: endLineOf(member),
            signature: shortSignature(member),
            visibility: "public",
            calls: collectCalls(member),
            implements: [],
            instantiates: collectInstantiations(member),
            type_refs: collectTypeRefs(member),
          });
        }
      }
    } else if (kind === SyntaxKind.InterfaceDeclaration) {
      const name = typeof child.getName === "function" ? child.getName() : null;
      if (!name) return;
      outputs.push({
        file: rel,
        name,
        container: null,
        kind: "interface",
        line: lineOf(child),
        end_line: endLineOf(child),
        signature: shortSignature(child),
        visibility: hasExportModifier(child) ? "export" : "local",
        calls: [],
        implements: [],
        instantiates: [],
        type_refs: [],
      });
      // Emit each interface member as its own symbol so resolve_call_edges
      // can hang dispatch edges off them. Container = interface name, kind
      // = "method" so the qualified lookup ("IFoo", "Bar") finds them.
      const members = typeof child.getMembers === "function" ? child.getMembers() : [];
      for (const member of members) {
        const mk = member.getKind();
        if (mk !== SyntaxKind.MethodSignature) continue;
        const mname = typeof member.getName === "function" ? member.getName() : null;
        if (!mname) continue;
        outputs.push({
          file: rel,
          name: mname,
          container: name,
          kind: "method",
          line: lineOf(member),
          end_line: endLineOf(member),
          signature: shortSignature(member),
          visibility: "public",
          calls: [],
          implements: [],
          instantiates: [],
          type_refs: collectTypeRefs(member),
        });
      }
    } else if (kind === SyntaxKind.TypeAliasDeclaration) {
      const name = typeof child.getName === "function" ? child.getName() : null;
      if (!name) return;
      outputs.push({
        file: rel,
        name,
        container: null,
        kind: "type",
        line: lineOf(child),
        end_line: endLineOf(child),
        signature: shortSignature(child),
        visibility: hasExportModifier(child) ? "export" : "local",
        calls: [],
        implements: [],
        instantiates: [],
        type_refs: collectTypeRefs(child),
      });
    } else if (kind === SyntaxKind.EnumDeclaration) {
      const name = typeof child.getName === "function" ? child.getName() : null;
      if (!name) return;
      outputs.push({
        file: rel,
        name,
        container: null,
        kind: "enum",
        line: lineOf(child),
        end_line: endLineOf(child),
        signature: shortSignature(child),
        visibility: hasExportModifier(child) ? "export" : "local",
        calls: [],
        implements: [],
        instantiates: [],
        type_refs: [],
      });
    } else if (kind === SyntaxKind.VariableStatement) {
      const isExported = hasExportModifier(child);
      for (const decl of child.getDeclarationList().getDeclarations()) {
        const init = decl.getInitializer();
        if (!init) continue;
        const ik = init.getKind();
        if (ik !== SyntaxKind.ArrowFunction && ik !== SyntaxKind.FunctionExpression) {
          continue;
        }
        const name = decl.getName();
        if (!name) continue;
        outputs.push({
          file: rel,
          name,
          container: null,
          kind: "function",
          line: lineOf(decl),
          end_line: endLineOf(decl),
          signature: shortSignature(decl),
          visibility: isExported ? "export" : "local",
          calls: collectCalls(init),
          implements: [],
          instantiates: collectInstantiations(init),
          type_refs: collectTypeRefs(decl),
        });
      }
    }
  });
}

function collectSidecar(sourceFile, sourceRel, boundRelsSet, sidecar) {
  const seen = new Set();
  sourceFile.forEachDescendant((desc) => {
    if (desc.getKind() !== SyntaxKind.CallExpression) return;
    const expr = desc.getExpression();
    if (!expr) return;

    let symbol = null;
    try {
      symbol = expr.getSymbol() || null;
    } catch {
      return;
    }
    if (!symbol && expr.getKind() === SyntaxKind.PropertyAccessExpression) {
      try {
        const nameNode = typeof expr.getNameNode === "function" ? expr.getNameNode() : null;
        if (nameNode) symbol = nameNode.getSymbol() || null;
      } catch {
        symbol = null;
      }
    }
    if (!symbol) return;

    if (typeof symbol.getAliasedSymbol === "function") {
      try {
        const aliased = symbol.getAliasedSymbol();
        if (aliased) symbol = aliased;
      } catch {
        /* ignore */
      }
    }

    const decls = symbol.getDeclarations();
    if (!decls || decls.length === 0) return;

    let targetDecl = null;
    for (const d of decls) {
      const f = d.getSourceFile();
      if (!f) continue;
      const filePath = toForwardSlash(f.getFilePath());
      if (boundRelsSet.has(filePath)) {
        targetDecl = d;
        break;
      }
    }
    if (!targetDecl) return;

    let name = symbol.getName();
    if (!name || name === "default") {
      const k = expr.getKind();
      if (k === SyntaxKind.Identifier) name = expr.getText();
      else if (k === SyntaxKind.PropertyAccessExpression && typeof expr.getName === "function") {
        name = expr.getName();
      }
    }
    if (!name) return;

    const container = enclosingContainer(targetDecl);
    const line = desc.getStartLineNumber();
    const key = `${name}::${container || ""}::${line}`;
    if (seen.has(key)) return;
    seen.add(key);
    sidecar.push({
      source_file: sourceRel,
      source_line: line,
      target: { name, container },
    });
  });
}

function parseArgs(argv) {
  const compilationRoots = [];
  let sidecarPath = null;
  for (let i = 0; i < argv.length; i++) {
    if (argv[i] === "--compilation-root" && i + 1 < argv.length) {
      for (const part of argv[++i].split(",")) {
        const t = part.trim();
        if (t) compilationRoots.push(t);
      }
    } else if (argv[i] === "--sidecar" && i + 1 < argv.length) {
      sidecarPath = argv[++i];
    } else {
      process.stderr.write(`unknown arg: ${argv[i]}\n`);
      process.exit(1);
    }
  }
  return { compilationRoots, sidecarPath };
}

async function main() {
  const { compilationRoots, sidecarPath } = parseArgs(process.argv.slice(2));

  let stdinJson;
  try {
    const raw = await readStdin();
    stdinJson = JSON.parse(raw || "[]");
  } catch (e) {
    process.stderr.write(`failed to parse stdin JSON: ${e.message}\n`);
    process.exit(1);
  }
  if (!Array.isArray(stdinJson)) {
    process.stderr.write("stdin payload must be a JSON array of file paths\n");
    process.exit(1);
  }

  const cwd = process.cwd();
  // ts-morph normalizes file paths to absolute forward-slash form; keep
  // boundRelsSet keyed on the same form so the sidecar comparison is direct.
  const boundRelsSet = new Set();
  for (const rel of stdinJson) {
    boundRelsSet.add(toForwardSlash(path.resolve(cwd, rel)));
  }

  const project = new Project({
    skipFileDependencyResolution: false,
    skipLoadingLibFiles: true,
    compilerOptions: {
      allowJs: false,
      jsx: 4, // ReactJSX — works without needing react types loaded
      target: 99, // ESNext
      module: 99, // ESNext
      moduleResolution: 2, // NodeJs
      strict: false,
      noEmit: true,
      isolatedModules: false, // false so cross-file symbol resolution works
    },
  });

  // Track per-source-file bound status. A file may arrive via both stdin and
  // a compilation-root walk; bound takes precedence (emit symbols).
  const sourceFileMeta = new Map(); // absForwardPath → { isBound: bool }

  for (const rel of stdinJson) {
    const abs = toForwardSlash(path.resolve(cwd, rel));
    try {
      project.addSourceFileAtPath(abs);
      sourceFileMeta.set(abs, { isBound: true });
    } catch (e) {
      process.stderr.write(`failed to add bound ${rel}: ${e.message}\n`);
    }
  }

  for (const root of compilationRoots) {
    const rootAbs = path.resolve(cwd, root);
    if (!fs.existsSync(rootAbs)) {
      process.stderr.write(`compilation root missing: ${root}\n`);
      continue;
    }
    for (const abs of enumerateTsFiles(rootAbs)) {
      const forward = toForwardSlash(abs);
      if (sourceFileMeta.has(forward)) continue;
      try {
        project.addSourceFileAtPath(forward);
        sourceFileMeta.set(forward, { isBound: false });
      } catch (e) {
        process.stderr.write(`failed to add ${forward}: ${e.message}\n`);
      }
    }
  }

  const outputs = [];
  const sidecar = sidecarPath ? [] : null;

  for (const sourceFile of project.getSourceFiles()) {
    const abs = toForwardSlash(sourceFile.getFilePath());
    const meta = sourceFileMeta.get(abs);
    if (!meta) continue; // shouldn't happen
    const rel = repoRel(abs, cwd);
    if (meta.isBound) {
      emitSourceFile(sourceFile, rel, outputs);
    } else if (sidecar) {
      collectSidecar(sourceFile, rel, boundRelsSet, sidecar);
    }
  }

  process.stdout.write(JSON.stringify(outputs));

  if (sidecarPath) {
    try {
      fs.writeFileSync(sidecarPath, JSON.stringify(sidecar));
    } catch (e) {
      process.stderr.write(`sidecar write failed ${sidecarPath}: ${e.message}\n`);
      process.exit(1);
    }
  }
}

main().catch((e) => {
  process.stderr.write(`extractor crashed: ${e && e.stack ? e.stack : String(e)}\n`);
  process.exit(1);
});
