import xml.etree.ElementTree as ET
import re

XSD_NS = {'xs': 'http://www.w3.org/2001/XMLSchema'}

PRIMITIVES = {
    'xs:string': 'text', 'xs:decimal': 'number', 'xs:int': 'number',
    'xs:integer': 'number', 'xs:nonNegativeInteger': 'number',
    'xs:date': 'date', 'xs:dateTime': 'datetime-local',
    'xs:boolean': 'checkbox', 'xs:anyURI': 'url', 'xs:Name': 'text'
}

def clean_name(name):
    if not name: return ""
    name = name.strip().rstrip(';')
    if ':' in name: name = name.split(':')[-1]
    return "".join(part.title() for part in name.split("_"))

def find_global_group(root, group_ref):
    ref_clean = group_ref.split(':')[-1] if ':' in group_ref else group_ref
    return root.find(f"./xs:group[@name='{ref_clean}']", XSD_NS)

def find_global_complex_type(root, type_name):
    if not type_name: return None
    type_clean = type_name.split(':')[-1] if ':' in type_name else type_name
    return root.find(f"./xs:complexType[@name='{type_clean}']", XSD_NS)

def check_if_relational_ref(name, elem_type):
    name = name.lower() if name else ""
    elem_type = elem_type.lower() if elem_type else ""

    if "definition" in elem_type or "definition" in name or "name" in elem_type:
        return False, None

    is_person = (
                        elem_type.endswith('_ref') and "person" in elem_type
                ) or name in ["data_submitter", "measurement_researcher", "qc_researcher", "author"]

    is_org = (
                     elem_type.endswith('_ref') and "organization" in elem_type
             ) or name in ["data_provider", "funding_agency", "data_center", "document_source", "data_source", "organization"]

    if name == "dataset_contact":
        return True, "PersonDefinition"

    if is_person: return True, "PersonDefinition"
    if is_org: return True, "OrganizationDefinition"
    return False, None

def get_local_elements_only(node):
    elements = []
    if node is None: return elements

    def walk(current):
        for child in current:
            tag = child.tag.split('}')[-1]
            if tag == 'element':
                elements.append(child)
            elif tag in ['complexType', 'group'] and current != node:
                continue
            else:
                walk(child)
    walk(node)
    return elements

def extract_fields_tier_by_tier(node, root_element, seen_groups=None):
    if seen_groups is None: seen_groups = set()
    fields = []
    if node is None: return fields

    for group_el in node.findall('.//xs:group', XSD_NS):
        ref = group_el.get('ref')
        if ref and ref not in seen_groups:
            seen_groups.add(ref)
            group_node = find_global_group(root_element, ref)
            if group_node is not None:
                fields.extend(extract_fields_tier_by_tier(group_node, root_element, seen_groups))

    for derive in node.findall('.//xs:extension', XSD_NS) + node.findall('.//xs:restriction', XSD_NS):
        base = derive.get('base')
        if base and not base.startswith('xs:'):
            base_node = find_global_complex_type(root_element, base)
            if base_node is not None:
                fields.extend(extract_fields_tier_by_tier(base_node, root_element, seen_groups))

    direct_elements = get_local_elements_only(node)

    for child in direct_elements:
        f_name = child.get('name')
        f_type = child.get('type')
        max_occurs = child.get('maxOccurs', '1')
        if not f_name: continue

        is_ref, target_profile = check_if_relational_ref(f_name, f_type)
        if is_ref:
            fields.append({
                'kind': 'reference_selector',
                'name': f_name,
                'target_class': target_profile
            })
            continue

        inline_complex = child.find('xs:complexType', XSD_NS)
        if inline_complex is not None or max_occurs == 'unbounded':
            repeated_el = child.find('.//xs:element', XSD_NS)
            t_type = repeated_el.get('type') if repeated_el is not None else child.get('type')
            t_name = repeated_el.get('name') if repeated_el is not None else f_name

            is_sub_ref, sub_target = check_if_relational_ref(t_name, t_type)
            if is_sub_ref:
                fields.append({
                    'kind': 'reference_selector',
                    'name': f_name,
                    'target_class': sub_target
                })
            else:
                target_class = clean_name(t_type if t_type else t_name)
                if not target_class: target_class = clean_name(f_name)
                fields.append({
                    'kind': 'list_group',
                    'name': f_name,
                    'target_class': target_class,
                    'field_link': t_name
                })
            continue

        if f_type:
            f_type = f_type.strip().rstrip(';')
            if f_type in PRIMITIVES:
                fields.append({'kind': 'primitive', 'name': f_name, 'input_type': PRIMITIVES[f_type]})
            else:
                fields.append({'kind': 'child_component', 'name': f_name, 'type_link': f_type})
        else:
            fields.append({'kind': 'primitive', 'name': f_name, 'input_type': 'text'})

    return fields

