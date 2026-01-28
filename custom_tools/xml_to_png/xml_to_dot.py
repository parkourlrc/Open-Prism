import xml.etree.ElementTree as ET
import argparse
import os
import html

def escape_dot_label(label):
    """Escapes characters potentially problematic in DOT labels and handles newlines."""
    # Escape backslashes and double quotes
    escaped = label.replace('\\', '\\\\').replace('"', '\\"')
    # Replace newlines with \n for DOT
    escaped = escaped.replace('\n', '\\n')
    # Escape HTML special characters just in case, although DOT usually handles them
    escaped = html.escape(escaped)
    return escaped

def xml_to_dot(xml_path, dot_path):
    """
    Converts a custom architecture XML file to Graphviz DOT format.
    """
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
    except ET.ParseError as e:
        print(f"Error parsing XML file '{xml_path}': {e}")
        return False
    except FileNotFoundError:
        print(f"Error: XML file not found at '{xml_path}'")
        return False

    if root.tag != 'diagram':
        print(f"Error: Expected root tag 'diagram', found '{root.tag}'")
        return False

    dot_lines = []
    dot_lines.append("digraph G {")
    dot_lines.append("  rankdir=TB; // Top to Bottom layout, change to LR for Left to Right if preferred")
    dot_lines.append("  node [shape=record, style=filled, fillcolor=lightyellow];") # Default node style
    dot_lines.append("  edge [fontsize=10];") # Default edge style

    # Add diagram title and description as graph label if present
    title = root.find('title')
    description = root.find('description')
    graph_label_parts = []
    if title is not None and title.text:
        graph_label_parts.append(escape_dot_label(title.text.strip()))
    if description is not None and description.text:
        graph_label_parts.append(escape_dot_label(description.text.strip()))
    if graph_label_parts:
         dot_lines.append(f'  label="{ "\\n".join(graph_label_parts) }";')
         dot_lines.append("  labelloc=t;") # Place label at the top

    nodes = {} # Store node ID and its DOT representation

    # Process components (nodes)
    components_element = root.find('components')
    if components_element is not None:
        for component in components_element.findall('.//component'): # Find all components recursively
            comp_id = component.get('id')
            comp_label = component.get('label', comp_id) # Use ID if label is missing
            comp_type = component.get('type', '')

            # Build node label content
            node_label_content = [f"<{comp_id}> {escape_dot_label(comp_label)}"] # Use port for ID
            if comp_type:
                 node_label_content[0] += f"\\n({escape_dot_label(comp_type)})" # Add type on new line

            functions_element = component.find('functions')
            if functions_element is not None:
                funcs = [func.text.strip() for func in functions_element.findall('function') if func.text]
                if funcs:
                    # Add functions as a list within the record shape
                    func_list_str = "\\n- " + "\\n- ".join(escape_dot_label(f) for f in funcs)
                    node_label_content.append(f"Functions:{func_list_str}")

            # Handle sub_components (create clusters) - Basic implementation
            sub_components_element = component.find('sub_components')
            is_cluster = sub_components_element is not None and len(sub_components_element) > 0

            if is_cluster:
                 # Define a cluster subgraph
                 dot_lines.append(f'  subgraph "cluster_{comp_id}" {{')
                 dot_lines.append(f'    label = "{escape_dot_label(comp_label)}\\n({escape_dot_label(comp_type)})";')
                 dot_lines.append(f'    style=filled;')
                 dot_lines.append(f'    color=lightgrey;')
                 # Add nodes within the cluster here (processed in the main loop)
                 # We store cluster info for later node placement
                 nodes[comp_id] = {'is_cluster': True, 'label': comp_label, 'type': comp_type}
                 # Note: This simple approach doesn't draw the cluster box itself as a node,
                 # it just groups the sub-nodes visually.
            else:
                 # Define a regular node
                 node_label_str = " | ".join(node_label_content) # Separate sections with '|' for record shape
                 node_definition = f'  "{comp_id}" [label="{node_label_str}"];'
                 dot_lines.append(node_definition)
                 nodes[comp_id] = {'is_cluster': False}


    # Place nodes inside clusters if they belong to one
    processed_nodes_in_clusters = set()
    if components_element is not None:
        for component in components_element.findall('component'):
             comp_id = component.get('id')
             sub_components_element = component.find('sub_components')
             if sub_components_element is not None:
                 for sub_component in sub_components_element.findall('component'):
                     sub_comp_id = sub_component.get('id')
                     if sub_comp_id in nodes and not nodes[sub_comp_id]['is_cluster'] and sub_comp_id not in processed_nodes_in_clusters:
                         # Find the node definition and move it inside the cluster subgraph
                         node_def_to_move = None
                         original_index = -1
                         for i, line in enumerate(dot_lines):
                             if line.strip().startswith(f'"{sub_comp_id}"'):
                                 node_def_to_move = line
                                 original_index = i
                                 break
                         if node_def_to_move and original_index != -1:
                             # Find the cluster start line
                             cluster_start_index = -1
                             for i, line in enumerate(dot_lines):
                                 if line.strip().startswith(f'subgraph "cluster_{comp_id}"'):
                                     cluster_start_index = i
                                     break
                             if cluster_start_index != -1:
                                 # Remove original definition and insert into cluster
                                 dot_lines.pop(original_index)
                                 dot_lines.insert(cluster_start_index + 1, node_def_to_move) # Insert after cluster opening
                                 processed_nodes_in_clusters.add(sub_comp_id)


    # Close any open cluster subgraphs
    open_clusters = sum(1 for line in dot_lines if 'subgraph "cluster_' in line)
    closed_clusters = sum(1 for line in dot_lines if line.strip() == '}')
    dot_lines.extend(['  }'] * (open_clusters - closed_clusters))


    # Process connections (edges)
    connections_element = root.find('connections')
    if connections_element is not None:
        for connection in connections_element.findall('connection'):
            conn_from = connection.get('from')
            conn_to = connection.get('to')
            conn_label = connection.get('label', '')
            # conn_type = connection.get('type', '') # Could be used for styling later

            if conn_from in nodes and conn_to in nodes:
                 # Handle connections involving clusters (connect to cluster or nodes within)
                 # For simplicity, we connect the cluster ID directly if 'from' or 'to' is a cluster.
                 # Graphviz might require specific handling (lhead/ltail) for better cluster edges.
                 from_node_id = f'"{conn_from}"'
                 to_node_id = f'"{conn_to}"'

                 # Basic edge definition
                 edge_label_str = f' [label="{escape_dot_label(conn_label)}"]' if conn_label else ''
                 dot_lines.append(f'  {from_node_id} -> {to_node_id}{edge_label_str};')
            else:
                 print(f"Warning: Skipping connection from '{conn_from}' to '{conn_to}' as one or both nodes were not found or defined.")


    dot_lines.append("}")

    try:
        os.makedirs(os.path.dirname(dot_path), exist_ok=True)
        with open(dot_path, 'w', encoding='utf-8') as f:
            f.write("\n".join(dot_lines))
        print(f"Successfully converted '{xml_path}' to DOT format at '{dot_path}'")
        return True
    except IOError as e:
        print(f"Error writing DOT file to '{dot_path}': {e}")
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert custom architecture XML to Graphviz DOT format.")
    parser.add_argument("xml_input", help="Path to the input XML file.")
    parser.add_argument("dot_output", help="Path to the output DOT file.")
    args = parser.parse_args()

    xml_to_dot(args.xml_input, args.dot_output)