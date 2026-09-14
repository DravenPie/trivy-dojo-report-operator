import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

import yaml

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
CHART_PATH = REPOSITORY_ROOT / "charts"
DEFAULT_VALUES_PATH = CHART_PATH / "values.yaml"
DISTRIBUTED_MANIFEST_PATH = (
    REPOSITORY_ROOT / "deploy" / "trivy-dojo-report-operator.yaml"
)


class HelmTagsTest(unittest.TestCase):
    @staticmethod
    def render_chart(*additional_args: str) -> str:
        result = subprocess.run(
            [
                "helm",
                "template",
                "telekom-mms",
                str(CHART_PATH),
                "--values",
                str(DEFAULT_VALUES_PATH),
                "--namespace",
                "default",
                *additional_args,
            ],
            check=True,
            capture_output=True,
            cwd=REPOSITORY_ROOT,
            text=True,
        )
        return result.stdout

    @staticmethod
    def deployment_environment(rendered_chart: str) -> dict[str, str]:
        deployment = next(
            document
            for document in yaml.safe_load_all(rendered_chart)
            if document and document.get("kind") == "Deployment"
        )
        environment = deployment["spec"]["template"]["spec"]["containers"][0]["env"]
        return {entry["name"]: entry.get("value") for entry in environment}

    def test_default_tags_values_are_exported_as_environment_variables(self) -> None:
        environment = self.deployment_environment(self.render_chart())

        self.assertEqual(
            {
                name: environment[name]
                for name in (
                    "DEFECT_DOJO_TAGS",
                    "DEFECT_DOJO_EVAL_TAGS",
                    "DEFECT_DOJO_APPLY_TAGS_TO_FINDINGS",
                    "DEFECT_DOJO_APPLY_TAGS_TO_ENDPOINTS",
                    "DEFECT_DOJO_VERSION",
                    "DEFECT_DOJO_APPLY_TAGS_TO_PRODUCT",
                    "DEFECT_DOJO_ENABLE_PRODUCT_TAG_INHERITANCE",
                )
            },
            {
                "DEFECT_DOJO_TAGS": "",
                "DEFECT_DOJO_EVAL_TAGS": "false",
                "DEFECT_DOJO_APPLY_TAGS_TO_FINDINGS": "false",
                "DEFECT_DOJO_APPLY_TAGS_TO_ENDPOINTS": "false",
                "DEFECT_DOJO_VERSION": "",
                "DEFECT_DOJO_APPLY_TAGS_TO_PRODUCT": "false",
                "DEFECT_DOJO_ENABLE_PRODUCT_TAG_INHERITANCE": "false",
            },
        )

    def test_evaluated_tags_expression_is_exported_without_changes(self) -> None:
        expression = textwrap.dedent("""\
            [
              'time:platform',
              'env:hml',
              'namespace:demo',
            ]""")
        values_override = (
            "operator:\n"
            "  trivyDojoReportOperator:\n"
            "    env:\n"
            "      defectDojoTags: |-\n"
            f"{textwrap.indent(expression, '        ')}\n"
            '      defectDojoEvalTags: "true"\n'
            '      defectDojoApplyTagsToFindings: "true"\n'
            '      defectDojoApplyTagsToEndpoints: "true"\n'
            '      defectDojoVersion: "v1.2.3"\n'
            '      defectDojoApplyTagsToProduct: "true"\n'
            '      defectDojoEnableProductTagInheritance: "true"\n'
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            override_path = Path(temporary_directory) / "tags-values.yaml"
            override_path.write_text(values_override)
            environment = self.deployment_environment(
                self.render_chart("--values", str(override_path))
            )

        self.assertEqual(environment["DEFECT_DOJO_TAGS"], expression)
        self.assertEqual(environment["DEFECT_DOJO_EVAL_TAGS"], "true")
        self.assertEqual(environment["DEFECT_DOJO_APPLY_TAGS_TO_FINDINGS"], "true")
        self.assertEqual(environment["DEFECT_DOJO_APPLY_TAGS_TO_ENDPOINTS"], "true")
        self.assertEqual(environment["DEFECT_DOJO_VERSION"], "v1.2.3")
        self.assertEqual(environment["DEFECT_DOJO_APPLY_TAGS_TO_PRODUCT"], "true")
        self.assertEqual(
            environment["DEFECT_DOJO_ENABLE_PRODUCT_TAG_INHERITANCE"], "true"
        )

    def test_distributed_manifest_matches_the_canonical_render(self) -> None:
        self.assertEqual(
            DISTRIBUTED_MANIFEST_PATH.read_text(),
            self.render_chart(),
        )


if __name__ == "__main__":
    unittest.main()
