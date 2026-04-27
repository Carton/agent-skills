import json
import sys

def analyze():
    if len(sys.argv) < 3:
        print("Usage: analyze_callgraph.py <callgraph.json> <output.md>")
        return
        
    in_file = sys.argv[1]
    out_file = sys.argv[2]
    
    try:
        with open(in_file, 'r') as f:
            cg = json.load(f)
    except Exception as e:
        print(f"Error reading {in_file}: {e}")
        return

    # Count incoming and outgoing edges for each node
    nodes = {}
    for node in cg:
        name = node.get('name', 'unknown')
        size = node.get('size', 0)
        imports = node.get('imports', [])
        nodes[name] = {
            'size': size,
            'out_edges': imports,
            'in_edges': [],
            'is_import': name.startswith('sym.imp.')
        }
        
    for node_name, node_data in nodes.items():
        for imp in node_data['out_edges']:
            if imp in nodes:
                nodes[imp]['in_edges'].append(node_name)

    # Filter out imports from the main list, but keep track of how many times they are called
    funcs = []
    for name, data in nodes.items():
        if data['is_import']: continue
        
        # Count standard library/system calls vs internal calls
        std_calls = sum(1 for e in data['out_edges'] if e.startswith('sym.imp.'))
        internal_calls = len(data['out_edges']) - std_calls
        
        funcs.append({
            'name': name,
            'size': data['size'],
            'in_degree': len(data['in_edges']),
            'out_degree': len(data['out_edges']),
            'std_calls': std_calls,
            'internal_calls': internal_calls
        })
        
    # Sort by in_degree descending to find highly used utilities
    funcs.sort(key=lambda x: x['in_degree'], reverse=True)
    
    with open(out_file, 'w') as f:
        f.write("# Function Callgraph Summary\n\n")
        f.write("This summary provides metrics on all functions to help classify them into App Core vs 3rd-party/System logic.\n\n")
        f.write("| Function Name | Size | Times Called (In) | Calls Out | StdLib Calls | Internal Calls |\n")
        f.write("|---------------|------|-------------------|-----------|--------------|----------------|\n")
        for func in funcs:
            if func['size'] > 0 or func['in_degree'] > 0:
                f.write(f"| {func['name']} | {func['size']} | {func['in_degree']} | {func['out_degree']} | {func['std_calls']} | {func['internal_calls']} |\n")

if __name__ == '__main__':
    analyze()