def generate_library_code(root):
    code = [
        "import dash\nfrom dash import html, dcc\nimport dash_bootstrap_components as dbc",
        "from metadata_ref_selector import MetadataRefSelector",
        "from metadata_list_group import MetadataListGroup\n"
    ]

    targets = root.findall('.//xs:complexType', XSD_NS) + root.findall('.//xs:group', XSD_NS)
    processed_classes = set()

    for node in targets:
        type_name = node.get('name')
        if not type_name or type_name in processed_classes: continue
        processed_classes.add(type_name)

        fields = extract_fields_tier_by_tier(node, root)
        class_name = clean_name(type_name)
        display_title = type_name.replace('_', ' ').title()

        code.append(f"class {class_name}(html.Div):")
        code.append(f"    \"\"\"Autogenerated field layout configurations for: {type_name}\"\"\"")
        # 🎯 THE FIX: Constructor signature accepts explicit exclude_fields list
        code.append("    def __init__(self, instance_id='default', initial_values=None, xpath_prefix='dataset_metadata', exclude_fields=None, className=None, style=None, **kwargs):")
        code.append("        init_vals = initial_values if initial_values else {}")
        code.append("        exclusions = exclude_fields if exclude_fields else []")
        code.append("        layout_elements = [")
        code.append(f"            html.H5('{display_title}', className='mb-3 text-dark border-bottom pb-1 fw-bold'),")
        code.append("        ]")

        seen_fields = set()
        for f in fields:
            if f['name'] in seen_fields: continue
            seen_fields.add(f['name'])
            label = f['name'].replace('_', ' ').title()

            # 🎯 THE FIX: Every individual element block guards itself against the exclusion blacklist natively
            code.append(f"        if '{f['name']}' not in exclusions:")
            if f['kind'] == 'primitive':
                code.append("            layout_elements.append(dbc.Row([")
                code.append(f"                dbc.Label('{label}', width=4, className='text-muted small'),")
                code.append("                dbc.Col([")
                if f['input_type'] == 'checkbox':
                    code.append(f"                    dbc.Checkbox(id={{'type': 'primitive-input', 'xpath': xpath_prefix, 'field': '{f['name']}', 'instance': instance_id}}, value=bool(init_vals.get('{f['name']}', False)))")
                else:
                    code.append(f"                    dbc.Input(id={{'type': 'primitive-input', 'xpath': xpath_prefix, 'field': '{f['name']}', 'instance': instance_id}}, type='{f['input_type']}', value=init_vals.get('{f['name']}', ''), placeholder='Enter {label}...')")
                code.append("                ], width=8),")
                code.append("            ], className='mb-2'))")

            elif f['kind'] == 'reference_selector':
                code.append("            layout_elements.append(html.Div([")
                code.append(f"                MetadataRefSelector(ref_field_name='{f['name']}', target_class='{f['target_class']}', parent_complex_type=xpath_prefix, instance_id=instance_id)")
                code.append("            ], className='mb-4'))")

            elif f['kind'] == 'list_group':
                code.append("            layout_elements.append(html.Div([")
                code.append(f"                MetadataListGroup(list_field_name='{f['field_link']}', component_class=globals().get('{f['target_class']}', html.Div), instance_id=instance_id, xpath_prefix=f\"{{xpath_prefix}}/{{'{f['name']}'}}\")")
                code.append("            ], className='mb-4'))")

            elif f['kind'] == 'child_component':
                child_class = clean_name(f['type_link'])
                code.append("            layout_elements.append(html.Div([")
                code.append(f"                html.Small('Sub-section: {label}', className='text-info d-block mb-1 fw-bold'),")
                code.append(f"                {child_class}(instance_id=instance_id, initial_values=initial_values, xpath_prefix=f\"{{xpath_prefix}}/{{'{f['name']}'}}\", exclude_fields=None, className='ms-3 border-start ps-3 bg-white') if globals().get('{child_class}') else html.Div(dbc.Input(id={{'type': 'primitive-input', 'xpath': xpath_prefix, 'field': '{f['name']}', 'instance': instance_id}}, type='text', placeholder='Enter {label}...'))")
                code.append("            ], className='mb-3'))")

        code.append("        default_class = 'p-3 border rounded mb-3 bg-light shadow-sm'")
        code.append("        super().__init__(children=layout_elements, className=f'{default_class} {className}' if className else default_class, **kwargs)\n")

    return "\n".join(code)

if __name__ == '__main__':
    tree = ET.parse('ocads_metadata_schema.xsd')
    root = tree.getroot()
    with open('ocads_unified_components.py', 'w', encoding='utf-8') as f:
        f.write(generate_library_code(root))
    print("Success! Re-compiled self-filtering components.")