#!/usr/bin/env python3
"""
API Contract Validation Script

Validates OpenAPI specifications for completeness and consistency.

Usage:
    python3 validate-api-contract.py [--product-root PATH] <path-to-openapi-yaml>
    python3 validate-api-contract.py {PRODUCT_ROOT}/planning-mds/api/example-api.yaml
    python3 validate-api-contract.py /abs/path/to/openapi.yaml

A leading `{PRODUCT_ROOT}/` placeholder in the path is expanded to the resolved
product root.
"""

import argparse
import sys
import yaml
from pathlib import Path
from typing import Any, List, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from _product_root import add_product_root_arg, expand_product_root, resolve_product_root  # noqa: E402

class ApiContractValidator:
    ERROR_SCHEMA_NAME = 'ProblemDetails'
    ERROR_SCHEMA_REF = '#/components/schemas/ProblemDetails'

    def __init__(self, file_path: str):
        self.file_path = Path(file_path)
        self.spec = None
        self.errors = []
        self.warnings = []

    def load_spec(self) -> bool:
        """Load OpenAPI YAML spec."""
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                self.spec = yaml.safe_load(f)
            return True
        except Exception as e:
            self.errors.append(f"Failed to load API spec: {e}")
            return False

    def validate(self) -> Tuple[bool, List[str], List[str]]:
        """Validate API contract completeness and quality."""
        if not self.load_spec():
            return False, self.errors, self.warnings

        self.check_required_fields()
        self.check_paths()
        self.check_responses()
        self.check_error_contract()
        self.check_security()
        self.check_schemas()

        is_valid = len(self.errors) == 0
        return is_valid, self.errors, self.warnings

    def check_required_fields(self):
        """Check for required OpenAPI fields."""
        required = ['openapi', 'info', 'paths']
        for field in required:
            if field not in self.spec:
                self.errors.append(f"Missing required field: {field}")

        if 'info' in self.spec:
            info_required = ['title', 'version']
            for field in info_required:
                if field not in self.spec['info']:
                    self.errors.append(f"Missing required info field: {field}")

    def check_paths(self):
        """Check API paths follow REST conventions."""
        if 'paths' not in self.spec:
            return

        for path, methods in self.spec['paths'].items():
            # Check for verbs in path (should use HTTP methods instead)
            verb_indicators = ['get', 'post', 'put', 'delete', 'create', 'update', 'list']
            for verb in verb_indicators:
                if verb in path.lower():
                    self.warnings.append(f"Path '{path}' contains verb '{verb}' - use HTTP methods instead")

            # Paths should be absolute route templates and avoid legacy /api base prefixes.
            if not path.startswith('/'):
                self.warnings.append(f"Path '{path}' should start with '/'")
            if path == '/api' or path.startswith('/api/'):
                self.errors.append(
                    f"Path '{path}' uses forbidden legacy /api prefix; use root resource paths"
                )

            # Check each method
            for method in methods:
                if method not in ['get', 'post', 'put', 'patch', 'delete', 'options', 'head']:
                    continue

                operation = methods[method]

                # Check for operationId
                if 'operationId' not in operation:
                    self.warnings.append(f"{method.upper()} {path}: Missing operationId")

                # Check for summary
                if 'summary' not in operation:
                    self.warnings.append(f"{method.upper()} {path}: Missing summary")

                # Check for responses
                if 'responses' not in operation:
                    self.errors.append(f"{method.upper()} {path}: Missing responses")

    def check_responses(self):
        """Check response definitions."""
        if 'paths' not in self.spec:
            return

        for path, methods in self.spec['paths'].items():
            for method, operation in methods.items():
                if method not in ['get', 'post', 'put', 'patch', 'delete']:
                    continue

                if 'responses' not in operation:
                    continue

                responses = operation['responses']

                # Check for success response
                success_codes = ['200', '201', '204']
                has_success = any(code in responses for code in success_codes)
                if not has_success:
                    self.warnings.append(f"{method.upper()} {path}: No success response (200, 201, or 204)")

                # POST should return 201
                if method == 'post' and '201' not in responses:
                    self.warnings.append(f"POST {path}: Should return 201 Created")

                # DELETE should return 204
                if method == 'delete' and '204' not in responses:
                    self.warnings.append(f"DELETE {path}: Should return 204 No Content")

                # Check for error responses
                if '400' not in responses:
                    self.warnings.append(f"{method.upper()} {path}: Missing 400 Bad Request response")

                if '401' not in responses:
                    self.warnings.append(f"{method.upper()} {path}: Missing 401 Unauthorized response")

                if '403' not in responses:
                    self.warnings.append(f"{method.upper()} {path}: Missing 403 Forbidden response")

    def _resolve_local_ref(self, ref: str) -> Any:
        """Resolve local OpenAPI refs like #/components/schemas/Thing."""
        if not isinstance(ref, str) or not ref.startswith('#/'):
            return None

        node = self.spec
        for token in ref[2:].split('/'):
            if not isinstance(node, dict) or token not in node:
                return None
            node = node[token]
        return node

    def _extract_response_schema_ref(self, response: dict, context: str) -> str:
        """Resolve response object and return application/json schema $ref."""
        if not isinstance(response, dict):
            self.errors.append(f"{context}: response must be an object")
            return ''

        response_object = response
        if '$ref' in response:
            response_object = self._resolve_local_ref(response['$ref'])
            if not isinstance(response_object, dict):
                self.errors.append(f"{context}: invalid response reference {response['$ref']}")
                return ''

        content = response_object.get('content', {})
        json_content = content.get('application/json') or content.get('application/problem+json')
        if not isinstance(json_content, dict):
            self.errors.append(f"{context}: error responses must define application/json content")
            return ''

        schema = json_content.get('schema')
        if not isinstance(schema, dict):
            self.errors.append(f"{context}: error responses must define a schema")
            return ''

        schema_ref = schema.get('$ref')
        if not schema_ref:
            self.errors.append(f"{context}: error responses must reference {self.ERROR_SCHEMA_REF}")
            return ''

        return schema_ref

    def check_error_contract(self):
        """Check for canonical RFC 7807 ProblemDetails schema and usage."""
        if 'components' not in self.spec:
            self.warnings.append("Missing components section - define reusable schemas")
            return

        if 'schemas' not in self.spec['components']:
            self.warnings.append("Missing schemas in components")
            return

        schemas = self.spec['components']['schemas']

        if 'ErrorResponse' in schemas:
            self.errors.append(
                "Found legacy ErrorResponse schema - use canonical ProblemDetails schema only"
            )

        if self.ERROR_SCHEMA_NAME not in schemas:
            self.errors.append(
                f"Missing {self.ERROR_SCHEMA_NAME} schema - all APIs should use RFC 7807 format"
            )
            return

        error_schema = schemas[self.ERROR_SCHEMA_NAME]
        properties = error_schema.get('properties', {})
        required_fields = set(error_schema.get('required', []))

        required_properties = ['type', 'title', 'status', 'code', 'traceId']
        for field in required_properties:
            if field not in properties:
                self.errors.append(f"{self.ERROR_SCHEMA_NAME} missing required property: {field}")

        required_presence = ['type', 'title', 'status']
        for field in required_presence:
            if field not in required_fields:
                self.errors.append(f"{self.ERROR_SCHEMA_NAME} should require field: {field}")

        # Every operation-level 4xx/5xx response should reference ProblemDetails.
        paths = self.spec.get('paths', {})
        for path, methods in paths.items():
            if not isinstance(methods, dict):
                continue

            for method, operation in methods.items():
                if method not in ['get', 'post', 'put', 'patch', 'delete']:
                    continue
                if not isinstance(operation, dict):
                    continue

                responses = operation.get('responses', {})
                if not isinstance(responses, dict):
                    continue

                for status_code, response in responses.items():
                    status_str = str(status_code)
                    if not status_str or status_str[0] not in {'4', '5'}:
                        continue

                    context = f"{method.upper()} {path} {status_str}"
                    schema_ref = self._extract_response_schema_ref(response, context)
                    if schema_ref and schema_ref != self.ERROR_SCHEMA_REF:
                        self.errors.append(
                            f"{context}: expected {self.ERROR_SCHEMA_REF}, found {schema_ref}"
                        )

    def check_security(self):
        """Check security definitions."""
        if 'security' not in self.spec and 'securitySchemes' not in self.spec.get('components', {}):
            self.warnings.append("No security defined - all endpoints should require authentication")

    def check_schemas(self):
        """Check schema definitions."""
        if 'components' not in self.spec or 'schemas' not in self.spec['components']:
            return

        schemas = self.spec['components']['schemas']

        for schema_name, schema in schemas.items():
            # Check for description
            if 'description' not in schema and 'properties' not in schema:
                self.warnings.append(f"Schema '{schema_name}' missing description")

            # Check for required fields definition
            if 'properties' in schema and 'required' not in schema:
                self.warnings.append(f"Schema '{schema_name}' has properties but no 'required' array")

