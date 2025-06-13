#!/usr/bin/env python3
"""
Auto-documentation generator for Claude Conductor
Extracts docstrings and type hints to generate comprehensive API documentation
"""

import ast
import inspect
import os
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional
import importlib.util


class DocstringExtractor:
    """Extract and format docstrings from Python modules"""
    
    def __init__(self):
        self.classes = {}
        self.functions = {}
        self.modules = {}
    
    def extract_from_file(self, file_path: str) -> Dict[str, Any]:
        """Extract documentation from a Python file"""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        try:
            tree = ast.parse(content)
        except SyntaxError as e:
            print(f"Warning: Could not parse {file_path}: {e}")
            return {}
        
        file_docs = {
            'module_docstring': ast.get_docstring(tree),
            'classes': {},
            'functions': {},
            'imports': []
        }
        
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                file_docs['classes'][node.name] = self._extract_class_info(node)
            elif isinstance(node, ast.FunctionDef) and not self._is_method(node, tree):
                file_docs['functions'][node.name] = self._extract_function_info(node)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    file_docs['imports'].append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ''
                for alias in node.names:
                    file_docs['imports'].append(f"{module}.{alias.name}")
        
        return file_docs
    
    def _extract_class_info(self, node: ast.ClassDef) -> Dict[str, Any]:
        """Extract class information including methods and attributes"""
        class_info = {
            'docstring': ast.get_docstring(node),
            'methods': {},
            'attributes': [],
            'bases': [base.id if hasattr(base, 'id') else str(base) for base in node.bases]
        }
        
        for item in node.body:
            if isinstance(item, ast.FunctionDef):
                class_info['methods'][item.name] = self._extract_function_info(item)
            elif isinstance(item, ast.AnnAssign) and hasattr(item.target, 'id'):
                # Extract annotated attributes
                attr_name = item.target.id
                attr_type = self._get_type_annotation(item.annotation)
                class_info['attributes'].append({
                    'name': attr_name,
                    'type': attr_type
                })
        
        return class_info
    
    def _extract_function_info(self, node: ast.FunctionDef) -> Dict[str, Any]:
        """Extract function information including parameters and return type"""
        func_info = {
            'docstring': ast.get_docstring(node),
            'parameters': [],
            'return_type': None,
            'decorators': []
        }
        
        # Extract decorators
        for decorator in node.decorator_list:
            if hasattr(decorator, 'id'):
                func_info['decorators'].append(decorator.id)
            elif hasattr(decorator, 'attr'):
                func_info['decorators'].append(decorator.attr)
        
        # Extract parameters
        for arg in node.args.args:
            param_info = {
                'name': arg.arg,
                'type': self._get_type_annotation(arg.annotation) if arg.annotation else None,
                'default': None
            }
            func_info['parameters'].append(param_info)
        
        # Extract defaults
        defaults = node.args.defaults
        if defaults:
            # Match defaults to parameters (defaults are for the last N parameters)
            num_defaults = len(defaults)
            for i, default in enumerate(defaults):
                param_idx = len(func_info['parameters']) - num_defaults + i
                if param_idx >= 0 and param_idx < len(func_info['parameters']):
                    func_info['parameters'][param_idx]['default'] = self._get_default_value(default)
        
        # Extract return type
        if node.returns:
            func_info['return_type'] = self._get_type_annotation(node.returns)
        
        return func_info
    
    def _get_type_annotation(self, annotation) -> str:
        """Convert AST type annotation to string"""
        if annotation is None:
            return None
        
        if hasattr(annotation, 'id'):
            return annotation.id
        elif hasattr(annotation, 'attr'):
            return f"{self._get_type_annotation(annotation.value)}.{annotation.attr}"
        elif isinstance(annotation, ast.Subscript):
            base = self._get_type_annotation(annotation.value)
            slice_val = self._get_type_annotation(annotation.slice)
            return f"{base}[{slice_val}]"
        elif isinstance(annotation, ast.Tuple):
            elements = [self._get_type_annotation(elt) for elt in annotation.elts]
            return f"({', '.join(elements)})"
        elif isinstance(annotation, ast.Constant):
            return repr(annotation.value)
        else:
            return str(annotation)
    
    def _get_default_value(self, default_node) -> str:
        """Extract default value from AST node"""
        if isinstance(default_node, ast.Constant):
            return repr(default_node.value)
        elif isinstance(default_node, ast.Name):
            return default_node.id
        elif isinstance(default_node, ast.Attribute):
            return f"{self._get_default_value(default_node.value)}.{default_node.attr}"
        else:
            return "..."
    
    def _is_method(self, node: ast.FunctionDef, tree: ast.AST) -> bool:
        """Check if function is a method (inside a class)"""
        for parent_node in ast.walk(tree):
            if isinstance(parent_node, ast.ClassDef):
                if node in parent_node.body:
                    return True
        return False


