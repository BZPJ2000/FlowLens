import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);

function loadBabelParser() {
  const candidates = [
    "@babel/parser",
    path.resolve(process.cwd(), "../frontend/node_modules/@babel/parser"),
    path.resolve(process.cwd(), "frontend/node_modules/@babel/parser"),
    path.resolve(process.cwd(), "../../frontend/node_modules/@babel/parser"),
  ];
  for (const candidate of candidates) {
    try {
      return require(candidate);
    } catch {
      // try next
    }
  }
  throw new Error("Cannot load @babel/parser");
}

const parser = loadBabelParser();
const filePath = process.argv[2];
const sourceType = process.argv[3] || "typescript";
const code = fs.readFileSync(filePath, "utf8");

function parseCode() {
  const plugins = [
    "typescript",
    "jsx",
    "decorators-legacy",
    "classProperties",
    "classPrivateProperties",
    "classPrivateMethods",
    "objectRestSpread",
    "dynamicImport",
    "topLevelAwait",
  ];
  return parser.parse(code, {
    sourceType: "unambiguous",
    plugins,
    errorRecovery: true,
  });
}

function idName(node) {
  if (!node) return "";
  if (node.type === "Identifier") return node.name;
  if (node.type === "PrivateName") return idName(node.id);
  if (node.type === "StringLiteral" || node.type === "NumericLiteral") return String(node.value);
  if (node.type === "MemberExpression" || node.type === "OptionalMemberExpression") {
    return idName(node.property);
  }
  return "";
}

function typeName(node) {
  if (!node) return "unknown";
  const typeAnn = node.typeAnnotation || node.returnType;
  if (!typeAnn) return "unknown";
  const t = typeAnn.typeAnnotation || typeAnn;
  return tsTypeToString(t);
}

function tsTypeToString(node) {
  if (!node) return "unknown";
  switch (node.type) {
    case "TSStringKeyword":
      return "string";
    case "TSNumberKeyword":
      return "number";
    case "TSBooleanKeyword":
      return "boolean";
    case "TSVoidKeyword":
      return "void";
    case "TSAnyKeyword":
      return "any";
    case "TSUnknownKeyword":
      return "unknown";
    case "TSNeverKeyword":
      return "never";
    case "TSTypeReference":
      return idName(node.typeName) || "unknown";
    case "TSArrayType":
      return `${tsTypeToString(node.elementType)}[]`;
    case "TSUnionType":
      return node.types.map(tsTypeToString).join(" | ");
    case "TSTypeLiteral":
      return "object";
    case "TSFunctionType":
      return "function";
    default:
      return node.type.replace(/^TS/, "").replace(/Keyword$/, "").toLowerCase() || "unknown";
  }
}

function paramInfo(param) {
  let node = param;
  if (node.type === "AssignmentPattern") node = node.left;
  if (node.type === "RestElement") node = node.argument;
  if (node.type === "TSParameterProperty") node = node.parameter;
  const name = idName(node) || (
    node.type === "ObjectPattern" ? "{...}" :
    node.type === "ArrayPattern" ? "[...]" : ""
  );
  return { name, type: typeName(node) };
}

function functionInfo(name, node, exported = false) {
  const params = (node.params || []).map(paramInfo).filter((p) => p.name);
  return {
    name,
    params,
    return_type: typeName(node),
    is_exported: exported,
    is_async: !!node.async,
    line_start: node.loc?.start?.line || 0,
    line_end: node.loc?.end?.line || 0,
  };
}

function calleeName(node) {
  if (!node) return "";
  if (node.type === "Identifier") return node.name;
  if (node.type === "MemberExpression" || node.type === "OptionalMemberExpression") {
    return idName(node.property);
  }
  return "";
}

function argName(node) {
  if (!node) return "";
  if (node.type === "Identifier") return node.name;
  if (node.type === "MemberExpression" || node.type === "OptionalMemberExpression") {
    return idName(node.property);
  }
  if (node.type === "StringLiteral" || node.type === "NumericLiteral" || node.type === "BooleanLiteral") {
    return String(node.value);
  }
  if (node.type === "ObjectExpression") return "{...}";
  if (node.type === "ArrayExpression") return "[...]";
  if (node.type === "CallExpression") return calleeName(node.callee);
  return "";
}

function visit(node, visitor, parent = null) {
  if (!node || typeof node.type !== "string") return;
  visitor(node, parent);
  for (const [key, value] of Object.entries(node)) {
    if (key === "loc" || key === "start" || key === "end" || key === "extra") continue;
    if (Array.isArray(value)) {
      for (const child of value) visit(child, visitor, node);
    } else if (value && typeof value.type === "string") {
      visit(value, visitor, node);
    }
  }
}

function parseExportNames(specifiers) {
  return (specifiers || []).map((s) => idName(s.exported || s.local)).filter(Boolean);
}

const ast = parseCode();
const imports = [];
const exports = [];
const functions = [];
const classes = [];
const calls = [];
const exportedNames = new Set();
const functionNameStack = [];

