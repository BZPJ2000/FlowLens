import test from "node:test";
import assert from "node:assert/strict";

import {
  buildCodeGraphModel,
  edgeKindFromLabel,
  getGraphStats,
  getNodeNeighborhood,
  searchNodes,
} from "../src/lib/graphModel.js";
import type { DataFlowGraph } from "../src/types/index.js";

const graph: DataFlowGraph = {
  nodes: [
    {
      id: "file:math",
      file_path: "E:/repo/src/math.ts",
      file_name: "math.ts",
      folder_path: "src",
      language: "typescript",
      summary: "1 functions, 0 classes, 0 methods",
      detail: "math.ts",
      architecture_role: "module",
      ports: [],
      functions: [
        {
          id: "math.sum",
          name: "sum",
          qualified_name: "math.sum",
          start_line: 1,
          end_line: 3,
          params: [
            { name: "a", type: "number" },
            { name: "b", type: "number" },
          ],
          return_type: "number",
          is_exported: true,
          is_async: false,
          description: "sum",
        },
      ],
      classes: [],
      x: 0,
      y: 0,
    },
    {
      id: "file:app",
      file_path: "E:/repo/src/app.ts",
      file_name: "app.ts",
      folder_path: "src",
      language: "typescript",
      summary: "1 functions, 1 classes, 1 methods",
      detail: "app.ts",
      architecture_role: "module",
      ports: [],
      functions: [
        {
          id: "app.checkout",
          name: "checkout",
          qualified_name: "app.checkout",
          start_line: 5,
          end_line: 8,
          params: [{ name: "price", type: "number" }],
          return_type: "number",
          is_exported: true,
          is_async: false,
          description: "checkout",
        },
      ],
      classes: [
        {
          id: "app.Cart",
          name: "Cart",
          qualified_name: "app.Cart",
          start_line: 10,
          end_line: 16,
          is_exported: true,
          methods: [
            {
              id: "app.Cart.total",
              name: "total",
              qualified_name: "app.Cart.total",
              start_line: 11,
              end_line: 15,
              params: [],
              return_type: "number",
              is_exported: true,
              is_async: false,
              description: "total",
            },
          ],
        },
      ],
      x: 320,
      y: 0,
    },
  ],
  edges: [
    {
      id: "call:checkout:sum",
      source_node_id: "file:app",
      target_node_id: "file:math",
      source_port_id: "out-call",
      target_port_id: "in-sum",
      source_function_id: "app.checkout",
      target_function_id: "math.sum",
      variable_name: "call",
      data_type: "Unknown",
      edge_type: "call",
      source_slot: null,
      target_slot: null,
      line_number: 6,
      resolution: "resolved",
      label: "sum(price, 1)",
    },
    {
      id: "arg:checkout:sum:price",
      source_node_id: "file:app",
      target_node_id: "file:math",
      source_port_id: "out-price",
      target_port_id: "in-a",
      source_function_id: "app.checkout",
      target_function_id: "math.sum",
      variable_name: "price",
      data_type: "Unknown",
      edge_type: "arg",
      source_slot: "price",
      target_slot: "a",
      line_number: 6,
      resolution: "resolved",
      label: "price -> a",
    },
    {
      id: "return:sum:checkout:total",
      source_node_id: "file:math",
      target_node_id: "file:app",
      source_port_id: "out-return",
      target_port_id: "in-total",
      source_function_id: "math.sum",
      target_function_id: "app.checkout",
      variable_name: "total",
      data_type: "number",
      edge_type: "return",
      source_slot: "return",
      target_slot: "total",
      line_number: 6,
      resolution: "resolved",
      label: "sum.return -> total",
    },
    {
      id: "orphan",
      source_node_id: "file:app",
      target_node_id: "file:missing",
      source_port_id: "out-missing",
      target_port_id: "in-missing",
      source_function_id: "app.checkout",
      target_function_id: "missing.fn",
      variable_name: "missing",
      data_type: "Unknown",
      edge_type: "call",
      source_slot: null,
      target_slot: null,
      line_number: 7,
      resolution: "unresolved",
      label: "missing()",
    },
  ],
  entry_points: ["file:app"],
  exit_points: ["file:math"],
};

test("buildCodeGraphModel expands folders files symbols variables and relationships", () => {
  const model = buildCodeGraphModel(graph);
  const stats = getGraphStats(model);

  assert.equal(stats.folderCount, 2);
  assert.equal(stats.fileCount, 2);
  assert.equal(stats.functionCount, 2);
  assert.equal(stats.classCount, 1);
  assert.equal(stats.methodCount, 1);
  assert.equal(stats.variableCount, 2);
  assert.equal(stats.callCount, 1);
  assert.equal(stats.argCount, 2);
  assert.equal(stats.returnCount, 2);
  assert.equal(model.orphanEdgeCount, 1);
});

test("getNodeNeighborhood returns adjacent ids for a symbol", () => {
  const model = buildCodeGraphModel(graph);
  const neighborhood = getNodeNeighborhood(model, "app.checkout");

  assert.ok(neighborhood.outgoing.some((edge) => edge.target === "math.sum"));
  assert.ok([...neighborhood.relatedIds].some((id) => id.startsWith("var:arg:checkout")));
});

test("variable nodes keep file ownership so file-scoped views can show data flow", () => {
  const model = buildCodeGraphModel(graph);
  const price = model.variables.find((node) => node.id === "var:arg:checkout:sum:price");
  const total = model.variables.find((node) => node.id === "var:return:sum:checkout:total");

  assert.equal(price?.fileId, "file:app");
  assert.equal(price?.fileName, "app.ts");
  assert.equal(total?.fileId, "file:math");
  assert.equal(total?.fileName, "math.ts");
});

test("searchNodes finds symbols and files", () => {
  const model = buildCodeGraphModel(graph);

  assert.equal(searchNodes(model, "checkout")[0].id, "app.checkout");
  assert.equal(searchNodes(model, "math.ts")[0].id, "file:math");
});

test("edgeKindFromLabel classifies fallback edge labels", () => {
  assert.equal(
    edgeKindFromLabel({
      id: "custom-return",
      source_node_id: "a",
      target_node_id: "b",
      source_port_id: "a",
      target_port_id: "b",
      source_function_id: "a.fn",
      target_function_id: "b.fn",
      variable_name: "value",
      data_type: "Unknown",
      edge_type: "return",
      label: "return value",
    }),
    "return",
  );
});