class MarkdownGenerator:
    """Generate Markdown documentation from extracted information"""
    
    def __init__(self):
        self.output = []
    
    def generate_module_docs(self, module_name: str, module_info: Dict[str, Any]) -> str:
        """Generate documentation for a module"""
        self.output = []
        
        self._add_header(f"{module_name}", level=1)
        
        if module_info.get('module_docstring'):
            self._add_text(module_info['module_docstring'])
            self._add_newline()
        
        # Generate classes documentation
        if module_info.get('classes'):
            self._add_header("Classes", level=2)
            for class_name, class_info in module_info['classes'].items():
                self._generate_class_docs(class_name, class_info)
        
        # Generate functions documentation
        if module_info.get('functions'):
            self._add_header("Functions", level=2)
            for func_name, func_info in module_info['functions'].items():
                self._generate_function_docs(func_name, func_info)
        
        return '\n'.join(self.output)
    
    def _generate_class_docs(self, class_name: str, class_info: Dict[str, Any]):
        """Generate documentation for a class"""
        self._add_header(f"{class_name}", level=3)
        
        if class_info.get('bases'):
            bases_str = ', '.join(class_info['bases'])
            self._add_text(f"**Inherits from:** {bases_str}")
            self._add_newline()
        
        if class_info.get('docstring'):
            self._add_text(class_info['docstring'])
            self._add_newline()
        
        # Attributes
        if class_info.get('attributes'):
            self._add_header("Attributes", level=4)
            for attr in class_info['attributes']:
                attr_line = f"- `{attr['name']}`"
                if attr['type']:
                    attr_line += f" ({attr['type']})"
                self._add_text(attr_line)
            self._add_newline()
        
        # Methods
        if class_info.get('methods'):
            self._add_header("Methods", level=4)
            for method_name, method_info in class_info['methods'].items():
                if not method_name.startswith('_'):  # Skip private methods
                    self._generate_method_docs(method_name, method_info)
    
    def _generate_function_docs(self, func_name: str, func_info: Dict[str, Any]):
        """Generate documentation for a function"""
        self._add_header(f"{func_name}", level=3)
        
        # Function signature
        params = []
        for param in func_info.get('parameters', []):
            param_str = param['name']
            if param['type']:
                param_str += f": {param['type']}"
            if param['default'] is not None:
                param_str += f" = {param['default']}"
            params.append(param_str)
        
        signature = f"`{func_name}({', '.join(params)})`"
        if func_info.get('return_type'):
            signature += f" -> {func_info['return_type']}"
        
        self._add_text(signature)
        self._add_newline()
        
        if func_info.get('docstring'):
            self._add_text(func_info['docstring'])
            self._add_newline()
        
        self._generate_parameter_docs(func_info.get('parameters', []))
    
    def _generate_method_docs(self, method_name: str, method_info: Dict[str, Any]):
        """Generate documentation for a method"""
        self._add_header(f"{method_name}", level=5)
        
        # Method signature (skip 'self' parameter)
        params = method_info.get('parameters', [])
        if params and params[0]['name'] == 'self':
            params = params[1:]
        
        param_strs = []
        for param in params:
            param_str = param['name']
            if param['type']:
                param_str += f": {param['type']}"
            if param['default'] is not None:
                param_str += f" = {param['default']}"
            param_strs.append(param_str)
        
        signature = f"`{method_name}({', '.join(param_strs)})`"
        if method_info.get('return_type'):
            signature += f" -> {method_info['return_type']}"
        
        self._add_text(signature)
        self._add_newline()
        
        if method_info.get('docstring'):
            self._add_text(method_info['docstring'])
            self._add_newline()
        
        self._generate_parameter_docs(params)
    
    def _generate_parameter_docs(self, parameters: List[Dict[str, Any]]):
        """Generate parameter documentation"""
        if not parameters:
            return
        
        self._add_text("**Parameters:**")
        for param in parameters:
            param_doc = f"- `{param['name']}`"
            if param['type']:
                param_doc += f" ({param['type']})"
            if param['default'] is not None:
                param_doc += f" = {param['default']}"
            self._add_text(param_doc)
        self._add_newline()
    
    def _add_header(self, text: str, level: int = 1):
        """Add a header to the output"""
        self.output.append(f"{'#' * level} {text}")
        self.output.append("")
    
    def _add_text(self, text: str):
        """Add text to the output"""
        self.output.append(text)
    
    def _add_newline(self):
        """Add a newline to the output"""
        self.output.append("")


def generate_api_docs(source_dir: str, output_dir: str):
    """Generate API documentation for all Python modules in source directory"""
    source_path = Path(source_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    extractor = DocstringExtractor()
    generator = MarkdownGenerator()
    
    # Find all Python files
    python_files = list(source_path.rglob("*.py"))
    
    # Generate documentation for each module
    for py_file in python_files:
        if py_file.name.startswith('__'):
            continue  # Skip __init__.py and __pycache__
        
        print(f"Processing {py_file}")
        
        try:
            module_info = extractor.extract_from_file(str(py_file))
            
            # Generate module name from file path
            relative_path = py_file.relative_to(source_path)
            module_name = str(relative_path.with_suffix('')).replace('/', '.')
            
            # Generate documentation
            docs = generator.generate_module_docs(module_name, module_info)
            
            # Write to output file
            output_file = output_path / f"{module_name.replace('.', '_')}.md"
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(docs)
            
            print(f"Generated documentation: {output_file}")
            
        except Exception as e:
            print(f"Error processing {py_file}: {e}")


def main():
    """Main entry point"""
    if len(sys.argv) != 3:
        print("Usage: python generate_docs.py <source_dir> <output_dir>")
        sys.exit(1)
    
    source_dir = sys.argv[1]
    output_dir = sys.argv[2]
    
    if not os.path.exists(source_dir):
        print(f"Error: Source directory '{source_dir}' does not exist")
        sys.exit(1)
    
    print(f"Generating API documentation from {source_dir} to {output_dir}")
    generate_api_docs(source_dir, output_dir)
    print("Documentation generation complete!")


if __name__ == "__main__":
    main()