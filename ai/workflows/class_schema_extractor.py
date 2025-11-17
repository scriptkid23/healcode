"""
Utilities for extracting class schemas using tree-sitter (with graceful fallbacks).

Builds ClassDefinition objects for the workflow to index class structure across
error files and their dependents.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import List, Optional, Iterable, Set

from ai.workflows.config import SecurityConfig, LanguageConfig
from ai.workflows.enhanced_parsers import TreeSitterParser
from ai.workflows.state import (
    ClassDefinition,
    ClassField,
    ClassMethod,
    MethodParameter,
)


class ClassSchemaExtractor:
    """Extract class structure (fields/methods) from source files."""

    def __init__(self, security_config: SecurityConfig, language_config: LanguageConfig):
        self.security_config = security_config
        self.language_config = language_config
        # Map language identifiers to extractor functions for easy extensibility
        self.extractor_registry = {
            "python": self._extract_python_classes,
            "java": self._extract_java_classes,
        }

    def extract_class_definitions(
        self, file_content: str, file_path: str
    ) -> List[ClassDefinition]:
        """Dispatch extraction based on language inferred from file extension."""
        language = self._get_language_from_path(file_path)

        extractor = self.extractor_registry.get(language)
        if extractor:
            return extractor(file_content, file_path)

        # Unsupported languages return empty schema
        return []

    def _get_language_from_path(self, file_path: str) -> str:
        """Determine language from file extension"""
        ext = Path(file_path).suffix.lower()
        
        language_map = {
            '.py': 'python',
            '.java': 'java',
            '.js': 'javascript',
            '.jsx': 'javascript',
            '.ts': 'typescript',
            '.tsx': 'typescript',
            '.rs': 'rust'
        }
        
        return language_map.get(ext, 'unknown')

    def _extract_python_classes(
        self, file_content: str, file_path: str
    ) -> List[ClassDefinition]:
        """Prefer tree-sitter for Python, fallback to AST for reliability."""
        ts_results = self._extract_python_tree_sitter(file_content, file_path)
        if ts_results:
            return ts_results

        try:
            tree = ast.parse(file_content)
        except SyntaxError:
            return []

        definitions: List[ClassDefinition] = []

        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                parent = None
                if node.bases:
                    base = node.bases[0]
                    parent = self._annotation_to_str(base)

                fields: List[ClassField] = []
                methods: List[ClassMethod] = []

                for body_node in node.body:
                    if isinstance(body_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        params = []
                        for arg in body_node.args.args:
                            if arg.arg in {"self", "cls"}:
                                continue
                            params.append(
                                MethodParameter(
                                    name=arg.arg,
                                    data_type=self._annotation_to_str(arg.annotation),
                                )
                            )
                        return_type = self._annotation_to_str(body_node.returns)
                        visibility = self._visibility_from_identifier(body_node.name)
                        methods.append(
                            ClassMethod(
                                name=body_node.name,
                                parameters=params,
                                return_type=return_type or "Any",
                                visibility=visibility,
                            )
                        )
                    elif isinstance(body_node, (ast.Assign, ast.AnnAssign)):
                        target = None
                        if isinstance(body_node, ast.Assign) and body_node.targets:
                            t = body_node.targets[0]
                            if isinstance(t, ast.Name):
                                target = t.id
                        elif isinstance(body_node, ast.AnnAssign) and isinstance(
                            body_node.target, ast.Name
                        ):
                            target = body_node.target.id

                        if target:
                            annotation = None
                            if isinstance(body_node, ast.AnnAssign):
                                annotation = self._annotation_to_str(body_node.annotation)
                            fields.append(
                                ClassField(
                                    name=target,
                                    data_type=annotation or "any",
                                    visibility=self._visibility_from_identifier(target),
                                )
                            )

                definitions.append(
                    ClassDefinition(
                        name=node.name,
                        file_path=file_path,
                        parent_class=parent,
                        fields=fields,
                        methods=methods,
                    )
                )

        return definitions

    def _extract_python_tree_sitter(
        self, file_content: str, file_path: str
    ) -> List[ClassDefinition]:
        try:
            parser = TreeSitterParser("python", self.security_config)
            result = parser.parse(file_content, file_path)
        except Exception:
            return []

        definitions: List[ClassDefinition] = []
        root = result.tree.root_node  # type: ignore[attr-defined]

        for class_node in self._find_descendants(root, {"class_definition"}):
            name_node = class_node.child_by_field_name("name")
            if not name_node:
                # Fallback: first identifier child
                name_node = next(
                    (c for c in class_node.children if c.type == "identifier"), None
                )
            if not name_node:
                continue

            parent = None
            superclass_node = class_node.child_by_field_name("superclasses")
            if superclass_node:
                parent = self._node_text(superclass_node, file_content).strip("()")
            else:
                arg_list = next(
                    (c for c in class_node.children if c.type == "argument_list"), None
                )
                if arg_list:
                    parent = self._node_text(arg_list, file_content).strip("()")

            body = class_node.child_by_field_name("body") or next(
                (c for c in class_node.children if c.type == "block"), None
            )

            fields: List[ClassField] = []
            methods: List[ClassMethod] = []

            for stmt in getattr(body, "children", []):
                if stmt.type == "function_definition":
                    method_name_node = stmt.child_by_field_name("name") or next(
                        (c for c in stmt.children if c.type == "identifier"), None
                    )
                    method_name = self._node_text(method_name_node, file_content)
                    params_node = stmt.child_by_field_name("parameters")
                    params: List[MethodParameter] = []
                    for ident in self._find_descendants(params_node, {"identifier"}):
                        name = self._node_text(ident, file_content)
                        if name in {"self", "cls"}:
                            continue
                        params.append(MethodParameter(name=name, data_type="any"))
                    methods.append(
                        ClassMethod(
                            name=method_name,
                            parameters=params,
                            return_type="Any",
                            visibility=self._visibility_from_identifier(method_name),
                        )
                    )
                elif stmt.type == "expression_statement":
                    assignment = next(
                        (
                            c
                            for c in stmt.children
                            if c.type in {"assignment", "augmented_assignment", "annassign"}
                        ),
                        None,
                    )
                    target_node = None
                    if assignment:
                        target_node = assignment.child_by_field_name("left") or next(
                            (c for c in assignment.children if c.type == "identifier"),
                            None,
                        )
                    if target_node:
                        field_name = self._node_text(target_node, file_content)
                        fields.append(
                            ClassField(
                                name=field_name,
                                data_type="any",
                                visibility=self._visibility_from_identifier(field_name),
                            )
                        )

            definitions.append(
                ClassDefinition(
                    name=self._node_text(name_node, file_content),
                    file_path=file_path,
                    parent_class=parent,
                    fields=fields,
                    methods=methods,
                )
            )

        return definitions

    def _extract_java_classes(
        self, file_content: str, file_path: str
    ) -> List[ClassDefinition]:
        """Use tree-sitter to build Java class schemas."""
        try:
            parser = TreeSitterParser("java", self.security_config)
            result = parser.parse(file_content, file_path)
        except Exception:
            return []

        definitions: List[ClassDefinition] = []
        root = result.tree.root_node  # type: ignore[attr-defined]
        stack = [root]

        while stack:
            node = stack.pop()
            if node.type == "class_declaration":
                class_def = self._build_java_class(node, file_content, file_path)
                if class_def:
                    definitions.append(class_def)
            stack.extend(node.children)

        return definitions

    def _build_java_class(
        self, node, file_content: str, file_path: str
    ) -> Optional[ClassDefinition]:
        name_node = node.child_by_field_name("name")
        if not name_node:
            return None

        class_name = self._node_text(name_node, file_content)
        parent = None
        parent_node = node.child_by_field_name("superclass")
        if parent_node:
            parent = self._node_text(parent_node, file_content)

        body = node.child_by_field_name("body")
        fields: List[ClassField] = []
        methods: List[ClassMethod] = []

        for member in self._find_descendants(
            body, {"field_declaration", "method_declaration", "constructor_declaration"}
        ):
            snippet = self._node_text(member, file_content)
            visibility = self._guess_visibility(snippet)

            if member.type == "field_declaration":
                type_node = member.child_by_field_name("type")
                data_type = self._node_text(type_node, file_content) if type_node else "any"
                for declarator in self._find_descendants(member, {"variable_declarator"}):
                    name_part = declarator.child_by_field_name("name")
                    field_name = self._node_text(name_part, file_content)
                    fields.append(
                        ClassField(
                            name=field_name,
                            data_type=data_type or "any",
                            visibility=visibility,
                        )
                    )

            elif member.type in {"method_declaration", "constructor_declaration"}:
                name_part = member.child_by_field_name("name")
                method_name = self._node_text(name_part, file_content)
                params: List[MethodParameter] = []
                parameters_node = member.child_by_field_name("parameters")

                if parameters_node:
                    for param in self._find_descendants(parameters_node, {"formal_parameter"}):
                        param_name_node = param.child_by_field_name("name")
                        param_type_node = param.child_by_field_name("type")
                        params.append(
                            MethodParameter(
                                name=self._node_text(param_name_node, file_content),
                                data_type=self._node_text(param_type_node, file_content)
                                or "any",
                            )
                        )

                return_node = member.child_by_field_name("type")
                return_type = (
                    self._node_text(return_node, file_content) if return_node else class_name
                )
                methods.append(
                    ClassMethod(
                        name=method_name,
                        parameters=params,
                        return_type=return_type or "void",
                        visibility=visibility,
                    )
                )

        return ClassDefinition(
            name=class_name,
            file_path=file_path,
            parent_class=parent,
            fields=fields,
            methods=methods,
        )

    def _annotation_to_str(self, node: Optional[ast.AST]) -> str:
        if node is None:
            return "any"
        try:
            return ast.unparse(node)  # type: ignore[attr-defined]
        except Exception:
            return getattr(node, "id", "any")

    def _node_text(self, node, content: str) -> str:
        if not node:
            return ""
        return content[node.start_byte : node.end_byte]  # type: ignore[index]

    def _find_descendants(self, node, kinds: Set[str]) -> Iterable:
        if not node:
            return []
        stack = [node]
        while stack:
            current = stack.pop()
            if current.type in kinds:
                yield current
            stack.extend(current.children)

    def _guess_visibility(self, snippet: str) -> str:
        lowered = snippet.lower()
        if "private" in lowered:
            return "private"
        if "protected" in lowered:
            return "protected"
        return "public"

    def _visibility_from_identifier(self, name: str) -> str:
        if name.startswith("__"):
            return "private"
        if name.startswith("_"):
            return "protected"
        return "public"
