const path = require("node:path");
const { pathToFileURL } = require("node:url");

const scriptDirectory = path.resolve(__dirname, "../../../../src/uptimely/explorer/app/static/js");
const moduleAt = name => import(pathToFileURL(path.join(scriptDirectory, name)).href);

function sampleData() {
  const fn = {
    name: "<Calculate>", description: "Calculate <values>", kind: "vectorize",
    args: { value: { type: "float" } }, return_type: "DataFrame",
    doc: { params: { value: "<Input>" }, examples: ['print("<script>")'], raises: [] },
    entrypoint: "example:calculate",
  };
  const column = { name: "value", label: "<Value>", role: "Output", type: "float" };
  return {
    format_version: 1,
    project: { name: "<Test project>", spec_version: 5 },
    scope: { label: "all features", is_scoped: false },
    catalogs: {
      configuration: {
        profiles: {
          readings: {
            name: "Readings", grain: [{ dimension: "machine", resolution: "machine" }],
            features: {
              id: { name: "Machine ID", type: "string" },
              value: { name: "<Value>", type: "float" },
            },
            assembly: { calculate: { compute: { function: "calculate", args: {} }, interface: { inputs: [], outputs: ["$features.value"] } } },
            scope: "one row per machine <source>",
          },
        },
        dimensions: {
          machine: {
            name: "Machine",
            resolutions: { machine: { key: "id", type: "string" } },
          },
        },
        functions: { calculate: fn },
      },
      summary: { profile_count: 1, operator_count: 1, dimension_count: 1,
        feature_count: 1, function_count: 1, feature_buckets: { input: 0, output: 1 },
        function_buckets: { vectorize: 1 } },
      function_groups: { vectorize: { calculate: fn } },
    },
    graphs: {
      feature_lineage: { nodes: [{ id: "value", label: "</script><script>alert(1)</script>" }], links: [] },
      invocation_lineage: { nodes: [], links: [] },
      feature_style: { function_color: "#ffffff", background_color: "#101820" },
      invocation_style: { background_color: "#101820" },
    },
    plan: { stage_count: 1, invocation_count: 1, function_count: 1, profile_count: 1,
      feature_count: 1, dependency_count: 0, max_parallel_invocations: 1,
      function_kind_counts: [["vectorize", 1]] },
    stages: [{ stage: 1, steps: [{
      title: "<Calculate>", function: "calculate", function_label: "Calculate",
      function_kind: "vectorize", profile: "readings", dataset: "readings",
      input_features: [], output_features: ["value"], depends_on_invocations: [],
      args: { value: { value: "<input>", type: { engine: "float" } } },
      returns: { type: { engine: "DataFrame" } }, row_context: null,
    }] }],
    animation: { stages: [[{
      number: 1, invocation_id: "calculate:readings", function_label: "Calculate",
      function: "calculate", profile: "readings", dataset: "readings", dataset_label: "Readings",
      operator: "<Calculate>", dependencies: [], columns: [column], main_columns: [column],
      kind: { id: "vectorize" }, input_tables: [], row_count: 3,
    }]] },
  };
}

module.exports = { sampleData, moduleAt };
