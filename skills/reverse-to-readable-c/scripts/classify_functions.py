#!/usr/bin/env python3
"""
增强版函数分类器 - 图算法 + 字符串传播（改进版）

改进：
1. 限制传播范围（只传播到直接邻居，深度=1）
2. 增加 "模块核心度" 计算（避免过度传播）
3. 区分传播质量（向上/向下传播分置信度）
"""

import json
import sys
from collections import defaultdict, Counter
from typing import Dict, List, Tuple, Set


class ImprovedFunctionClassifier:
    """改进版函数分类器 - 避免过度传播"""

    def __init__(self, callgraph_json: str, string_xref_md: str = None):
        self.callgraph_json = callgraph_json
        self.string_xref_md = string_xref_md

        # 图数据
        self.in_degree = Counter()
        self.out_degree = Counter()
        self.functions = set()
        self.callers = defaultdict(set)
        self.callees = defaultdict(set)

        # 字符串引用
        self.string_refs = {}

        # 分类传播缓存
        self.func_to_module = {}

        # 模块关键词（更精确）
        self.module_keywords = {
            'steam_errors': {
                'required': ['invalid_steam', 'invalid_password', 'invalid_email', 'invalid_login'],
                'optional': ['steam', 'valve', 'hsteamuser', 'hsteampipe', 'cached_credential']
            },
            'json_parser': {
                'required': ['parse_error', 'syntax_error'],
                'optional': ['json', 'invalid_string', 'invalid_number', 'utf_8']
            },
            'cli_parser': {
                'required': ['usage:', '--help', '--version'],
                'optional': ['argument', 'parse_args']
            },
            'filesystem': {
                'required': ['filesystem_error'],
                'optional': ['invalid_filesystem', 'invalid_backup_path']
            },
            'config': {
                'required': ['invalid_configuration'],
                'optional': ['configuration', 'version mismatch']
            },
            'network': {
                'required': ['wsastartup', 'wsacleanup'],
                'optional': ['socket', 'connect', 'bind']
            }
        }

        self._load_callgraph()
        if string_xref_md:
            self._load_string_xref()

    def _load_callgraph(self):
        """加载调用图"""
        with open(self.callgraph_json, 'r') as f:
            data = json.load(f)

        for func in data:
            caller = func['name']
            self.functions.add(caller)
            imports = func.get('imports', [])
            self.out_degree[caller] = len(imports)

            for callee in imports:
                if callee:
                    self.in_degree[callee] += 1
                    self.callers[callee].add(caller)
                    self.callees[caller].add(callee)
                    self.functions.add(callee)

    def _load_string_xref(self):
        """加载字符串交叉引用"""
        with open(self.string_xref_md, 'r') as f:
            for line in f:
                if '->' in line and 'str.' in line:
                    try:
                        parts = line.split(':', 1)
                        if len(parts) >= 2:
                            rest = parts[1].strip()
                            if '->' in rest:
                                func_part, string_part = rest.split('->', 1)
                                func_name = func_part.strip()
                                string_desc = string_part.strip()
                                if string_desc.startswith('str.'):
                                    string_desc = string_desc[4:]
                                if '  0x' in string_desc:
                                    string_desc = string_desc.split('  0x')[0]

                                if func_name not in self.string_refs:
                                    self.string_refs[func_name] = set()
                                self.string_refs[func_name].add(string_desc.lower())
                    except:
                        pass

    def _classify_by_strings(self, func_name: str) -> Tuple[str, str, float]:
        """
        基于字符串内容分类（改进版）

        使用 required/optional 关键词，避免过度匹配
        """
        if func_name not in self.string_refs:
            return None, '', 0.0

        strings = ' '.join(self.string_refs[func_name]).lower()

        # 检查每个模块
        for module, keywords in self.module_keywords.items():
            required = keywords.get('required', [])
            optional = keywords.get('optional', [])

            # 必须匹配至少一个 required 关键词
            required_match = any(kw in strings for kw in required)
            optional_match = any(kw in strings for kw in optional)

            if required_match or optional_match:
                confidence = 0.95 if required_match else 0.7
                return module, f'{module}_func', confidence

        return None, '', 0.0

    def _propagate_classification_limited(self, func_name: str, max_depth: int = 1,
                                          visited: Set = None) -> Dict[str, Tuple]:
        """
        限制性传播分类（避免过度传播）

        改进：
        1. 默认深度=1（只传播到直接邻居）
        2. 只传播到"核心度"低的函数（避免影响 hub 节点）
        3. 如果函数已经有明确分类，不覆盖
        """
        if visited is None:
            visited = set()

        if func_name in visited or max_depth > 1:
            return {}
        visited.add(func_name)

        propagated = {}
        module_info = self.func_to_module.get(func_name)

        if not module_info:
            return propagated

        module = module_info['module']

        # 向上传播（调用者）：只传播到入度<=10的函数
        # 避免将 hub 节点错误标记
        for caller in self.callers.get(func_name, set()):
            if caller not in self.func_to_module and self.in_degree[caller] <= 10:
                confidence = 0.5
                if caller.startswith('sym.') or caller.startswith('sub.'):
                    continue  # 跳过系统函数
                propagated[caller] = (module, f'called_{module}', confidence)

        # 向下传播（被调用者）：只传播到出度<=5的函数
        # 避免影响复杂的下级函数
        for callee in self.callees.get(func_name, set()):
            if callee not in self.func_to_module and self.out_degree[callee] <= 5:
                confidence = 0.4
                if callee.startswith('sym.') or callee.startswith('sub.'):
                    continue  # 跳过系统函数
                propagated[callee] = (module, f'{module}_helper', confidence)

        # 递归传播（仅在深度=1时）
        if max_depth == 1:
            for next_func in list(propagated.keys()):
                # 限制递归范围
                if len(propagated) < 50:  # 最多传播50个函数
                    propagated.update(self._propagate_classification_limited(
                        next_func, max_depth + 1, visited
                    ))

        return propagated

    def classify(self, func_name: str) -> Tuple[str, str, float]:
        """
        分类单个函数（多层策略）
        """
        in_deg = self.in_degree[func_name]
        out_deg = self.out_degree[func_name]

        # === Layer 1: 已知模式匹配 ===

        if func_name.startswith('sub.msvcrt.dll_'):
            clean_name = func_name.replace('sub.msvcrt.dll_', '').replace('_', '.')
            return ('[SKIP: msvcrt]', clean_name, 1.0)

        if func_name.startswith('sym.imp.'):
            lib_name = func_name.split('.')[2] if '.' in func_name else 'winapi'
            return (f'[SKIP: {lib_name}]', func_name.replace('sym.imp.', ''), 1.0)

        if func_name.startswith('sub.'):
            return ('[SKIP: thirdparty]', func_name, 0.9)

        # === Layer 2: 字符串内容匹配 ===

        module, reason, conf = self._classify_by_strings(func_name)
        if module:
            return module, f'{module}_func', conf

        # === Layer 3: 传播分类 ===

        if func_name in self.func_to_module:
            module_info = self.func_to_module[func_name]
            confidence = module_info.get('confidence', 0.6)
            return module_info['module'], module_info.get('clean_name', 'related'), confidence

        # === Layer 4: 图结构分析 ===

        if out_deg == 0:
            if in_deg > 50:
                return ('[SKIP: library_leaf]', 'library_function', 0.8)
            elif in_deg > 20:
                return ('[SKIP: utility_leaf]', 'utility_function', 0.7)
            elif in_deg >= 5:
                return ('[SKIP: leaf]', 'leaf_function', 0.6)
            else:
                return ('unknown', 'isolated', 0.5)

        if out_deg > 20:
            return ('core', 'orchestrator', 0.7)
        elif out_deg > 10:
            return ('core', 'main', 0.6)
        elif out_deg > 5:
            return ('core', 'logic', 0.5)

        if in_deg > 50 and out_deg <= 3:
            return ('[SKIP: wrapper]', 'library_wrapper', 0.7)
        elif in_deg > 20 and out_deg <= 2:
            return ('[SKIP: wrapper]', 'utility_wrapper', 0.6)

        if in_deg > 0 and out_deg > 0:
            if in_deg >= out_deg:
                return ('app_helper', 'helper', 0.4)
            else:
                return ('app_logic', 'logic', 0.4)

        return ('unknown', f'func_{func_name.split(".")[-1][:8]}', 0.3)

    def classify_with_limited_propagation(self) -> Dict[str, Dict]:
        """分类所有函数 + 限制性传播"""
        print("[*] Phase 1: 初步分类...")
        results = {}
        module_counts = Counter()

        # 第一阶段：初步分类
        for func_name in self.functions:
            category, clean_name, confidence = self.classify(func_name)
            results[func_name] = {
                'category': category,
                'clean_name': clean_name,
                'confidence': confidence,
                'in_degree': self.in_degree[func_name],
                'out_degree': self.out_degree[func_name]
            }
            module_counts[category] += 1

            # 记录基于字符串的分类（用于传播）
            if confidence >= 0.7 and not category.startswith('[SKIP:'):
                self.func_to_module[func_name] = {
                    'module': category,
                    'clean_name': clean_name,
                    'confidence': confidence,
                    'reason': 'string_matched'
                }

        print(f"    已分类 {len(results)} 个函数")

        # 第二阶段：限制性传播
        print(f"\n[*] Phase 2: 限制性传播（深度=1，最多50个函数）...")

        seeds = [f for f, info in self.func_to_module.items()
                if info.get('reason') == 'string_matched']
        print(f"    找到 {len(seeds)} 个种子函数")

        propagated_count = 0
        total_propagated = 0

        for seed in seeds:
            propagated = self._propagate_classification_limited(seed, max_depth=1)
            new_funcs = len([f for f in propagated if f not in self.func_to_module])

            if new_funcs > 0:
                print(f"    从 {seed} 传播 {new_funcs} 个函数 (模块: {self.func_to_module[seed]['module']})")

                for func, (module, clean_name, confidence) in propagated.items():
                    if func not in self.func_to_module:
                        self.func_to_module[func] = {
                            'module': module,
                            'clean_name': clean_name,
                            'confidence': confidence,
                            'reason': f'propagated_from_{seed}'
                        }
                        results[func]['category'] = module
                        results[func]['clean_name'] = clean_name
                        results[func]['confidence'] = confidence
                        propagated_count += 1

                total_propagated += new_funcs

                if total_propagated >= 50:  # 限制总传播数量
                    print(f"    达到传播上限 (50个函数)，停止传播")
                    break

        print(f"    总共传播了 {propagated_count} 个额外函数")

        # 最终统计
        final_counts = Counter()
        for func_name, result in results.items():
            final_counts[result['category']] += 1

        print(f"\n[*] 最终分类统计:")
        for category, count in sorted(final_counts.items(), key=lambda x: -x[1]):
            print(f"    - {category:30s}: {count:4d}")

        total = len(results)
        skipped = sum(count for cat, count in final_counts.items() if cat.startswith('[SKIP:'))
        print(f"\n    总计: {total} 个函数")
        print(f"    跳过: {skipped} 个函数 ({skipped*100//total}%)")
        print(f"    应用: {total-skipped} 个函数 ({(total-skipped)*100//total}%)")
        print(f"    Unknown: {final_counts.get('unknown', 0)} 个函数")

        return results

    def update_mapping(self, input_tsv: str, output_tsv: str):
        """更新 mapping.tsv 文件"""
        # 读取原始 mapping
        original_mapping = {}
        with open(input_tsv, 'r') as f:
            headers = f.readline().strip().split('\t')
            for line in f:
                parts = line.strip().split('\t')
                if len(parts) >= 2:
                    address = parts[0]
                    original_name = parts[1]
                    original_mapping[original_name] = {
                        'address': address,
                        'original': original_name
                    }

        # 分类所有函数
        results = self.classify_with_limited_propagation()

        # 写入新的 mapping
        with open(output_tsv, 'w') as f:
            f.write("address\toriginal_name\tclean_name\tmodule\n")

            for func_name, result in results.items():
                if func_name in original_mapping:
                    address = original_mapping[func_name]['address']
                else:
                    if '.' in func_name:
                        addr_hex = func_name.split('.')[-1]
                        address = f"0x{addr_hex}"
                    else:
                        address = "0x00000000"

                f.write(f"{address}\t{func_name}\t{result['clean_name']}\t{result['category']}\n")

        print(f"\n✅ 新的 mapping 已保存到 {output_tsv}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 classify_functions_improved.py <callgraph.json> [string_xref.md] [input_mapping.tsv] [output_mapping.tsv]")
        print("\nExample:")
        print("  python3 classify_functions_improved.py phase1/callgraph.json phase1/string_xref.md mapping.tsv mapping_improved.tsv")
        sys.exit(1)

    callgraph_json = sys.argv[1]
    string_xref = sys.argv[2] if len(sys.argv) > 2 else None
    input_mapping = sys.argv[3] if len(sys.argv) > 3 else 'mapping.tsv'
    output_mapping = sys.argv[4] if len(sys.argv) > 4 else 'mapping_improved.tsv'

    print(f"[*] 改进版分类器（限制性传播）")
    print(f"    - 调用图: {callgraph_json}")
    print(f"    - 字符串引用: {string_xref if string_xref else '无'}")
    print(f"    - 传播深度: 1")
    print(f"    - 传播上限: 50 个函数")

    # 创建分类器
    classifier = ImprovedFunctionClassifier(callgraph_json, string_xref)

    # 更新 mapping
    classifier.update_mapping(input_mapping, output_mapping)


if __name__ == '__main__':
    main()
