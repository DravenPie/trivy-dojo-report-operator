import os
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

os.environ["DEFECT_DOJO_API_KEY"] = "test-api-key"
os.environ["DEFECT_DOJO_URL"] = "https://defectdojo.example.test"

with patch("prometheus_client.start_http_server"):
    import handlers


class Response:
    def __init__(self, data: dict) -> None:
        self.data = data
        self.content = b""

    def json(self) -> dict:
        return self.data

    def raise_for_status(self) -> None:
        return None


class HandlerTagsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.settings_patch = patch.multiple(
            handlers.settings,
            DEFECT_DOJO_APPLY_TAGS_TO_FINDINGS=True,
            DEFECT_DOJO_APPLY_TAGS_TO_ENDPOINTS=True,
            DEFECT_DOJO_APPLY_TAGS_TO_PRODUCT=True,
            DEFECT_DOJO_AUTO_CREATE_CONTEXT=True,
            DEFECT_DOJO_ENABLE_PRODUCT_TAG_INHERITANCE=True,
            DEFECT_DOJO_EVAL_TAGS=False,
            DEFECT_DOJO_PRODUCT_NAME="new-product",
            DEFECT_DOJO_PRODUCT_TYPE_NAME="Platform",
            DEFECT_DOJO_TAGS="team:platform,env:hml",
            DEFECT_DOJO_VERSION="v1.2.3",
        )
        self.settings_patch.start()
        self.addCleanup(self.settings_patch.stop)

    @staticmethod
    def send_report() -> None:
        handlers.send_to_dojo(
            body={"kind": "VulnerabilityReport"},
            meta={"name": "synthetic-report"},
            logger=Mock(),
        )

    def test_creates_new_product_with_tags_and_reimport_options(self) -> None:
        with (
            patch.object(
                handlers.requests,
                "get",
                side_effect=[
                    Response({"count": 0}),
                    Response({"count": 1, "results": [{"id": 42}]}),
                ],
            ),
            patch.object(
                handlers.requests,
                "post",
                side_effect=[Response({}), Response({})],
            ) as post,
        ):
            self.send_report()

        product_request, reimport_request = post.call_args_list
        self.assertEqual(
            product_request.args[0],
            "https://defectdojo.example.test/api/v2/products/",
        )
        self.assertEqual(
            product_request.kwargs["json"],
            {
                "name": "new-product",
                "description": "",
                "prod_type": 42,
                "enable_product_tag_inheritance": True,
                "tags": ["team:platform", "env:hml"],
            },
        )
        self.assertEqual(
            reimport_request.args[0],
            "https://defectdojo.example.test/api/v2/reimport-scan/",
        )
        self.assertEqual(
            reimport_request.kwargs["data"]["apply_tags_to_findings"], True
        )
        self.assertEqual(
            reimport_request.kwargs["data"]["apply_tags_to_endpoints"], True
        )
        self.assertEqual(reimport_request.kwargs["data"]["version"], "v1.2.3")
        self.assertNotIn("product_type_name", reimport_request.kwargs["data"])

    def test_does_not_change_existing_product_and_omits_empty_version(self) -> None:
        handlers.settings.DEFECT_DOJO_VERSION = ""

        with (
            patch.object(
                handlers.requests,
                "get",
                return_value=Response({"count": 1}),
            ),
            patch.object(
                handlers.requests,
                "post",
                return_value=Response({}),
            ) as post,
        ):
            self.send_report()

        self.assertEqual(post.call_count, 1)
        self.assertEqual(
            post.call_args.args[0],
            "https://defectdojo.example.test/api/v2/reimport-scan/",
        )
        self.assertNotIn("version", post.call_args.kwargs["data"])

    def test_does_not_create_product_when_auto_create_is_disabled(self) -> None:
        handlers.settings.DEFECT_DOJO_AUTO_CREATE_CONTEXT = False

        with (
            patch.object(
                handlers.requests,
                "get",
                return_value=Response({"count": 0}),
            ),
            patch.object(
                handlers.requests,
                "post",
                return_value=Response({}),
            ) as post,
        ):
            self.send_report()

        self.assertEqual(post.call_count, 1)
        self.assertEqual(
            post.call_args.args[0],
            "https://defectdojo.example.test/api/v2/reimport-scan/",
        )


if __name__ == "__main__":
    unittest.main()
