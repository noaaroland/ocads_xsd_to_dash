import xml.etree.ElementTree as ET
import os

# Path to temporary XML file
TEMP_XML_FILE = "temporary_file.xml"
NS_URL = "https://ncei.noaa.gov/ocads/v4.6"

# This will become a call to cache the data to redis, the xml_file will be the redis key.
def save_existing(key, root):
    updated_xml_str = ET.tostring(root, encoding='unicode', method='xml')
    with open(key, 'w', encoding='utf-8') as f:
        f.write(updated_xml_str)

# This should become a call to read to redis using the passed in key
def read_existing(key):
    if os.path.exists(key):
        with open(key, 'r', encoding='utf-8') as f:
            raw_xml = f.read()
            root = ET.fromstring(raw_xml)
    else:
        # Fallback to creating a fresh root document if file doesn't exist
        root = ET.Element("dataset_metadata", {
            "xmlns": "https://ncei.noaa.gov/ocads/v4.6",
            "metadata_version": "v4.6"
        })
    return root


def get_all_entities_from_xml(xml_file_path, target_collection):
    import xml.etree.ElementTree as ET

    try:
        tree = ET.parse(xml_file_path)
        root = tree.getroot()
    except Exception:
        return []

    rows = []
    element_tag = "person" if target_collection == "people" else "organization"

    # 🔗 {*} matches ANY namespace prefix or lack thereof seamlessly
    collection_node = root.find(f".//{{*}}{target_collection}")
    if collection_node is None:
        return rows

    entity_nodes = collection_node.findall(f"./{{*}}{element_tag}")

    for entity in entity_nodes:
        obj_id = entity.get("object_id")
        # Where the fallback placeholder is initialized:
        display_name = f"Unknown {element_tag.title()} (#{obj_id})"

        if target_collection == "people":
            # Direct child lookup using namespace-agnostic wildcards
            name_node = entity.find("./{*}name")
            if name_node is not None:
                first = name_node.find("./{*}first")
                last = name_node.find("./{*}last")

                first_text = first.text.strip() if first is not None and first.text else ""
                last_text = last.text.strip() if last is not None and last.text else ""
                if first_text or last_text:
                    display_name = f"{first_text} {last_text}".strip()
        else:
            # Route organization name elements cleanly
            org_def = entity.find("./{*}organization_definition")
            name_node = org_def.find("./{*}name") if org_def is not None else entity.find("./{*}name")
            if name_node is not None and name_node.text:
                display_name = name_node.text.strip()

        rows.append({
            "object_id": obj_id,
            "name": display_name
        })

    return rows

def get_variables_from_xml(xml_file_path):
    """
    Crawls the variables collection pool in the XML document and aggregates polymorphic
    parameter entries into clean, standardized rows for the Variable Matrix control table.
    """
    import xml.etree.ElementTree as ET
    from utils import read_existing

    try:
        root = read_existing(xml_file_path)
    except Exception:
        return []

    rows = []

    # Locate the root variables node container
    variables_node = root.find(".//{*}variables")
    if variables_node is None:
        return rows

    # The dictionary matching polymorphic XSD choice tags back to readable titles
    tag_display_names = {
        "basic": "Basic Column",
        "observed": "Standard Observed",
        "DIC": "Carbon: DIC Profile",
        "TA": "Carbon: TA Profile",
        "pH": "Carbon: pH Profile",
        "co2_continuous": "CO2: Continuous Track",
        "co2_discrete": "CO2: Discrete Sample"
    }

    # Loop through every child element inside the collection pool, regardless of its specific tag choice
    for var_element in variables_node:
        # Strip namespace wrapper brackets if present to get the raw string tag name
        raw_tag = var_element.tag.split("}")[-1] if "}" in var_element.tag else var_element.tag
        if raw_tag not in tag_display_names:
            continue

        obj_id = var_element.get("object_id", "Unknown")
        column_header = f"Unnamed Axis (#{obj_id})"
        unit_label = "Unspecified"

        # Deep lookup the column key header name within minimum_variable_fields
        col_node = var_element.find(".//{*}dataset_variable_name")
        if col_node is not None and col_node.text:
            column_header = col_node.text.strip()

        # Lookup the measurement units attribute values
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


def get_form_data_from_xml(xml_file_path, complex_type):
    """
    Recursively crawls an XML node matching a complex_type name and flattens all
    leaf element text nodes into a dictionary for form value hydration.
    """
    import xml.etree.ElementTree as ET
    try:
        tree = ET.parse(xml_file_path)
        root = tree.getroot()
    except Exception:
        return {}

    data = {}
    # Find the target complexType block using a namespace wildcard
    node = root.find(f".//{{*}}{complex_type}")
    if node is not None:
        # Loop through every element inside this block's subtree
        for child in node.iter():
            tag_clean = child.tag.split("}")[-1] if "}" in child.tag else child.tag
            # If it's a leaf node containing text, capture it
            if len(child) == 0 and child.text:
                data[tag_clean] = child.text.strip()
    return data