def main():
    parser = argparse.ArgumentParser(description="Validate OpenAPI contract")
    add_product_root_arg(parser)
    parser.add_argument(
        "file",
        help="Path to openapi YAML (relative paths are resolved against {PRODUCT_ROOT})",
    )
    args = parser.parse_args()

    product_root = resolve_product_root(args.product_root)
    raw_path = args.file
    if "{PRODUCT_ROOT}" in raw_path:
        file_path = str(expand_product_root(raw_path, product_root))
    elif Path(raw_path).is_absolute():
        file_path = raw_path
    else:
        candidate = Path(raw_path)
        if candidate.exists():
            file_path = str(candidate.resolve())
        else:
            file_path = str((product_root / raw_path).resolve())

    print(f"Validating API contract: {file_path}")
    print("-" * 60)

    validator = ApiContractValidator(file_path)
    is_valid, errors, warnings = validator.validate()

    # Print errors
    if errors:
        print("\n❌ ERRORS (Must Fix):")
        for i, error in enumerate(errors, 1):
            print(f"  {i}. {error}")

    # Print warnings
    if warnings:
        print("\n⚠️  WARNINGS (Should Fix):")
        for i, warning in enumerate(warnings, 1):
            print(f"  {i}. {warning}")

    # Print summary
    print("\n" + "=" * 60)
    if is_valid and not warnings:
        print("✅ API contract validation PASSED - No issues found!")
        sys.exit(0)
    elif is_valid:
        print(f"⚠️  API contract validation PASSED with {len(warnings)} warning(s)")
        sys.exit(0)
    else:
        print(f"❌ API contract validation FAILED with {len(errors)} error(s) and {len(warnings)} warning(s)")
        sys.exit(1)

if __name__ == "__main__":
    main()
