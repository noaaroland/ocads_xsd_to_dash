import os
import xml.etree.ElementTree as ET

# Constant Configuration Elements
TEMP_XML_FILE = "temporary_file.xml"
NS_URL = "https://ncei.noaa.gov/ocads/v4.6"


def read_existing(key):
    """Safely reads or initializes a clean namespaced OCADS XML root node tracking file."""
    if not os.path.exists(key) or os.path.getsize(key) == 0:
        root = ET.Element(f"{{{NS_URL}}}dataset_metadata")
        # Ensure initial empty structural pools are present
        ET.SubElement(root, f"{{{NS_URL}}}people")
        ET.SubElement(root, f"{{{NS_URL}}}organizations")

        ET.register_namespace('', NS_URL)
        tree = ET.ElementTree(root)
        tree.write(key, encoding='utf-8', xml_declaration=True)
        return root

    try:
        tree = ET.parse(key)
        return tree.getroot()
    except Exception:
        # Fallback reset if file becomes corrupted or un-parseable
        root = ET.Element(f"{{{NS_URL}}}dataset_metadata")
        return root


def save_existing(key, root):
    """
    🎯 THE FIX: Normalizes every element tag to the default namespace,
    completely stripping out spurious 'ns0' prefixes before writing to disk.
    """
    # 1. Iterate through every node in the tree and force it into the clean default namespace
    for elem in root.iter():
        if elem.tag and not elem.tag.startswith("{"):
            elem.tag = f"{{{NS_URL}}}{elem.tag}"
        elif elem.tag and "}" in elem.tag:
            local_tag = elem.tag.split("}")[-1]
            elem.tag = f"{{{NS_URL}}}{local_tag}"

    # 2. Register an explicit blank string to map directly to the OCADS default namespace
    ET.register_namespace('', NS_URL)

    # 3. Stream cleanly out to disk
    tree = ET.ElementTree(root)
    tree.write(key, encoding='utf-8', xml_declaration=True)


def get_all_entities_from_xml(xml_file_path, target_collection, root_node=None):
    """
    Namespace-agnostic tree scanner that loops through ALL collection instances
    to guarantee rowData is fully populated. Accepts an optional in-memory root_node
    to safely bypass disk-read race conditions during save lifecycles.
    """
    # 🎯 THE FIX: Use the active in-memory tree if passed, bypassing the disk lock completely
    if root_node is not None:
        root = root_node
    else:
        try:
            tree = ET.parse(xml_file_path)
            root = tree.getroot()
        except Exception:
            return []

    results = []
    element_tag = "person" if target_collection == "people" else "organization"

    for node in root.iter():
        tag_clean = node.tag.split('}')[-1]
        if tag_clean == target_collection:
            for item in node:
                raw_tag = item.tag.split('}')[-1] if '}' in item.tag else item.tag
                if raw_tag != element_tag:
                    continue

                obj_id = item.get("object_id", "")
                display_name = ""
                first_name = ""
                last_name = ""
                org_name = ""

                for child in item.iter():
                    tag_local = child.tag.split('}')[-1]
                    if tag_local == "first" and child.text:
                        first_name = child.text.strip()
                    elif tag_local == "last" and child.text:
                        last_name = child.text.strip()
                    elif tag_local in ["organization_name", "name"] and child.text and not display_name:
                        org_name = child.text.strip()

                if first_name or last_name:
                    display_name = f"{last_name}, {first_name}".strip(", ")
                elif org_name:
                    display_name = org_name
                else:
                    display_name = f"Unnamed Record ({obj_id})"

                results.append({
                    "object_id": obj_id,
                    "name": display_name
                })

    return results


def get_variables_from_xml(xml_file_path):
    """
    Crawls the variables collection pool in the XML document and aggregates polymorphic
    parameter entries into clean, standardized rows for the Variable Matrix control table.
    """
    try:
        tree = ET.parse(xml_file_path)
        root = tree.getroot()
    except Exception:
        return []

    rows = []

    # Locate the root variables node container using a safe wildcard strategy
    variables_node = None
    for node in root.iter():
        if node.tag.split('}')[-1] == "variables":
            variables_node = node
            break

    if variables_node is None:
        return rows

    tag_display_names = {
        "basic": "Basic Column",
        "observed": "Standard Observed",
        "DIC": "Carbon: DIC Profile",
        "TA": "Carbon: TA Profile",
        "pH": "Carbon: pH Profile",
        "co2_continuous": "CO2: Continuous Track",
        "co2_discrete": "CO2: Discrete Sample"
    }

    for var_element in variables_node:
        raw_tag = var_element.tag.split("}")[-1] if "}" in var_element.tag else var_element.tag
        if raw_tag not in tag_display_names:
            continue

        obj_id = var_element.get("object_id", "Unknown")
        column_header = f"Unnamed Axis (#{obj_id})"
        unit_label = "Unspecified"

        col_node = var_element.find(".//{*}dataset_variable_name")
        if col_node is not None and col_node.text:
            column_header = col_node.text.strip()

        unit_node = var_element.find(".//{*}units")
        if unit_node is not None and unit_node.text:
            unit_label = unit_node.text.strip()
        else:
            ph_scale_node = var_element.find(".//{*}ph_scale")
            if ph_scale_node is not None and ph_scale_node.text:
                unit_label = f"pH Scale: {ph_scale_node.text.strip()}"

        rows.append({
            "object_id": obj_id,
            "column_name": column_header,
            "type_class": tag_display_names[raw_tag],
            "units": unit_label
        })

    return rows


def get_form_data_from_xml(xml_file_path, base_xpath_target):
    """
    🎯 THE FIX: Namespace-resilient layout path evaluator that scans for saved
    primitive parameters using absolute structural tag matching trajectories.
    """
    try:
        tree = ET.parse(xml_file_path)
        root = tree.getroot()
    except Exception:
        return {}

    data = {}
    target_steps = [step for step in base_xpath_target.split('/') if step]

    # Trace nodes by parsing tag segments sequentially, ignoring outer namespace strings
    current_nodes = [root]
    for step in target_steps:
        next_nodes = []
        for node in current_nodes:
            for child in node:
                child_tag = child.tag.split('}')[-1]
                if child_tag == step:
                    next_nodes.append(child)
        current_nodes = next_nodes
        if not current_nodes:
            break

    if current_nodes:
        target_node = current_nodes[0]
        for child in target_node:
            child_tag = child.tag.split('}')[-1]
            if len(child) == 0 and child.text:
                data[child_tag] = child.text.strip()
            elif child.get("object_id"):
                data[f"{child_tag}__ref"] = child.get("object_id")

    return data