for (const stmt of ast.program.body || []) {
  if (stmt.type === "ImportDeclaration") {
    const source = stmt.source?.value || "";
    for (const spec of stmt.specifiers || []) {
      if (spec.type === "ImportDefaultSpecifier") {
        imports.push({ variable_name: idName(spec.local), source_module: source, import_type: "default", alias: "" });
      } else if (spec.type === "ImportNamespaceSpecifier") {
        imports.push({ variable_name: idName(spec.local), source_module: source, import_type: "namespace", alias: "" });
      } else if (spec.type === "ImportSpecifier") {
        const local = idName(spec.local);
        const imported = idName(spec.imported);
        imports.push({
          variable_name: local,
          source_module: source,
          import_type: spec.importKind === "type" || stmt.importKind === "type" ? "type" : "named",
          alias: imported && imported !== local ? imported : "",
        });
      }
    }
  } else if (stmt.type === "ExportNamedDeclaration") {
    if (stmt.declaration) {
      const decl = stmt.declaration;
      if (decl.id?.name) exportedNames.add(decl.id.name);
      if (decl.type === "VariableDeclaration") {
        for (const d of decl.declarations || []) {
          const name = idName(d.id);
          if (name) exportedNames.add(name);
        }
      }
    }
    for (const name of parseExportNames(stmt.specifiers)) exportedNames.add(name);
  } else if (stmt.type === "ExportDefaultDeclaration") {
    const decl = stmt.declaration;
    const name = decl?.id?.name || "default";
    exportedNames.add(name);
    exports.push({ variable_name: name, export_type: "default", data_type: "unknown", is_function: decl?.type?.includes("Function") || false, is_class: decl?.type === "ClassDeclaration", is_type_only: false });
  }
}

function addExport(name, kind, isTypeOnly = false) {
  if (!name) return;
  exports.push({
    variable_name: name,
    export_type: "named",
    data_type: kind === "function" ? "function" : kind === "class" ? "class" : "unknown",
    is_function: kind === "function",
    is_class: kind === "class",
    is_type_only: isTypeOnly,
  });
}

for (const stmt of ast.program.body || []) {
  const decl = stmt.type === "ExportNamedDeclaration" ? stmt.declaration : stmt;
  if (!decl) continue;
  if (decl.type === "FunctionDeclaration" && decl.id?.name) {
    functions.push(functionInfo(decl.id.name, decl, exportedNames.has(decl.id.name)));
  } else if (decl.type === "VariableDeclaration") {
    for (const d of decl.declarations || []) {
      const name = idName(d.id);
      if (!name) continue;
      if (d.init && ["ArrowFunctionExpression", "FunctionExpression"].includes(d.init.type)) {
        functions.push(functionInfo(name, d.init, exportedNames.has(name)));
      }
    }
  } else if (decl.type === "ClassDeclaration" && decl.id?.name) {
    const cls = {
      name: decl.id.name,
      methods: [],
      is_exported: exportedNames.has(decl.id.name),
      line_start: decl.loc?.start?.line || 0,
      line_end: decl.loc?.end?.line || 0,
    };
    for (const member of decl.body?.body || []) {
      if (member.kind === "constructor") continue;
      const name = idName(member.key);
      if (!name || !["ClassMethod", "ClassPrivateMethod"].includes(member.type)) continue;
      cls.methods.push(functionInfo(name, member, false));
    }
    classes.push(cls);
  }
}

for (const fn of functions) addExport(fn.name, "function");
for (const cls of classes) addExport(cls.name, "class");
for (const name of exportedNames) {
  if (!exports.some((e) => e.variable_name === name)) {
    const fn = functions.find((f) => f.name === name);
    const cls = classes.find((c) => c.name === name);
    addExport(name, fn ? "function" : cls ? "class" : "unknown");
  }
}

function visitFunctionBody(name, body) {
  functionNameStack.push(name);
  visit(body, (node) => {
    if (node.type === "CallExpression" || node.type === "OptionalCallExpression") {
      const callee = calleeName(node.callee);
      if (!callee) return;
      calls.push({
        caller_name: functionNameStack[functionNameStack.length - 1],
        callee_name: callee,
        args: (node.arguments || []).map((arg, idx) => ({
          name: argName(arg),
          type: "unknown",
          position: idx,
        })).filter((arg) => arg.name),
        line: node.loc?.start?.line || 0,
      });
    }
  });
  functionNameStack.pop();
}

for (const stmt of ast.program.body || []) {
  const decl = stmt.type === "ExportNamedDeclaration" ? stmt.declaration : stmt;
  if (!decl) continue;
  if (decl.type === "FunctionDeclaration" && decl.id?.name) {
    visitFunctionBody(decl.id.name, decl.body);
  } else if (decl.type === "VariableDeclaration") {
    for (const d of decl.declarations || []) {
      const name = idName(d.id);
      if (name && d.init && ["ArrowFunctionExpression", "FunctionExpression"].includes(d.init.type)) {
        visitFunctionBody(name, d.init.body);
      }
    }
  } else if (decl.type === "ClassDeclaration" && decl.id?.name) {
    for (const member of decl.body?.body || []) {
      const name = idName(member.key);
      if (name && ["ClassMethod", "ClassPrivateMethod"].includes(member.type)) {
        visitFunctionBody(name, member.body);
      }
    }
  }
}

process.stdout.write(JSON.stringify({ imports, exports, functions, classes, calls }));
